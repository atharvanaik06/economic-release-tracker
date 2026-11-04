"""Tests for explicit and null-safe frequency conversion."""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from research_data_builder.engine.frequency import AggregationMethod, convert_frequency
from research_data_builder.engine.harmonize import HarmonizationError
from research_data_builder.providers import Frequency


def monthly_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "entity": ["CZE", "CZE", "DEU", "DEU"],
            "period": [
                date(2024, 1, 1),
                date(2024, 2, 1),
                date(2024, 1, 1),
                date(2024, 2, 1),
            ],
            "variable": ["value"] * 4,
            "value": [Decimal("1"), Decimal("3"), None, None],
        },
        schema_overrides={"value": pl.Decimal(30, 10)},
    )


def test_frequency_conversion_requires_explicit_aggregation_and_preserves_all_null() -> None:
    with pytest.raises(HarmonizationError, match="requires"):
        convert_frequency(
            monthly_frame(),
            source=Frequency.MONTHLY,
            target=Frequency.ANNUAL,
            method=None,
        )

    annual = convert_frequency(
        monthly_frame(),
        source=Frequency.MONTHLY,
        target=Frequency.ANNUAL,
        method="mean",
    )
    assert annual["period"].to_list() == [date(2024, 1, 1), date(2024, 1, 1)]
    assert annual["value"].to_list() == [Decimal("2.0000000000"), None]


def test_frequency_conversion_rejects_upsampling_and_redundant_aggregation() -> None:
    with pytest.raises(HarmonizationError, match="finer"):
        convert_frequency(
            monthly_frame(),
            source=Frequency.ANNUAL,
            target=Frequency.MONTHLY,
            method="mean",
        )
    with pytest.raises(HarmonizationError, match="unnecessary"):
        convert_frequency(
            monthly_frame(),
            source=Frequency.MONTHLY,
            target=Frequency.MONTHLY,
            method="mean",
        )


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("sum", Decimal("4.0000000000")),
        ("min", Decimal("1.0000000000")),
        ("max", Decimal("3.0000000000")),
        ("last", Decimal("3.0000000000")),
    ],
)
def test_supported_aggregation_methods_are_deterministic(
    method: AggregationMethod,
    expected: Decimal,
) -> None:
    annual = convert_frequency(
        monthly_frame().filter(pl.col("entity") == "CZE"),
        source=Frequency.MONTHLY,
        target=Frequency.ANNUAL,
        method=method,
    )
    assert annual["value"].to_list() == [expected]


def test_frequency_buckets_and_no_op_are_explicit() -> None:
    original = monthly_frame()
    assert convert_frequency(
        original,
        source=Frequency.MONTHLY,
        target=Frequency.MONTHLY,
        method=None,
    ).equals(original)

    quarterly = convert_frequency(
        original,
        source=Frequency.MONTHLY,
        target=Frequency.QUARTERLY,
        method="last",
    )
    assert quarterly["period"].to_list() == [date(2024, 1, 1), date(2024, 1, 1)]

    with pytest.raises(HarmonizationError, match="weekly and daily"):
        convert_frequency(
            pl.DataFrame(
                {
                    "entity": ["CZE"],
                    "period": [date(2024, 1, 1)],
                    "variable": ["x"],
                    "value": [Decimal("1")],
                },
                schema_overrides={"value": pl.Decimal(30, 10)},
            ),
            source=Frequency.DAILY,
            target=Frequency.WEEKLY,
            method="last",
        )
