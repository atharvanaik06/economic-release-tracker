# Phased Build and Commit Plan

## How we will work

Each phase must finish with a demonstrable result, tests, and updated documentation. Commits will represent coherent engineering steps rather than arbitrary file batches.

Good commit messages explain the outcome:

```text
feat: detect revised observations during synchronization
test: cover missing and unchanged observation comparisons
docs: add local FRED synchronization walkthrough
```

We will avoid both extremes: one giant final commit and dozens of meaningless commits such as `changes` or `work in progress`.

## Phase 0: Define the product

**Goal:** agree on the problem, MVP boundary, and delivery sequence.

Deliverables:

- Plain-English project explanation.
- Functional and non-functional requirements.
- MVP acceptance criteria.
- Phased roadmap and commit strategy.

Planned commit:

1. `docs: define MVP requirements and phased delivery plan`

Exit condition: the MVP can be described in one sentence and every deferred feature is visibly out of scope.

## Phase 1: Create a professional service skeleton

**Goal:** boot a small, tested FastAPI application locally.

Deliverables:

- Python project and dependency configuration.
- FastAPI application with `/health`.
- Settings loaded from environment variables.
- Structured logging foundation.
- Formatting, linting, typing, and pytest configuration.
- Dockerfile and local PostgreSQL configuration.
- CI workflow and contributor commands.

Likely commits:

1. `chore: initialize FastAPI project and developer tooling`
2. `feat: add health endpoint and environment settings`
3. `build: add containerized local development stack`
4. `ci: validate formatting types and tests`

Demo: start the stack and receive a healthy API response.

## Phase 2: Design and persist versioned observations

**Goal:** create the database foundation without depending on a live provider.

Deliverables:

- Domain types for series, observations, versions, and sync results.
- SQLAlchemy models and Alembic migrations.
- Constraints that protect append-only history and idempotency.
- Repository layer for version and revision queries.
- Database integration tests.

Likely commits:

1. `feat: model economic series and observation versions`
2. `feat: add initial PostgreSQL schema and constraints`
3. `feat: implement observation repository queries`
4. `test: verify version uniqueness and transactional writes`

Demo: load fixture versions and query a period's full history.

## Phase 3: Integrate FRED behind a provider boundary

**Goal:** retrieve economic data without coupling the rest of the service to FRED response shapes.

Deliverables:

- Provider protocol/interface.
- FRED HTTP client with timeout, retry, and error mapping.
- Normalization of values, missing data, dates, and metadata.
- Fake provider and recorded fixtures for deterministic tests.

Likely commits:

1. `feat: define economic data provider contract`
2. `feat: implement FRED series and observation client`
3. `test: add deterministic FRED response fixtures`

Demo: fetch and normalize one configured series while tests can run offline.

## Phase 4: Build the synchronization and diff engine

**Goal:** turn provider responses into reliable release-change records.

Deliverables:

- Decimal-safe comparison logic.
- `new`, `revised`, `unchanged`, and `missing` classifications.
- Atomic persistence of a sync run, versions, and changes.
- Idempotency and concurrent-run protection.
- Failure states and useful logs.

Likely commits:

1. `feat: classify new revised and missing observations`
2. `feat: persist synchronization runs atomically`
3. `feat: make repeated synchronization idempotent`
4. `test: cover revision and rollback scenarios`

Demo: use fixtures to show a new quarter and a historical revision, then repeat the sync with no duplicates.

## Phase 5: Expose series, runs, and revisions through the API

**Goal:** make the core engine useful to an API client.

Deliverables:

- Series catalog and detail endpoints.
- Manual synchronization endpoint.
- Sync-run change endpoint.
- Period revision-history endpoint.
- Pagination, validation, schemas, and consistent errors.
- API integration tests and OpenAPI examples.

Likely commits:

1. `feat: expose tracked series endpoints`
2. `feat: expose synchronization and change history`
3. `feat: expose period revision history`
4. `test: cover validation pagination and API errors`
5. `docs: add core API walkthrough`

Demo: execute the complete revision workflow using HTTP requests only.

## Phase 6: Add point-in-time data and reproducible snapshots

**Goal:** deliver the project's strongest research-facing feature.

Deliverables:

- Point-in-time observation query.
- Immutable snapshot records referencing exact versions.
- Canonical serialization and SHA-256 checksum.
- JSON and CSV export.
- Snapshot verification command or endpoint.

Likely commits:

1. `feat: query observations available as of a timestamp`
2. `feat: create immutable multi-series snapshots`
3. `feat: export snapshots with deterministic checksums`
4. `test: verify point-in-time and checksum behavior`
5. `docs: add reproducible research example`

Demo: create a historical snapshot, export it, and verify its checksum after newer data has been ingested.

**MVP release point:** tag `v0.1.0` after Phases 1-6 satisfy the acceptance criteria.

## Phase 7: Add users, watchlists, and notifications

**Goal:** evolve the research tool into a multi-user monitoring product.

Deliverables:

- Authentication and authorization.
- User-owned watchlists.
- Webhook subscriptions and signed payloads.
- Background delivery queue, retry policy, and delivery history.
- Optional email notifications.

Example commits:

1. `feat: add authenticated user accounts`
2. `feat: add user-owned series watchlists`
3. `feat: enqueue signed webhook deliveries`
4. `feat: retry and audit failed notifications`

Demo: a watched revision produces a signed webhook and records the delivery attempt.

## Phase 8: Schedule and deploy on AWS

**Goal:** operate the service reliably without manual synchronization.

Deliverables:

- Production container images.
- Infrastructure as code for API, worker, PostgreSQL, queue, storage, and secrets.
- EventBridge schedule.
- CloudWatch logs, metrics, alarms, and dead-letter handling.
- GitHub Actions deployment workflow.
- Runbook and cost notes.

The initial AWS design can use ECS Fargate, RDS PostgreSQL, EventBridge, SQS, ECR, S3, CloudWatch, and Secrets Manager, but it must be reviewed against cost and operational complexity before implementation.

Example commits:

1. `infra: provision network database and secrets`
2. `infra: deploy API and worker services`
3. `infra: schedule ingestion and queue notifications`
4. `ci: automate image build and deployment`
5. `ops: add alarms dashboards and recovery runbook`

Demo: a scheduled cloud ingestion creates a change event and a downloadable snapshot export.

## Phase 9: Optional portfolio extensions

Only start these after the deployed core is reliable:

- Add BEA or World Bank through the existing provider contract.
- Build a small revision timeline dashboard.
- Analyze revision bias and magnitude.
- Backtest with point-in-time rather than revised data.
- Add release-calendar awareness.

Each extension should have a separate issue, measurable user value, and its own commit series.

## Recommended portfolio checkpoints

Capture evidence at these points:

1. Phase 1: API and engineering quality baseline.
2. Phase 4: core algorithm with a convincing revision demo.
3. Phase 6: complete local MVP and reproducible snapshot story.
4. Phase 8: cloud architecture and operations story.

The Git history will then show a natural progression: product thinking, foundations, data modeling, integration, algorithmic behavior, API design, reproducibility, asynchronous systems, and cloud operations.

