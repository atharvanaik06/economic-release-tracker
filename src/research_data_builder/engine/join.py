"""Deterministic wide-table joins with unmatched-key reporting."""

from collections.abc import Mapping
from typing import Literal

import polars as pl

from research_data_builder.engine.harmonize import HarmonizationError
from research_data_builder.engine.result import JoinReport
from research_data_builder.recipes.schemas import JoinType


def join_variables(
    frames: Mapping[str, pl.DataFrame],
    *,
    keys: tuple[str, ...],
    join_type: JoinType,
) -> tuple[pl.DataFrame, tuple[JoinReport, ...]]:
    """Join ordered long-form variables and explain every unmatched key set."""
    if not frames:
        raise HarmonizationError("at least one variable frame is required")

    prepared = [(_name, _wide(frame, _name, keys)) for _name, frame in frames.items()]
    _, result = prepared[0]
    reports: list[JoinReport] = []
    polars_join: Literal["full", "inner", "left"]
    if join_type is JoinType.OUTER:
        polars_join = "full"
    elif join_type is JoinType.INNER:
        polars_join = "inner"
    else:
        polars_join = "left"

    for variable, right in prepared[1:]:
        left_keys = result.select(keys).unique()
        right_keys = right.select(keys).unique()
        left_only = left_keys.join(right_keys, on=keys, how="anti").height
        right_only = right_keys.join(left_keys, on=keys, how="anti").height
        reports.append(
            JoinReport(
                variable=variable,
                left_only_keys=left_only,
                right_only_keys=right_only,
            )
        )
        result = result.join(right, on=keys, how=polars_join, coalesce=True)

    value_columns = [name for name, _ in prepared]
    result = result.select([*keys, *value_columns]).sort(list(keys), nulls_last=False)
    return result, tuple(reports)


def _wide(frame: pl.DataFrame, variable: str, keys: tuple[str, ...]) -> pl.DataFrame:
    required = {*keys, "variable", "value"}
    missing = required.difference(frame.columns)
    if missing:
        raise HarmonizationError(f"{variable} frame is missing columns: {sorted(missing)}")
    if frame.height and frame["variable"].unique().to_list() != [variable]:
        raise HarmonizationError(f"frame variable does not match output name: {variable}")
    return frame.select([*keys, pl.col("value").alias(variable)])
