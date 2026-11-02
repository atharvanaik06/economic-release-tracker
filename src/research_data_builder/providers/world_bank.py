"""World Bank connector implementing the provider-neutral data contract."""

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
from research_data_builder.providers.errors import IndicatorNotFoundError, ProviderResponseError
from research_data_builder.providers.http import JsonHttpClient, RetryPolicy


class WorldBankConnector:
    """Retrieve and normalize World Bank indicators, entities, and observations."""

    provider = DataProvider.WORLD_BANK
    capabilities = ProviderCapabilities(
        indicator_search=True,
        entity_catalog=True,
        date_filtering=True,
        geographic_filtering=True,
        revisions=False,
    )
    page_size = 1_000

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.http = JsonHttpClient(self.provider.value, client, retry_policy=retry_policy)

    async def search_indicators(self, query: str, *, limit: int = 20) -> list[Indicator]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            raise ValueError("query cannot be empty")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")

        matches: list[Indicator] = []
        page = 1
        while True:
            metadata, rows = await self._get_page("/indicator", page=page)
            for row in rows:
                searchable_text = " ".join(
                    (
                        str(row.get("id", "")),
                        str(row.get("name", "")),
                        str(row.get("sourceNote", "")),
                    )
                ).casefold()
                if normalized_query in searchable_text:
                    matches.append(self._parse_indicator(row))
                    if len(matches) == limit:
                        return matches
            if page >= self._total_pages(metadata):
                return matches
            page += 1

    async def get_indicator(self, indicator_id: str) -> Indicator:
        normalized_id = self._path_identifier(indicator_id, "indicator_id")
        _, rows = await self._get_page(f"/indicator/{normalized_id}", page=1)
        if not rows:
            raise IndicatorNotFoundError(f"World Bank indicator not found: {indicator_id}")
        return self._parse_indicator(rows[0])

    async def list_entities(self) -> list[Entity]:
        rows = await self._all_pages("/country")
        entities = [self._parse_entity(row) for row in rows]
        return sorted(entities, key=lambda entity: entity.provider_entity_id)

    async def get_observations(self, query: ObservationQuery) -> list[Observation]:
        indicator = await self.get_indicator(query.indicator_id)
        entity_path = "all"
        if query.entity_ids:
            entity_path = ";".join(
                self._path_identifier(entity_id, "entity_id") for entity_id in query.entity_ids
            )

        extra_params: dict[str, str | int] = {}
        if query.start_date is not None or query.end_date is not None:
            start_year = query.start_date.year if query.start_date else 1960
            end_year = query.end_date.year if query.end_date else date.today().year
            extra_params["date"] = f"{start_year}:{end_year}"

        rows = await self._all_pages(
            f"/country/{entity_path}/indicator/{indicator.provider_indicator_id}",
            extra_params=extra_params,
        )
        observations = [self._parse_observation(row, indicator) for row in rows]
        return sorted(observations, key=lambda item: (item.entity_id or "", item.period))

    async def _all_pages(
        self,
        path: str,
        *,
        extra_params: Mapping[str, str | int] | None = None,
    ) -> list[Mapping[str, Any]]:
        page = 1
        all_rows: list[Mapping[str, Any]] = []
        while True:
            metadata, rows = await self._get_page(path, page=page, extra_params=extra_params)
            all_rows.extend(rows)
            if page >= self._total_pages(metadata):
                return all_rows
            page += 1

    async def _get_page(
        self,
        path: str,
        *,
        page: int,
        extra_params: Mapping[str, str | int] | None = None,
    ) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
        params: dict[str, str | int] = {
            "format": "json",
            "page": page,
            "per_page": self.page_size,
        }
        if extra_params:
            params.update(extra_params)
        payload = await self.http.get_json(path, params=params)
        return self._unpack_page(payload)

    def _parse_indicator(self, row: Mapping[str, Any]) -> Indicator:
        indicator_id = self._required_text(row, "id")
        return Indicator(
            provider=self.provider,
            provider_indicator_id=indicator_id,
            title=self._required_text(row, "name"),
            description=self._optional_text(row.get("sourceNote")),
            unit=self._optional_text(row.get("unit")),
            frequency=Frequency.ANNUAL,
            source_url=f"https://data.worldbank.org/indicator/{indicator_id}",
            provider_metadata=dict(row),
        )

    def _parse_entity(self, row: Mapping[str, Any]) -> Entity:
        region = self._nested_text(row.get("region"), "value")
        income_level = self._nested_text(row.get("incomeLevel"), "value")
        return Entity(
            provider=self.provider,
            provider_entity_id=self._required_text(row, "id"),
            name=self._required_text(row, "name"),
            iso2_code=self._optional_text(row.get("iso2Code")),
            iso3_code=self._optional_text(row.get("id")),
            region=region,
            income_level=income_level,
            provider_metadata=dict(row),
        )

    def _parse_observation(
        self,
        row: Mapping[str, Any],
        indicator: Indicator,
    ) -> Observation:
        raw_value = row.get("value")
        value: Decimal | None
        if raw_value is None or raw_value == "":
            value = None
        else:
            try:
                value = Decimal(str(raw_value))
            except InvalidOperation as error:
                raise ProviderResponseError(
                    f"World Bank returned an invalid decimal for {indicator.provider_indicator_id}"
                ) from error

        entity_id = self._optional_text(row.get("countryiso3code"))
        if entity_id is None:
            entity_id = self._nested_text(row.get("country"), "id")

        return Observation(
            provider=self.provider,
            indicator_id=indicator.provider_indicator_id,
            entity_id=entity_id,
            period=self._parse_period(self._required_text(row, "date")),
            value=value,
            is_missing=value is None,
            unit=indicator.unit,
            frequency=indicator.frequency,
            provider_metadata={
                "country_name": self._nested_text(row.get("country"), "value"),
                "decimal": row.get("decimal"),
                "observation_status": row.get("obs_status"),
            },
        )

    @staticmethod
    def _unpack_page(payload: Any) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
        if not isinstance(payload, list) or len(payload) != 2:
            raise ProviderResponseError("World Bank response is not a two-part page")
        metadata, rows = payload
        if not isinstance(metadata, dict) or not isinstance(rows, list):
            raise ProviderResponseError("World Bank response has invalid page metadata or rows")
        if not all(isinstance(row, dict) for row in rows):
            raise ProviderResponseError("World Bank response contains invalid rows")
        return metadata, cast(list[Mapping[str, Any]], rows)

    @staticmethod
    def _total_pages(metadata: Mapping[str, Any]) -> int:
        try:
            pages = int(metadata["pages"])
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderResponseError("World Bank response has invalid page count") from error
        if pages < 1:
            raise ProviderResponseError("World Bank response has invalid page count")
        return pages

    @staticmethod
    def _parse_period(value: str) -> date:
        if len(value) == 4 and value.isdigit():
            return date(int(value), 1, 1)
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ProviderResponseError(
                "World Bank returned an invalid observation period"
            ) from error

    @staticmethod
    def _path_identifier(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized or any(character in normalized for character in "/?#;"):
            raise ValueError(f"{field_name} is not a valid provider identifier")
        return normalized

    @staticmethod
    def _required_text(row: Mapping[str, Any], field_name: str) -> str:
        value = row.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ProviderResponseError(f"World Bank response has invalid field: {field_name}")
        return value.strip()

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @classmethod
    def _nested_text(cls, value: Any, field_name: str) -> str | None:
        if not isinstance(value, dict):
            return None
        return cls._optional_text(value.get(field_name))
