"""Tests for coverage, missing, range, type, key, and join validation."""

from datetime import date
from decimal import Decimal

import polars as pl

from research_data_builder.engine import ExecutionResult, JoinReport
from research_data_builder.providers import Frequency
from research_data_builder.recipes.schemas import RecipeDefinition
from research_data_builder.validation import validate_dataset
from research_data_builder.validation.engine import _periods
from tests.recipes.test_schemas import valid_recipe


def test_validation_reports_coverage_missing_ranges_and_join_mismatches() -> None:
    payload = valid_recipe()
    payload["start_date"] = "2024-01-01"
    payload["end_date"] = "2024-12-31"
    payload["validations"] = [
        {
            "variable": "inflation",
            "minimum": -10,
            "maximum": 20,
            "severity": "error",
        }
    ]
    payload["transformations"] = []
    recipe = RecipeDefinition.model_validate(payload)
    frame = pl.DataFrame(
        {
            "entity": ["CZE"],
            "period": [date(2024, 1, 1)],
            "gdp_growth": [Decimal("2.5")],
            "inflation": [Decimal("25")],
        },
        schema_overrides={
            "gdp_growth": pl.Decimal(30, 10),
            "inflation": pl.Decimal(30, 10),
        },
    )
    result = ExecutionResult(
        frame=frame,
        join_reports=(JoinReport("inflation", 1, 0),),
        entity_mapping_version="v1",
    )

    report = validate_dataset(result, recipe)

    assert report.passed is False
    assert report.expected_row_count == 2
    assert report.coverage_percent == 50.0
    assert {issue.code for issue in report.issues} == {
        "missing_coverage",
        "range_violation",
        "unmatched_join_keys",
    }
    assert report.as_dict()["summary"]["errors"] == 1


def test_validation_passes_complete_decimal_dataset() -> None:
    payload = valid_recipe()
    payload["start_date"] = "2024-01-01"
    payload["end_date"] = "2024-12-31"
    payload["transformations"] = []
    recipe = RecipeDefinition.model_validate(payload)
    frame = pl.DataFrame(
        {
            "entity": ["CZE", "DEU"],
            "period": [date(2024, 1, 1), date(2024, 1, 1)],
            "gdp_growth": [Decimal("2.5"), Decimal("1.5")],
            "inflation": [Decimal("3"), Decimal("2")],
        },
        schema_overrides={
            "gdp_growth": pl.Decimal(30, 10),
            "inflation": pl.Decimal(30, 10),
        },
    )

    report = validate_dataset(
        ExecutionResult(frame=frame, join_reports=(), entity_mapping_version="v1"), recipe
    )

    assert report.passed is True
    assert report.coverage_percent == 100.0
    assert report.issues[0].code == "validation_passed"


def test_validation_blocks_duplicate_schema_type_and_entirely_missing_variable() -> None:
    payload = valid_recipe()
    payload["start_date"] = "2024-01-01"
    payload["end_date"] = "2024-12-31"
    payload["transformations"] = []
    recipe = RecipeDefinition.model_validate(payload)
    frame = pl.DataFrame(
        {
            "entity": ["CZE", "CZE"],
            "period": [date(2024, 1, 1), date(2024, 1, 1)],
            "gdp_growth": [2.5, 2.5],
            "inflation": [None, None],
            "unexpected": [1, 1],
        },
        schema_overrides={"inflation": pl.Decimal(30, 10)},
    )

    report = validate_dataset(
        ExecutionResult(frame=frame, join_reports=(), entity_mapping_version="v1"), recipe
    )

    assert report.passed is False
    codes = {issue.code for issue in report.issues}
    assert {"duplicate_keys", "unexpected_schema", "unexpected_type", "missing_values"} <= codes
    assert any(
        issue.variable == "inflation" and issue.severity == "error" for issue in report.issues
    )


def test_expected_period_generation_supports_monthly_and_quarterly_recipes() -> None:
    assert _periods(date(2024, 2, 15), date(2024, 4, 30), Frequency.MONTHLY) == (
        date(2024, 2, 1),
        date(2024, 3, 1),
        date(2024, 4, 1),
    )
    assert _periods(date(2024, 2, 15), date(2024, 7, 1), Frequency.QUARTERLY) == (
        date(2024, 1, 1),
        date(2024, 4, 1),
        date(2024, 7, 1),
    )
    assert _periods(date(2024, 1, 1), date(2024, 1, 2), Frequency.DAILY) is None
