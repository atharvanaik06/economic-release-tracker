# Product Requirements

## 1. Product summary

The Economic Release Tracker is a backend service for researchers, analysts, and developers who need to know how published economic data changes over time.

The product adds value on top of FRED by storing successive versions, calculating differences, and creating citable point-in-time snapshots. It is not intended to be a general replacement for FRED.

## 2. Problem, simplified

Imagine that GDP for Q2 is first reported as `1.8%`. A month later it is changed to `1.6%` when Q3 is published.

A normal data request usually shows only the newest numbers. Our service keeps both versions and reports:

```text
New value:     Q3 = 2.1%
Revised value: Q2 = 1.8% -> 1.6%
```

That allows a researcher to prove which values were used in an older analysis and allows an analyst to see only what changed.

## 3. Users and their needs

### Primary: economics students and researchers

- Reconstruct the data available on a historical date.
- Export the exact dataset used in an analysis.
- Cite metadata and a checksum so the dataset can be verified.

### Secondary: economic and financial analysts

- Track a small set of important series.
- See new observations and revisions without comparing tables manually.

### Later: application developers

- Consume consistent change events.
- Receive webhook notifications when watched series change.

## 4. MVP user stories

1. As a user, I can list the economic series tracked by the service.
2. As an operator, I can trigger synchronization for a configured series.
3. As a user, I can see which observations were new or revised during a synchronization.
4. As a user, I can inspect the complete revision history for a period.
5. As a researcher, I can request the data that was known as of a given date.
6. As a researcher, I can create an immutable snapshot containing one or more series.
7. As a researcher, I can export a snapshot as JSON or CSV with source metadata and a checksum.

## 5. MVP functional requirements

### FR-1: Series catalog

- Store provider ID, title, units, frequency, source, and last synchronization time.
- Support a small configured list of FRED series such as CPI, unemployment, and the federal funds rate.
- Validate unknown or inactive series IDs.

### FR-2: Provider ingestion

- Fetch observations and relevant metadata from FRED.
- Use explicit request timeouts and bounded retries.
- Record the provider retrieval time.
- Convert provider responses into internal domain objects before persistence.
- Never commit a real API key; read it from the environment.

### FR-3: Version storage

- Preserve every materially different value seen for a series and period.
- Store when a version was first observed by this system.
- Store the provider's vintage/realtime dates when available.
- Never overwrite an older observation version.
- Represent missing values explicitly instead of converting them to zero.

### FR-4: Synchronization and change detection

- Compare a provider response with the latest stored state.
- Classify each result as `new`, `revised`, `unchanged`, or `missing`.
- Calculate the signed and absolute revision amount when numeric values change.
- Save the observation versions and the synchronization result atomically.
- Reprocessing the same provider response must not create duplicates.

### FR-5: Change and revision API

- List synchronization runs for a series.
- Return the new and revised observations from a run.
- Return all known versions for a given series and period.
- Use pagination for collection endpoints.

Proposed MVP routes:

```text
GET  /health
GET  /series
GET  /series/{series_id}
POST /series/{series_id}/sync
GET  /series/{series_id}/sync-runs
GET  /sync-runs/{run_id}/changes
GET  /series/{series_id}/revisions?period=YYYY-MM-DD
```

### FR-6: Point-in-time queries

- For every requested period, return the latest version known on or before `as_of`.
- Exclude values first observed after `as_of`.
- Include the effective vintage and observation timestamps in the response.

### FR-7: Reproducible snapshots

- Create a snapshot from one or more series and an `as_of` timestamp.
- Freeze the selected observation-version IDs so later revisions cannot alter the snapshot.
- Include series metadata, units, frequency, source, creation time, and selection criteria.
- Generate a deterministic SHA-256 checksum from canonical snapshot content.
- Export the snapshot as JSON and CSV.

Proposed routes:

```text
POST /snapshots
GET  /snapshots/{snapshot_id}
GET  /snapshots/{snapshot_id}/export?format=json
GET  /snapshots/{snapshot_id}/export?format=csv
```

## 6. Data model, conceptually

- `series`: one record per tracked economic series.
- `sync_runs`: one record per ingestion attempt, including status and counts.
- `observation_versions`: append-only values for a series and economic period.
- `changes`: the new/revised/missing classifications produced by a sync run.
- `snapshots`: immutable snapshot metadata and checksum.
- `snapshot_items`: the exact observation versions included in a snapshot.

Exact tables and constraints will be designed before the first migration.

## 7. Non-functional requirements

### Correctness

- Use decimal-safe numeric handling; do not rely on binary floating point for comparisons.
- Make synchronization idempotent.
- Use database constraints to prevent duplicate versions.
- Store service timestamps in UTC and preserve provider vintage dates separately.

### Reliability

- A failed provider call must not create a successful or partial sync result.
- Database changes for one synchronization must be transactional.
- Errors must be structured and logged without secrets.

### Performance

- Optimize for correctness first and a catalog of tens, not thousands, of series.
- Paginated API requests should remain responsive with at least one million observation-version rows.
- Add indexes based on measured query patterns.

### Security

- Keep API keys and database credentials in environment variables or a secret manager.
- Validate provider IDs, dates, pagination, and export formats.
- Do not expose internal stack traces through the API.
- Authentication is not required for the local MVP, but mutation endpoints must be easy to protect later.

### Quality and operations

- Unit-test comparison, point-in-time selection, and checksum logic.
- Integration-test database constraints, transactions, and API endpoints.
- Use migrations for every schema change.
- Provide local startup instructions and sample environment configuration.
- CI must run formatting, linting, type checking, and tests.

## 8. MVP acceptance criteria

The MVP is complete when a reviewer can:

1. start the API and PostgreSQL locally from documented commands;
2. synchronize at least three configured FRED series;
3. repeat a synchronization without duplicate records;
4. run a fixture-based demo that produces both a new observation and a revision;
5. inspect the revision through the REST API;
6. query what was known at a historical timestamp;
7. create and export a snapshot;
8. regenerate the same checksum from the exported canonical data; and
9. run the full automated test suite and CI successfully.

The fixture-based demo is required because real FRED data may not revise during a live project demonstration.

## 9. Out of scope for the MVP

- World Bank, BEA, or other providers.
- User accounts and multi-tenant permissions.
- User-created watchlists.
- Email and webhook delivery.
- Scheduled cloud ingestion.
- AWS infrastructure.
- A browser frontend.
- Economic forecasting, trading signals, or revision analytics.
- High-frequency market data.

These are candidates for later phases, not promises for the first release.

## 10. Product success measures

- Duplicate observation versions created by an identical sync: zero.
- Fixture changes correctly classified: 100% of tested cases.
- Snapshot checksum changes when and only when canonical snapshot content changes.
- A new developer can run the documented demo locally without reading the implementation.

