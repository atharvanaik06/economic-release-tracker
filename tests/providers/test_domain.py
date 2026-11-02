"""Tests for provider-neutral domain validation."""

from datetime import date
from decimal import Decimal

import pytest

from research_data_builder.providers import (
    DataProvider,
    Observation,
    ObservationQuery,
)


def test_observation_query_validates_dates_and_identifiers() -> None:
    with pytest.raises(ValueError, match="indicator_id"):
        ObservationQuery(indicator_id=" ")

    with pytest.raises(ValueError, match="start_date"):
        ObservationQuery(
            indicator_id="GDP",
            start_date=date(2025, 1, 1),
            end_date=date(2024, 1, 1),
        )

    with pytest.raises(ValueError, match="entity_ids"):
        ObservationQuery(indicator_id="GDP", entity_ids=("US", ""))


def test_observation_requires_missing_flag_to_match_value() -> None:
    with pytest.raises(ValueError, match="is_missing"):
        Observation(
            provider=DataProvider.FRED,
            indicator_id="GDP",
            period=date(2024, 1, 1),
            value=Decimal("1"),
            is_missing=True,
        )
