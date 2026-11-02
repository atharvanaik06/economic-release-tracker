# Provider Connectors

Phase 3 provides one asynchronous contract for public-data discovery and retrieval. Recipe and
build code can work with `Indicator`, `Entity`, `ObservationQuery`, and `Observation` without
knowing the original provider response shape.

## Implemented capabilities

| Capability | FRED | World Bank |
|---|---:|---:|
| Indicator text search | Yes | Yes |
| Exact indicator metadata | Yes | Yes |
| Observation retrieval | Yes | Yes |
| Date filtering | Yes | Yes, by inclusive year range |
| Geographic entity catalog | No | Yes |
| Multi-entity request | No | Yes |
| Pagination | Yes | Yes |
| Missing-value normalization | `.` to null | `null` to null |
| Decimal-safe values | Yes | Yes |
| Historical vintage selection | Not yet | No |

FRED series often describe one already-scoped geography, so the connector rejects a separate
entity filter rather than pretending it is supported. ALFRED point-in-time vintage selection is a
later extension. The current World Bank connector treats the supported Indicators API as annual;
frequency conversion is not guessed.

## Reliability policy

Every connector uses the same HTTP policy:

- request timeouts are explicit;
- attempts are bounded;
- transport failures, HTTP 429, and HTTP 500/502/503/504 are retryable;
- `Retry-After` is honored up to the configured maximum backoff;
- ordinary 4xx responses fail immediately;
- malformed successful responses become typed provider-response failures;
- response bodies and FRED credentials are not copied into exceptions or INFO logs.

## Normalized objects

An `Indicator` contains provider identity, provider indicator ID, title, description, unit,
canonical frequency, source URL, and preserved provider metadata.

An `Observation` contains provider identity, indicator ID, optional entity, canonical period,
`Decimal` value or explicit missing state, unit, frequency, and useful source metadata.

This is an intentionally small contract. Provider-only fields remain in `provider_metadata` until
the product has a demonstrated reason to promote them.

## FRED configuration

Create a FRED API key and store it only in the local `.env` file:

```text
RESEARCH_DATA_FRED_API_KEY=your-local-key
```

The checked-in `.env.example` contains no credential. In production the key will come from a
secret manager.

## Catalog refresh

`ProviderCatalogService` searches a bounded provider catalog and writes normalized entries through
`SeriesRepository.upsert`. A canonical metadata document is hashed with SHA-256.

```text
new identity       -> create series
known + new hash   -> update metadata
known + same hash  -> no database write
```

The caller owns the database transaction. Provider requests happen before or between short
database operations; connector code never commits a transaction.

## Current boundary

Phase 3 is an internal connector and service layer. Public provider routes are still part of the
planned API surface, not implemented endpoints. Phase 4 will use these connectors when resolving
versioned recipe inputs and build plans.

All connector tests use `httpx.MockTransport` fixtures. CI therefore tests pagination, missing
values, rate limits, retries, malformed responses, filters, and catalog idempotency without relying
on external network availability or live data that can change unexpectedly.
