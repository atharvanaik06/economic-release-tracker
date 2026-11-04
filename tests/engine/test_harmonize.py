"""Tests for canonical entity, period, and long-form staging."""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from research_data_builder.engine.harmonize import (
    ENTITY_MAPPING_VERSION,
    HarmonizationError,
    canonical_entity,
    canonical_period,
    observations_to_long,
)
from research_data_builder.providers import DataProvider, Frequency, Observation


def observation(
    entity: str | None,
    period: date,
    value: Decimal | None,
    *,
    frequency: Frequency = Frequency.ANNUAL,
) -> Observation:
    return Observation(
        provider=DataProvider.WORLD_BANK,
        indicator_id="TEST",
        entity_id=entity,
        period=period,
        value=value,
        is_missing=value is None,
        frequency=frequency,
    )


def test_entity_mapping_is_explicit_and_versioned() -> None:
    assert ENTITY_MAPPING_VERSION == "2026-11-04.v1"
    assert canonical_entity("cz") == "CZE"
    assert canonical_entity("WLD") == "WLD"
    assert canonical_entity(None) is None
    with pytest.raises(HarmonizationError, match="unsupported"):
        canonical_entity("Czech Republic")


def test_periods_use_canonical_period_starts() -> None:
    assert canonical_period(date(2024, 11, 20), Frequency.ANNUAL) == date(2024, 1, 1)
    assert canonical_period(date(2024, 11, 20), Frequency.QUARTERLY) == date(2024, 10, 1)
    assert canonical_period(date(2024, 11, 20), Frequency.MONTHLY) == date(2024, 11, 1)
    assert canonical_period(date(2024, 11, 20), Frequency.SEMIANNUAL) == date(2024, 7, 1)
    with pytest.raises(HarmonizationError, match="frequency"):
        canonical_period(date(2024, 1, 1), Frequency.UNKNOWN)


def test_observations_become_sorted_decimal_safe_long_form() -> None:
    frame = observations_to_long(
        [
            observation("DE", date(2024, 12, 31), None),
            observation("CZ", date(2024, 12, 31), Decimal("2.1234567890")),
        ],
        output_name="gdp_growth",
    )

    assert frame.columns == ["entity", "period", "variable", "value"]
    assert frame["entity"].to_list() == ["CZE", "DEU"]
    assert frame["value"].dtype == pl.Decimal(precision=30, scale=10)
    assert frame["value"].to_list() == [Decimal("2.1234567890"), None]


def test_duplicate_entity_period_keys_are_rejected() -> None:
    duplicate = observation("CZE", date(2024, 1, 1), Decimal("1"))
    with pytest.raises(HarmonizationError, match="duplicate"):
        observations_to_long([duplicate, duplicate], output_name="gdp")
