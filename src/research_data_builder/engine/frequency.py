"""Explicit, rejection-first frequency conversion."""

from typing import Literal

import polars as pl

from research_data_builder.engine.harmonize import HarmonizationError
from research_data_builder.providers.domain import Frequency

AggregationMethod = Literal["mean", "sum", "min", "max", "last"]

FREQUENCY_RANK = {
    Frequency.DAILY: 0,
    Frequency.WEEKLY: 1,
    Frequency.MONTHLY: 2,
    Frequency.QUARTERLY: 3,
    Frequency.SEMIANNUAL: 4,
    Frequency.ANNUAL: 5,
}


def convert_frequency(
    frame: pl.DataFrame,
    *,
    source: Frequency,
    target: Frequency,
    method: AggregationMethod | None,
) -> pl.DataFrame:
    """Aggregate to a coarser frequency only when an explicit method is supplied."""
    if source is target:
        if method is not None:
            raise HarmonizationError("aggregation is unnecessary when frequencies already match")
        return frame
    if source not in FREQUENCY_RANK or target not in FREQUENCY_RANK:
        raise HarmonizationError("unsupported or unknown frequency conversion")
    if FREQUENCY_RANK[source] > FREQUENCY_RANK[target]:
        raise HarmonizationError("upsampling to a finer frequency is not supported")
    if method is None:
        raise HarmonizationError(
            f"converting {source.value} to {target.value} requires an aggregate transformation"
        )

    bucket = _period_bucket(target)
    staged = frame.with_columns(bucket.alias("period")).sort(["entity", "period"])
    value = pl.col("value")
    non_null_count = value.count()
    if method == "mean":
        aggregate = value.mean()
    elif method == "sum":
        aggregate = pl.when(non_null_count > 0).then(value.sum()).otherwise(None)
    elif method == "min":
        aggregate = value.min()
    elif method == "max":
        aggregate = value.max()
    else:
        aggregate = value.drop_nulls().last()

    return (
        staged.group_by(["entity", "period", "variable"], maintain_order=True)
        .agg(aggregate.cast(pl.Decimal(precision=30, scale=10)).alias("value"))
        .sort(["entity", "period"], nulls_last=False)
    )


def _period_bucket(target: Frequency) -> pl.Expr:
    period = pl.col("period")
    if target is Frequency.ANNUAL:
        return pl.date(period.dt.year(), pl.lit(1), pl.lit(1))
    if target is Frequency.SEMIANNUAL:
        month = pl.when(period.dt.month() <= 6).then(1).otherwise(7)
        return pl.date(period.dt.year(), month, pl.lit(1))
    if target is Frequency.QUARTERLY:
        month = ((period.dt.month() - 1) // 3) * 3 + 1
        return pl.date(period.dt.year(), month, pl.lit(1))
    if target is Frequency.MONTHLY:
        return pl.date(period.dt.year(), period.dt.month(), pl.lit(1))
    if target in {Frequency.WEEKLY, Frequency.DAILY}:
        raise HarmonizationError("weekly and daily aggregation buckets are not supported")
    raise HarmonizationError("unsupported target frequency")
