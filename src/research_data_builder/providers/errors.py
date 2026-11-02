"""Typed failures raised by provider connectors."""


class ProviderError(Exception):
    """Base class for expected provider failures."""


class ProviderConfigurationError(ProviderError):
    """A connector is missing required local configuration."""


class ProviderRequestError(ProviderError):
    """A provider request failed after applying retry policy."""

    def __init__(self, provider: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status_code = status_code


class ProviderResponseError(ProviderError):
    """A provider returned a successful but malformed response."""


class IndicatorNotFoundError(ProviderError):
    """A requested indicator does not exist at the provider."""


class UnsupportedProviderOperationError(ProviderError):
    """A caller requested a capability the connector does not support."""
