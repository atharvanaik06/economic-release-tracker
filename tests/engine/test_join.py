"""Tests for join rules, stable output, and unmatched-key reporting."""

from datetime import date
from decimal import Decimal

import polars as pl

from research_data_builder.engine.join import join_variables
from research_data_builder.recipes.schemas import JoinType


def variable_frame(name: str, entities: list[str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "entity": entities,
            "period": [date(2024, 1, 1)] * len(entities),
            "variable": [name] * len(entities),
            "value": [Decimal(str(index + 1)) for index in range(len(entities))],
        },
        schema_overrides={"value": pl.Decimal(30, 10)},
    )


def test_outer_join_preserves_union_and_reports_unmatched_keys() -> None:
    result, reports = join_variables(
        {
            "gdp": variable_frame("gdp", ["CZE", "DEU"]),
            "inflation": variable_frame("inflation", ["DEU", "FRA"]),
        },
        keys=("entity", "period"),
        join_type=JoinType.OUTER,
    )

    assert result.columns == ["entity", "period", "gdp", "inflation"]
    assert result["entity"].to_list() == ["CZE", "DEU", "FRA"]
    assert result["inflation"].to_list()[0] is None
    assert reports[0].left_only_keys == 1
    assert reports[0].right_only_keys == 1


def test_inner_join_preserves_only_intersection() -> None:
    result, _ = join_variables(
        {
            "gdp": variable_frame("gdp", ["CZE", "DEU"]),
            "inflation": variable_frame("inflation", ["DEU", "FRA"]),
        },
        keys=("entity", "period"),
        join_type=JoinType.INNER,
    )
    assert result["entity"].to_list() == ["DEU"]
