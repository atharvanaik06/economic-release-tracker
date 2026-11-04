"""Canonical entity, period, and long-form observation harmonization."""

import re
from datetime import date

import polars as pl

from research_data_builder.providers.domain import Frequency, Observation

ENTITY_MAPPING_VERSION = "2026-11-04.v1"

# Explicit aliases accepted at the boundary. Canonical ISO3-like provider codes pass through.
ENTITY_ALIASES: dict[str, str] = {
    "CZ": "CZE",
    "DE": "DEU",
    "FR": "FRA",
    "PL": "POL",
    "UK": "GBR",
    "US": "USA",
}


class HarmonizationError(ValueError):
    """Source data cannot be represented safely in the canonical schema."""


def canonical_entity(entity_id: str | None) -> str | None:
    """Resolve a supported alias or validate a canonical three-character code."""
    if entity_id is None:
        return None
    normalized = entity_id.strip().upper()
    if normalized in ENTITY_ALIASES:
        return ENTITY_ALIASES[normalized]
    if not re.fullmatch(r"[A-Z0-9]{3}", normalized):
        raise HarmonizationError(f"unsupported entity identifier: {entity_id}")
    return normalized


def canonical_period(value: date, frequency: Frequency) -> date:
    """Represent a provider period by its deterministic period-start date."""
    if frequency is Frequency.ANNUAL:
        return date(value.year, 1, 1)
    if frequency is Frequency.SEMIANNUAL:
        return date(value.year, 1 if value.month <= 6 else 7, 1)
    if frequency is Frequency.QUARTERLY:
        quarter_month = ((value.month - 1) // 3) * 3 + 1
        return date(value.year, quarter_month, 1)
    if frequency is Frequency.MONTHLY:
        return date(value.year, value.month, 1)
    if frequency in {Frequency.DAILY, Frequency.WEEKLY, Frequency.IRREGULAR}:
        return value
    raise HarmonizationError("source frequency must be known before harmonization")


def observations_to_long(
    observations: list[Observation],
    *,
    output_name: str,
) -> pl.DataFrame:
    """Convert normalized provider observations into one typed tidy table."""
    rows = [
        {
            "entity": canonical_entity(observation.entity_id),
            "period": canonical_period(observation.period, observation.frequency),
            "variable": output_name,
            "value": observation.value,
        }
        for observation in observations
    ]
    frame = pl.DataFrame(
        rows,
        schema={
            "entity": pl.String,
            "period": pl.Date,
            "variable": pl.String,
            "value": pl.Decimal(precision=30, scale=10),
        },
    ).sort(["entity", "period"], nulls_last=False)

    duplicate_count = (
        frame.group_by(["entity", "period", "variable"]).len().filter(pl.col("len") > 1).height
    )
    if duplicate_count:
        raise HarmonizationError(
            f"{output_name} contains {duplicate_count} duplicate entity-period keys"
        )
    return frame
