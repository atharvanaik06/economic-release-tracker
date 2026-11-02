# MacroMonitor Product Requirements

## 1. Product summary

MacroMonitor monitors economic indicators selected by users. It retrieves official data, compares each release with previously stored versions, records exactly what changed, and notifies subscribed applications through reliable webhooks.

It is not a replacement for FRED. Its value is the workflow FRED does not conveniently provide:

- continuously monitor selected series;
- detect new and revised observations;
- preserve an audit history;
- deliver structured change events;
- retry and inspect failed notifications.

## 2. Problem, simplified

Economic values change after publication:

```text
Previously stored data       Latest provider response
August:    324.1             August:    324.0  -> revised
September: 325.3             September: 325.5  -> revised
                             October:   326.4  -> new
```

Without MacroMonitor, an analyst must repeatedly inspect provider pages or compare downloads manually. With MacroMonitor, the user selects the series once and receives a structured event whenever something meaningful changes.

## 3. Target users

### Primary: analysts and data teams

- Monitor important economic indicators in one place.
- See only the observations that changed.
- Retain an auditable release and revision history.

### Secondary: application developers

- Subscribe an application to machine-readable economic change events.
- Receive signed webhook payloads.
- Inspect delivery attempts and replay failed deliveries.

### Later: researchers and quantitative users

- Analyze revision patterns.
- Reconstruct point-in-time datasets.
- Avoid look-ahead bias in historical analysis.

Research functionality is an extension, not the initial product.

## 4. Product MVP user stories

1. As a user, I can browse the economic series supported by the service.
2. As a user, I can create a watchlist and add series to it.
3. As an operator, I can trigger synchronization manually.
4. As the system, I can schedule synchronization without user intervention.
5. As a user, I can see which observations were new, revised, removed, or missing.
6. As a user, I can inspect every stored version of an observation.
7. As a developer, I can subscribe a webhook to a watchlist.
8. As a developer, I can verify that a webhook came from MacroMonitor.
9. As a developer, I can inspect successful and failed delivery attempts.
10. As an operator, I can safely retry a failed job or delivery without creating duplicates.

## 5. Functional requirements

### FR-1: Series catalog

- Store provider ID, title, units, frequency, source, and active status.
- Begin with a small configured set of FRED series such as CPI, unemployment, GDP, and the federal funds rate.
- Refresh provider metadata and detect unit or frequency changes.
- Reject unknown or inactive series IDs.

### FR-2: Watchlists

- Create, read, update, and delete watchlists.
- Add or remove supported series.
- Prevent the same series from appearing twice in one watchlist.
- Associate watchlists with an owner once authentication is enabled.

### FR-3: Provider ingestion

- Retrieve observations and relevant metadata from FRED.
- Use explicit connection and response timeouts.
- Retry only transient failures with bounded exponential backoff and jitter.
- Normalize provider responses into internal domain objects.
- Record retrieval time and provider vintage dates when available.
- Read provider credentials from environment variables or a secret manager.

### FR-4: Version history

- Preserve every materially different value seen for a series and period.
- Never overwrite an older observation version.
- Store decimal values without binary floating-point comparison.
- Represent missing values explicitly rather than converting them to zero.
- Record when the platform first observed each version.
- Prevent duplicate versions with database constraints.

### FR-5: Change detection

- Compare incoming normalized observations with the latest stored state.
- Classify results as `new`, `revised`, `unchanged`, `removed`, or `missing`.
- Calculate signed and absolute revision amounts.
- Detect relevant series metadata changes.
- Create immutable change events for meaningful changes.
- Save the sync run, versions, and events atomically.

### FR-6: Synchronization

- Support manual synchronization for development and administration.
- Support scheduled synchronization for watched active series.
- Avoid overlapping synchronization of the same series.
- Reprocessing identical input must not create duplicate versions or events.
- Record running, successful, and failed sync states with summary counts.

### FR-7: Release and revision API

- List tracked series and metadata.
- List synchronization runs.
- Return changes produced by a sync run.
- Return all known versions for a series and economic period.
- Return a feed of change events relevant to a watchlist.
- Paginate all unbounded collections.

### FR-8: Webhook subscriptions

- Create, list, disable, and delete webhook subscriptions for a watchlist.
- Validate HTTPS callback URLs in production.
- Store webhook secrets securely.
- Allow event-type filtering.
- Send a test event before enabling a subscription.

### FR-9: Webhook delivery

- Deliver the series, period, previous value, new value, revision amount, and event timestamp.
- Sign each request with HMAC using the subscription secret.
- Include an event ID and timestamp for replay protection.
- Deliver asynchronously outside the API request path.
- Retry transient failures using bounded exponential backoff.
- Record every attempt, response status, duration, and sanitized failure category.
- Move exhausted deliveries to a dead-letter state.
- Support safe manual replay without producing a second logical event.

### FR-10: Authentication and ownership

- Authentication is not required for the earliest local engine milestones.
- It is required before public deployment.
- Users may access only their own watchlists, subscriptions, and delivery history.
- Administrative synchronization and replay operations require elevated authorization.

### FR-11: Email notifications

