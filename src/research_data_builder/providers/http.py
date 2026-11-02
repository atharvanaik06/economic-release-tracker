"""Shared HTTP reliability policy for provider connectors."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from research_data_builder.providers.errors import (
    ProviderRequestError,
    ProviderResponseError,
)

Sleeper = Callable[[float], Awaitable[None]]
QueryValue = str | int


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry and timeout behavior shared by all connectors."""

    max_attempts: int = 3
    timeout_seconds: float = 15.0
    initial_backoff_seconds: float = 0.25
    maximum_backoff_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.initial_backoff_seconds < 0 or self.maximum_backoff_seconds < 0:
            raise ValueError("backoff values cannot be negative")


class JsonHttpClient:
    """Small JSON client with deterministic, testable provider failure behavior."""

    RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        provider: str,
        client: httpx.AsyncClient,
        *,
        retry_policy: RetryPolicy | None = None,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        self.provider = provider
        self.client = client
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, QueryValue] | None = None,
    ) -> Any:
        """GET and decode JSON, retrying only transient transport and HTTP failures."""
        last_error: httpx.RequestError | None = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                response = await self.client.get(
                    path,
                    params=params,
                    timeout=self.retry_policy.timeout_seconds,
                )
            except httpx.RequestError as error:
                last_error = error
                if attempt == self.retry_policy.max_attempts:
                    break
                await self.sleeper(self._backoff_seconds(attempt, retry_after=None))
                continue

            if response.status_code in self.RETRYABLE_STATUS_CODES:
                if attempt == self.retry_policy.max_attempts:
                    raise ProviderRequestError(
                        self.provider,
                        "transient request failure after retries",
                        status_code=response.status_code,
                    )
                await self.sleeper(
                    self._backoff_seconds(attempt, response.headers.get("Retry-After"))
                )
                continue

            if response.is_error:
                raise ProviderRequestError(
                    self.provider,
                    "provider rejected request",
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except ValueError as error:
                raise ProviderResponseError(
                    f"{self.provider}: provider returned invalid JSON"
                ) from error

        message = "provider could not be reached"
        if last_error is not None:
            message = f"{message} ({type(last_error).__name__})"
        raise ProviderRequestError(self.provider, message) from last_error

    def _backoff_seconds(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                requested_delay = max(0.0, float(retry_after))
                return float(min(requested_delay, self.retry_policy.maximum_backoff_seconds))
            except ValueError:
                pass

        exponential_delay = self.retry_policy.initial_backoff_seconds * (2 ** (attempt - 1))
        return float(min(exponential_delay, self.retry_policy.maximum_backoff_seconds))
