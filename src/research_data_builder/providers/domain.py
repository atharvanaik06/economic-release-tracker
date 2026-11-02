"""Provider-neutral domain objects returned by every connector."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any


class DataProvider(StrEnum):
    """Supported public data providers."""

    FRED = "fred"
    WORLD_BANK = "world_bank"


class Frequency(StrEnum):
    """Canonical observation frequencies understood by the build system."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"
    IRREGULAR = "irregular"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Features a connector can provide without provider-specific branching."""

    indicator_search: bool
    entity_catalog: bool
    date_filtering: bool
    geographic_filtering: bool
    revisions: bool = False


@dataclass(frozen=True, slots=True)
class Indicator:
    """Normalized metadata for one provider indicator or series."""

    provider: DataProvider
    provider_indicator_id: str
    title: str
    description: str | None
    unit: str | None
    frequency: Frequency
    source_url: str
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Entity:
    """Normalized geographic entity exposed by a provider."""

    provider: DataProvider
    provider_entity_id: str
    name: str
    iso2_code: str | None = None
    iso3_code: str | None = None
    region: str | None = None
    income_level: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ObservationQuery:
    """Provider-neutral request for a bounded indicator time series."""

    indicator_id: str
    entity_ids: tuple[str, ...] = ()
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if not self.indicator_id.strip():
            raise ValueError("indicator_id cannot be empty")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        if any(not entity_id.strip() for entity_id in self.entity_ids):
            raise ValueError("entity_ids cannot contain empty values")


@dataclass(frozen=True, slots=True)
class Observation:
    """One normalized value returned by a public data provider."""

    provider: DataProvider
    indicator_id: str
    period: date
    value: Decimal | None
    is_missing: bool
    entity_id: str | None = None
    unit: str | None = None
    frequency: Frequency = Frequency.UNKNOWN
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_missing != (self.value is None):
            raise ValueError("is_missing must match whether value is None")
