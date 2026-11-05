"""Deterministic coverage, key, type, missing, range, and join validation."""

from datetime import date
from decimal import Decimal

import polars as pl

from research_data_builder.engine.result import ExecutionResult
from research_data_builder.providers.domain import Frequency
from research_data_builder.recipes.schemas import RecipeDefinition
from research_data_builder.validation.models import Severity, ValidationIssue, ValidationReport


def validate_dataset(
    result: ExecutionResult,
    recipe: RecipeDefinition,
) -> ValidationReport:
    frame = result.frame
    issues: list[ValidationIssue] = []
    keys = list(recipe.join.keys)
    variables = [variable.output_name for variable in recipe.variables]

    duplicate_count = frame.group_by(keys).len().filter(pl.col("len") > 1).height
    if duplicate_count:
        issues.append(
            ValidationIssue(
                code="duplicate_keys",
                severity="error",
                message=f"dataset contains {duplicate_count} duplicate key groups",
                details={"keys": keys, "duplicate_groups": duplicate_count},
            )
        )

    expected_columns = [*keys, *variables]
    if frame.columns != expected_columns:
        issues.append(
            ValidationIssue(
                code="unexpected_schema",
                severity="error",
                message="dataset columns or ordering do not match the frozen recipe",
                details={"expected": expected_columns, "actual": frame.columns},
            )
        )
    for variable in variables:
        if variable in frame.columns and not isinstance(frame.schema[variable], pl.Decimal):
            issues.append(
                ValidationIssue(
                    code="unexpected_type",
                    severity="error",
                    variable=variable,
                    message=f"{variable} must use a decimal column",
                    details={"actual": str(frame.schema[variable])},
                )
            )

    expected_keys = _expected_keys(recipe)
    expected_count = len(expected_keys) if expected_keys is not None else None
    coverage_percent: float | None = None
    if expected_keys is not None:
        actual_keys = {tuple(row[key] for key in keys) for row in frame.select(keys).to_dicts()}
        missing_keys = sorted(expected_keys.difference(actual_keys), key=str)
        coverage_percent = (
            round(100 * len(actual_keys.intersection(expected_keys)) / len(expected_keys), 4)
            if expected_keys
            else 100.0
        )
        if missing_keys:
            issues.append(
                ValidationIssue(
                    code="missing_coverage",
                    severity="warning",
                    message=f"{len(missing_keys)} requested keys are absent",
                    details={"missing_keys": [list(key) for key in missing_keys[:100]]},
                )
            )

    missing_by_variable: dict[str, int] = {}
    for variable in variables:
        if variable not in frame.columns:
            continue
        missing = frame[variable].null_count()
        missing_by_variable[variable] = missing
        if missing:
            severity: Severity = "error" if missing == frame.height and frame.height else "warning"
            issues.append(
                ValidationIssue(
                    code="missing_values",
                    severity=severity,
                    variable=variable,
                    message=f"{variable} contains {missing} missing values",
                    details={"missing_count": missing, "row_count": frame.height},
                )
            )

    for rule in recipe.validations:
        if rule.variable not in frame.columns:
            continue
        expression = pl.lit(False)
        if rule.minimum is not None:
            expression = expression | (pl.col(rule.variable) < Decimal(str(rule.minimum)))
        if rule.maximum is not None:
            expression = expression | (pl.col(rule.variable) > Decimal(str(rule.maximum)))
        violations = frame.filter(pl.col(rule.variable).is_not_null() & expression).height
        if violations:
            issues.append(
                ValidationIssue(
                    code="range_violation",
                    severity=rule.severity.value,
                    variable=rule.variable,
                    message=f"{rule.variable} has {violations} values outside its declared range",
                    details={
                        "minimum": rule.minimum,
                        "maximum": rule.maximum,
                        "violation_count": violations,
                    },
                )
            )

    for join_report in result.join_reports:
        if join_report.left_only_keys or join_report.right_only_keys:
            issues.append(
                ValidationIssue(
                    code="unmatched_join_keys",
                    severity="warning",
                    variable=join_report.variable,
                    message=f"{join_report.variable} has unmatched join keys",
                    details={
                        "left_only_keys": join_report.left_only_keys,
                        "right_only_keys": join_report.right_only_keys,
                    },
                )
            )

    if not issues:
        issues.append(
            ValidationIssue(
                code="validation_passed",
                severity="info",
                message="all dataset validation checks passed",
            )
        )
    return ValidationReport(
        passed=not any(issue.severity == "error" for issue in issues),
        row_count=frame.height,
        expected_row_count=expected_count,
        coverage_percent=coverage_percent,
        issues=tuple(issues),
        missing_by_variable=missing_by_variable,
    )


def _expected_keys(recipe: RecipeDefinition) -> set[tuple[object, ...]] | None:
    periods = _periods(recipe.start_date, recipe.end_date, recipe.output_frequency)
    if periods is None:
        return None
    if recipe.join.keys == ("period",):
        return {(period,) for period in periods}
    return {(entity, period) for entity in recipe.entities for period in periods}


def _periods(start: date, end: date, frequency: Frequency) -> tuple[date, ...] | None:
    values: list[date] = []
    current = start
    if frequency is Frequency.ANNUAL:
        current = date(start.year, 1, 1)
        while current <= end:
            values.append(current)
            current = date(current.year + 1, 1, 1)
        return tuple(values)
    if frequency is Frequency.QUARTERLY:
        month = ((start.month - 1) // 3) * 3 + 1
        current = date(start.year, month, 1)
        while current <= end:
            values.append(current)
            month = current.month + 3
            current = date(current.year + (month > 12), ((month - 1) % 12) + 1, 1)
        return tuple(values)
    if frequency is Frequency.MONTHLY:
        current = date(start.year, start.month, 1)
        while current <= end:
            values.append(current)
            current = date(
                current.year + (current.month == 12),
                1 if current.month == 12 else current.month + 1,
                1,
            )
        return tuple(values)
    return None
