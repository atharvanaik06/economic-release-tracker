"""Tests for ordered transformations and null semantics."""

from datetime import date
from decimal import Decimal

import polars as pl

from research_data_builder.engine.transform import apply_transformations
from research_data_builder.recipes.schemas import TransformationDefinition


def frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "entity": ["CZE", "CZE", "CZE"],
            "period": [date(2022, 1, 1), date(2023, 1, 1), date(2024, 1, 1)],
            "variable": ["gdp"] * 3,
            "value": [Decimal("100"), Decimal("110"), Decimal("121")],
        },
        schema_overrides={"value": pl.Decimal(30, 10)},
    )


def step(operation: str, **parameters: object) -> TransformationDefinition:
    return TransformationDefinition.model_validate(
        {"operation": operation, "variable": "gdp", "parameters": parameters}
    )


def test_difference_lag_and_percent_change_have_explicit_leading_nulls() -> None:
    difference = apply_transformations(frame(), (step("difference", periods=1),), variable="gdp")
    assert difference["value"].to_list() == [
        None,
        Decimal("10.0000000000"),
        Decimal("11.0000000000"),
    ]

    lagged = apply_transformations(frame(), (step("lag", periods=2),), variable="gdp")
    assert lagged["value"].to_list() == [None, None, Decimal("100.0000000000")]

    changed = apply_transformations(frame(), (step("percent_change", periods=1),), variable="gdp")
    assert changed["value"].to_list() == [
        None,
        Decimal("10.0000000000"),
        Decimal("10.0000000000"),
    ]


def test_scale_is_decimal_safe_and_steps_are_ordered() -> None:
    transformed = apply_transformations(
        frame(),
        (step("scale", factor=2), step("difference", periods=1)),
        variable="gdp",
    )
    assert transformed["value"].to_list() == [
        None,
        Decimal("20.0000000000"),
        Decimal("22.0000000000"),
    ]
