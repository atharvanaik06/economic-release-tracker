"""Tests for bounded shared provider HTTP behavior."""

from collections.abc import Callable

import httpx
import pytest

from research_data_builder.providers.errors import ProviderRequestError, ProviderResponseError
from research_data_builder.providers.http import JsonHttpClient, RetryPolicy


def sequential_transport(
    responses: list[httpx.Response | Exception],
) -> httpx.MockTransport:
    """Return each configured result once, preserving request order."""
    remaining = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        result = next(remaining)
        if isinstance(result, Exception):
            raise result
        result.request = request
        return result

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_http_client_retries_transient_status_and_honors_capped_retry_after() -> None:
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    transport = sequential_transport(
        [
            httpx.Response(429, headers={"Retry-After": "20"}),
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with httpx.AsyncClient(transport=transport, base_url="https://provider.test") as client:
        http = JsonHttpClient(
            "test",
            client,
            retry_policy=RetryPolicy(
                max_attempts=3,
                initial_backoff_seconds=0.25,
                maximum_backoff_seconds=2,
            ),
            sleeper=record_sleep,
        )
        result = await http.get_json("/data", params={"page": 1})

    assert result == {"ok": True}
    assert sleeps == [2, 0.5]


@pytest.mark.anyio
async def test_http_client_retries_transport_errors_then_raises_typed_failure() -> None:
    async def no_sleep(_: float) -> None:
        return None

    request = httpx.Request("GET", "https://provider.test/data")
    transport = sequential_transport(
        [httpx.ConnectError("offline", request=request), httpx.ReadTimeout("slow", request=request)]
    )
    async with httpx.AsyncClient(transport=transport, base_url="https://provider.test") as client:
        http = JsonHttpClient(
            "test",
            client,
            retry_policy=RetryPolicy(max_attempts=2),
            sleeper=no_sleep,
        )
        with pytest.raises(ProviderRequestError, match="ReadTimeout"):
            await http.get_json("/data")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (httpx.Response(400, json={"message": "bad"}), ProviderRequestError),
        (httpx.Response(200, text="not-json"), ProviderResponseError),
    ],
)
async def test_http_client_rejects_non_retryable_and_malformed_responses(
    response: httpx.Response,
    expected_error: type[Exception],
) -> None:
    transport = sequential_transport([response])
    async with httpx.AsyncClient(transport=transport, base_url="https://provider.test") as client:
        http = JsonHttpClient("test", client)
        with pytest.raises(expected_error):
            await http.get_json("/data")


@pytest.mark.parametrize(
    "policy_factory",
    [
        lambda: RetryPolicy(max_attempts=0),
        lambda: RetryPolicy(timeout_seconds=0),
        lambda: RetryPolicy(initial_backoff_seconds=-1),
    ],
)
def test_retry_policy_rejects_invalid_values(policy_factory: Callable[[], RetryPolicy]) -> None:
    with pytest.raises(ValueError):
        policy_factory()
