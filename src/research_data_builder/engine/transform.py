"""Ordered deterministic transformations over one long-form variable."""

from decimal import Decimal

import polars as pl

from research_data_builder.recipes.schemas import (
    TransformationDefinition,
    TransformationOperation,
)


def apply_transformations(
    frame: pl.DataFrame,
    steps: tuple[TransformationDefinition, ...],
    *,
    variable: str,
) -> pl.DataFrame:
    """Apply declared non-aggregation transformations in recipe order."""
    result = frame.sort(["entity", "period"], nulls_last=False)
    for step in steps:
        if step.variable != variable or step.operation is TransformationOperation.AGGREGATE:
            continue
        periods = int(step.parameters.get("periods", 1))
        previous = pl.col("value").shift(periods).over("entity")
        if step.operation is TransformationOperation.LAG:
            expression = previous
        elif step.operation is TransformationOperation.DIFFERENCE:
            expression = pl.col("value") - previous
        elif step.operation is TransformationOperation.PERCENT_CHANGE:
            expression = (
                pl.when(previous.is_not_null() & (previous != 0))
                .then((pl.col("value") / previous - 1) * 100)
                .otherwise(None)
            )
        elif step.operation is TransformationOperation.SCALE:
            factor = Decimal(str(step.parameters["factor"]))
            expression = pl.col("value") * pl.lit(factor)
        else:  # pragma: no cover - enum validation prevents this branch
            raise ValueError(f"unsupported transformation: {step.operation}")
        result = result.with_columns(
            expression.cast(pl.Decimal(precision=30, scale=10)).alias("value")
        )
    return result
