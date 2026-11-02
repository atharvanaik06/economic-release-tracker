"""FRED connector implementing the provider-neutral data contract."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx

from research_data_builder.providers.domain import (
    DataProvider,
    Entity,
    Frequency,
    Indicator,
    Observation,
    ObservationQuery,
    ProviderCapabilities,
)
from research_data_builder.providers.errors import (
    IndicatorNotFoundError,
    ProviderConfigurationError,
    ProviderResponseError,
    UnsupportedProviderOperationError,
)
from research_data_builder.providers.http import JsonHttpClient, RetryPolicy


class FredConnector:
    """Retrieve and normalize indicator metadata and observations from FRED."""

    provider = DataProvider.FRED
    capabilities = ProviderCapabilities(
        indicator_search=True,
        entity_catalog=False,
        date_filtering=True,
        geographic_filtering=False,
        revisions=False,
    )
    page_size = 1_000

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not api_key.strip():
            raise ProviderConfigurationError("FRED requires a non-empty API key")
        self.api_key = api_key
        self.http = JsonHttpClient(self.provider.value, client, retry_policy=retry_policy)

    async def search_indicators(self, query: str, *, limit: int = 20) -> list[Indicator]:
        if not query.strip():
            raise ValueError("query cannot be empty")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")

        payload = await self.http.get_json(
            "/series/search",
            params=self._params(search_text=query, limit=limit),
        )
        rows = self._list_field(payload, "seriess")
        return [self._parse_indicator(row) for row in rows]

    async def get_indicator(self, indicator_id: str) -> Indicator:
        if not indicator_id.strip():
            raise ValueError("indicator_id cannot be empty")

        payload = await self.http.get_json(
            "/series",
            params=self._params(series_id=indicator_id),
        )
        rows = self._list_field(payload, "seriess")
        if not rows:
            raise IndicatorNotFoundError(f"FRED indicator not found: {indicator_id}")
        return self._parse_indicator(rows[0])

    async def list_entities(self) -> list[Entity]:
        raise UnsupportedProviderOperationError("FRED does not expose a geographic entity catalog")

    async def get_observations(self, query: ObservationQuery) -> list[Observation]:
        if query.entity_ids:
            raise UnsupportedProviderOperationError(
                "FRED observations cannot be filtered by geographic entity"
            )

        indicator = await self.get_indicator(query.indicator_id)
        offset = 0
        observations: list[Observation] = []

        while True:
            request_params = self._params(
                series_id=query.indicator_id,
                limit=self.page_size,
                offset=offset,
                sort_order="asc",
            )
            if query.start_date is not None:
                request_params["observation_start"] = query.start_date.isoformat()
            if query.end_date is not None:
                request_params["observation_end"] = query.end_date.isoformat()

            payload = await self.http.get_json("/series/observations", params=request_params)
            rows = self._list_field(payload, "observations")
            observations.extend(self._parse_observation(row, indicator) for row in rows)

            total_count = self._integer_field(payload, "count")
            offset += len(rows)
            if not rows or offset >= total_count:
                break

        return sorted(observations, key=lambda item: item.period)

    def _params(self, **values: str | int) -> dict[str, str | int]:
        return {"api_key": self.api_key, "file_type": "json", **values}

    def _parse_indicator(self, row: Mapping[str, Any]) -> Indicator:
        indicator_id = self._required_text(row, "id")
        return Indicator(
            provider=self.provider,
            provider_indicator_id=indicator_id,
            title=self._required_text(row, "title"),
            description=self._optional_text(row.get("notes")),
            unit=self._optional_text(row.get("units")),
            frequency=self._normalize_frequency(row),
            source_url=f"https://fred.stlouisfed.org/series/{indicator_id}",
            provider_metadata=dict(row),
        )

    def _parse_observation(
        self,
        row: Mapping[str, Any],
        indicator: Indicator,
    ) -> Observation:
        raw_value = self._required_text(row, "value")
        value: Decimal | None
        if raw_value in {".", "", "NA", "N/A"}:
            value = None
        else:
            try:
                value = Decimal(raw_value)
            except InvalidOperation as error:
                raise ProviderResponseError(
                    f"FRED returned an invalid decimal for {indicator.provider_indicator_id}"
                ) from error

        return Observation(
            provider=self.provider,
            indicator_id=indicator.provider_indicator_id,
            period=self._parse_date(self._required_text(row, "date"), "date"),
            value=value,
            is_missing=value is None,
            unit=indicator.unit,
            frequency=indicator.frequency,
            provider_metadata={
                "realtime_start": self._optional_text(row.get("realtime_start")),
                "realtime_end": self._optional_text(row.get("realtime_end")),
            },
        )

    @staticmethod
    def _normalize_frequency(row: Mapping[str, Any]) -> Frequency:
        short_name = str(row.get("frequency_short", "")).upper()
        short_mapping = {
            "D": Frequency.DAILY,
            "W": Frequency.WEEKLY,
            "BW": Frequency.WEEKLY,
            "M": Frequency.MONTHLY,
            "Q": Frequency.QUARTERLY,
            "SA": Frequency.SEMIANNUAL,
            "A": Frequency.ANNUAL,
        }
        if short_name in short_mapping:
            return short_mapping[short_name]

        name = str(row.get("frequency", "")).casefold()
        for prefix, frequency in (
            ("daily", Frequency.DAILY),
            ("weekly", Frequency.WEEKLY),
            ("monthly", Frequency.MONTHLY),
            ("quarterly", Frequency.QUARTERLY),
            ("semiannual", Frequency.SEMIANNUAL),
            ("annual", Frequency.ANNUAL),
        ):
            if name.startswith(prefix):
                return frequency
        return Frequency.UNKNOWN

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ProviderResponseError(f"FRED returned an invalid {field_name}") from error

    @classmethod
    def _list_field(cls, payload: Any, field_name: str) -> list[Mapping[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get(field_name), list):
            raise ProviderResponseError(f"FRED response is missing list field: {field_name}")
        rows = payload[field_name]
        if not all(isinstance(row, dict) for row in rows):
            raise ProviderResponseError(f"FRED field contains invalid rows: {field_name}")
        return cast(list[Mapping[str, Any]], rows)

    @staticmethod
    def _integer_field(payload: Any, field_name: str) -> int:
        if not isinstance(payload, dict):
            raise ProviderResponseError("FRED returned a non-object response")
        try:
            return int(payload[field_name])
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderResponseError(f"FRED response has invalid field: {field_name}") from error

    @staticmethod
    def _required_text(row: Mapping[str, Any], field_name: str) -> str:
        value = row.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ProviderResponseError(f"FRED response has invalid field: {field_name}")
        return value.strip()

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None