Email may be added after webhook delivery is reliable. It is not required for the product MVP because webhooks demonstrate the asynchronous delivery system without adding email-provider and template complexity.

## 6. Proposed API surface

```text
GET    /health

GET    /api/v1/series
GET    /api/v1/series/{series_id}
POST   /api/v1/series/{series_id}/sync
GET    /api/v1/series/{series_id}/sync-runs
GET    /api/v1/series/{series_id}/revisions?period=YYYY-MM-DD

POST   /api/v1/watchlists
GET    /api/v1/watchlists
GET    /api/v1/watchlists/{watchlist_id}
PATCH  /api/v1/watchlists/{watchlist_id}
DELETE /api/v1/watchlists/{watchlist_id}
PUT    /api/v1/watchlists/{watchlist_id}/series/{series_id}
DELETE /api/v1/watchlists/{watchlist_id}/series/{series_id}
GET    /api/v1/watchlists/{watchlist_id}/events

GET    /api/v1/sync-runs/{run_id}
GET    /api/v1/sync-runs/{run_id}/changes

POST   /api/v1/watchlists/{watchlist_id}/webhooks
GET    /api/v1/watchlists/{watchlist_id}/webhooks
DELETE /api/v1/webhooks/{subscription_id}
POST   /api/v1/webhooks/{subscription_id}/test
GET    /api/v1/webhooks/{subscription_id}/deliveries
POST   /api/v1/deliveries/{delivery_id}/replay
```

## 7. Conceptual data model

- `users`: authenticated owners and roles.
- `series`: provider series metadata.
- `watchlists`: user-owned monitoring groups.
- `watchlist_series`: many-to-many membership.
- `sync_runs`: ingestion attempt, status, timing, and result counts.
- `observation_versions`: append-only values for each series and economic period.
- `change_events`: immutable meaningful differences produced by synchronization.
- `webhook_subscriptions`: callback configuration, filters, status, and secret reference.
- `deliveries`: one logical event delivery per subscription.
- `delivery_attempts`: each HTTP attempt, response, duration, and error category.

Exact columns and constraints will be finalized before the first migration.

## 8. Non-functional requirements

### Correctness and consistency

- Use Python `Decimal` and PostgreSQL `NUMERIC`.
- Write a sync run, its versions, and its change events in one transaction.
- Use database constraints as the final duplicate defense.

### Idempotency

- Repeating provider input creates no duplicate observation versions or events.
- Redelivered queue messages create no duplicate logical deliveries.
- Mutation endpoints support an idempotency key where client retries are expected.

### Reliability

- A provider failure must not produce a partially successful sync.
- FRED outages must not prevent reads of stored history.
- Notification failures must not roll back committed economic data.
- Queued work is retried and eventually dead-lettered for inspection.

### Performance and scale

- Common reads should remain responsive with at least one million observation-version rows.
- Collection endpoints use bounded cursor pagination.
- Workers can scale independently from the API.
- Series synchronization can be distributed while retaining per-series concurrency control.

### Security

- No credentials or webhook secrets are committed to Git.
- Inputs, callback URLs, ranges, and payload sizes are validated.
- Webhook requests are signed and timestamped.
- Logs redact secrets, authorization headers, and sensitive callback details.
- Public deployment includes authentication, authorization, TLS, and rate limiting.

### Observability

- Structured logs carry request, job, sync-run, event, and delivery IDs.
- Metrics cover API latency, provider failures, series staleness, queue age, revision counts, webhook success, retries, and dead letters.
- Alerts focus on sustained user-impacting failures.

### Maintainability and testability

- Provider-specific code remains behind an interface.
- Schema changes use Alembic migrations.
- Core business logic runs against deterministic fixtures without network access.
- CI runs formatting, linting, type checking, unit tests, and integration tests.

## 9. Product MVP acceptance criteria

The local product MVP is complete when a reviewer can:

1. start the API, workers, local queue, and PostgreSQL from documented commands;
2. create a watchlist containing at least three FRED series;
3. execute two fixture releases that produce a new observation and revision;
4. repeat the same ingestion without duplicate versions or events;
5. inspect changes and revision history through the API;
6. subscribe a local test webhook;
7. observe a signed webhook generated from the change event;
8. simulate failure, inspect retries, and see the exhausted delivery state;
9. replay the failed delivery safely;
10. run the complete automated test suite successfully.

The public production release additionally requires authentication, AWS deployment, monitoring, backups, and an operational runbook.

## 10. Out of scope for the product MVP

- Providers other than FRED.
- Email notification.
- Browser frontend or mobile application.
- Immutable research snapshots and CSV datasets.
- Forecasting, trading signals, and backtesting.
- High-frequency market data.
- Complex billing or organization accounts.

These may be added only after the monitoring workflow is complete and reliable.

## 11. Success measures

- Duplicate versions from identical input: zero.
- Duplicate logical notifications during retry testing: zero.
- Fixture classifications correct across all tested cases.
- Successful webhooks delivered once under normal operation.
- Failed webhook attempts visible and safely replayable.
- Stale watched series detectable through metrics.
- A new developer can run the complete local demonstration from the README.
