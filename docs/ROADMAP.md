# MacroMonitor Phased Build and Commit Plan

## How we will work

Every phase ends with working behavior, tests, and updated documentation. We will commit each coherent engineering result and push regularly; phases 1, 4, 7, and 8 are portfolio checkpoints, not the only times code reaches GitHub.

Good commits describe an outcome:

```text
feat: classify revised economic observations
test: verify duplicate ingestion remains idempotent
feat: retry failed webhook deliveries
```

We will not create artificial commits merely to increase the commit count.

## Phase 0: Align the product

**Goal:** define MacroMonitor as a monitoring and notification product.

Deliverables:

- One-sentence product pitch.
- Monitoring-focused requirements.
- Architecture centered on watchlists, scheduled ingestion, and webhooks.
- Separation between the product MVP, production deployment, and optional research features.

Planned commit:

1. `docs: refocus product on economic monitoring and alerts`

Exit condition: a recruiter can understand the product in 30 seconds.

## Phase 1: Create a professional service skeleton

**Goal:** boot a small, tested FastAPI application locally.

Deliverables:

- Python project and locked dependency configuration.
- FastAPI application with `/health`.
- Typed settings loaded from environment variables.
- Structured logging foundation.
- Formatting, linting, typing, and pytest configuration.
- Dockerfile and Docker Compose PostgreSQL service.
- GitHub Actions validation workflow.
- `.env.example` without real credentials.

Likely commits:

1. `chore: initialize FastAPI project and developer tooling`
2. `feat: add health endpoint and environment settings`
3. `build: add containerized local development stack`
4. `ci: validate formatting types and tests`

Demo: clone the repository, start the stack, and receive a healthy API response.

**Portfolio checkpoint:** polish setup instructions and capture the first working API screenshot.

## Phase 2: Design and persist economic history

**Goal:** build the append-only database foundation without relying on a live provider.

Deliverables:

- Domain types for series, observations, versions, sync runs, and change events.
- SQLAlchemy models and Alembic migrations.
- Decimal-safe value representation.
- Constraints protecting version identity and append-only history.
- Repository queries for current values and revision history.
- PostgreSQL integration tests.

Likely commits:

1. `feat: model economic series and observation versions`
2. `feat: add sync run and change event schema`
3. `feat: implement revision history repositories`
4. `test: verify uniqueness transactions and version history`

Demo: load two fixture vintages and query the complete history of one period.

## Phase 3: Integrate FRED behind a provider interface

**Goal:** retrieve and normalize economic data without coupling the system to FRED response formats.

Deliverables:

- Provider protocol.
- FRED HTTP client with timeout, retry, and error mapping.
- Normalization of decimals, dates, missing values, units, and frequency.
- Fake provider and deterministic fixtures.
- Tests that run without external network access.

Likely commits:

1. `feat: define economic data provider contract`
2. `feat: implement FRED series and observation client`
3. `test: add deterministic provider fixtures`

Demo: fetch and normalize one configured series while the full test suite remains offline.

## Phase 4: Build the synchronization and revision engine

**Goal:** reliably convert provider responses into version history and change events.

Deliverables:

- `new`, `revised`, `unchanged`, `removed`, and `missing` classifications.
- Metadata-change detection.
- Atomic persistence of versions, events, and sync status.
- Idempotency for repeated input.
- Per-series concurrency control.
- Failure-state logging and rollback tests.

Likely commits:

1. `feat: classify economic observation changes`
2. `feat: persist synchronization results atomically`
3. `feat: make repeated synchronization idempotent`
4. `feat: prevent concurrent syncs for one series`
5. `test: cover revisions removals failures and rollback`

Demo: process two fixture releases, display a new observation and revision, then repeat the job with zero duplicates.

**Portfolio checkpoint:** record the core revision demo and document the key database and idempotency decisions.

## Phase 5: Expose the core API and watchlists

**Goal:** allow clients to configure monitoring and inspect results through HTTP.

Deliverables:

- Series catalog endpoints.
- Manual sync endpoint.
- Sync-run and revision-history endpoints.
- Watchlist CRUD and series membership.
- Watchlist event feed.
- Validation, cursor pagination, consistent errors, and OpenAPI examples.
- API integration tests.

Likely commits:

1. `feat: expose tracked series and sync history`
2. `feat: add watchlist management`
3. `feat: expose watchlist change events`
4. `test: cover API validation pagination and errors`
5. `docs: add core API walkthrough`

Demo: create a watchlist and inspect its revision event using only API calls.

## Phase 6: Add scheduled asynchronous ingestion

**Goal:** monitor watched series automatically without blocking API requests.

Deliverables:

- Background job abstraction with a simple local queue implementation.
- Schedule calculation for active watched series.
- Worker that invokes the existing synchronization service.
- Deterministic job identity and safe redelivery.
- Retry, timeout, and dead-letter behavior.
- Job-status and series-staleness visibility.

The local implementation preserves the boundaries later used by EventBridge and SQS without requiring AWS during development.

Likely commits:

1. `feat: enqueue watched series synchronization jobs`
2. `feat: process ingestion jobs in a background worker`
3. `feat: retry and dead-letter failed ingestion jobs`
4. `test: prove safe duplicate job delivery`
5. `docs: add scheduled monitoring demonstration`

Demo: a schedule creates a job, a worker detects a fixture revision, and redelivery creates no duplicate event.

## Phase 7: Deliver reliable webhook notifications

**Goal:** complete the local MacroMonitor product.

Deliverables:

- Webhook subscription endpoints.
- Test-event validation.
- HMAC-signed event payloads.
- Notification queue and delivery worker.
- Exponential-backoff retries.
- Delivery-attempt audit history.
- Dead-letter state and safe manual replay.
- End-to-end test from economic revision to webhook receipt.

Likely commits:

1. `feat: add webhook subscriptions to watchlists`
2. `feat: enqueue signed change notifications`
3. `feat: deliver webhooks in a background worker`
4. `feat: retry audit and dead-letter failed deliveries`
5. `feat: safely replay failed webhook deliveries`
6. `test: cover the complete monitoring workflow`
7. `docs: add MacroMonitor local demo`

Demo: a watched revision produces a signed webhook; a failing receiver is retried, audited, dead-lettered, and successfully replayed.

**Product MVP release:** tag `v0.1.0`.

**Portfolio checkpoint:** publish a short recorded demonstration, architecture diagram, measured test count, and local performance figures.

## Phase 8: Secure, deploy, and operate on AWS

**Goal:** turn the local product into a credible public production service.

Deliverables:

- User authentication and ownership authorization.
- Production rate limits and secure webhook-secret handling.
- API and worker container images in ECR.
- ECS Fargate services.
- RDS PostgreSQL with backups.
- EventBridge scheduling.
- SQS ingestion and notification queues with dead-letter queues.
- CloudWatch logs, metrics, dashboards, and alarms.
- Secrets Manager integration.
- GitHub Actions deployment workflow.
- Infrastructure as code, cost notes, recovery procedure, and runbook.

Likely commits:

1. `feat: add authentication and resource ownership`
2. `infra: provision network database queues and secrets`
3. `infra: deploy API ingestion and delivery services`
4. `infra: schedule monitoring and configure dead-letter queues`
5. `ops: add metrics alarms backups and runbook`
6. `ci: automate production image build and deployment`
7. `docs: publish production architecture and live demo`

Demo: a real scheduled FRED check produces an auditable change event and delivers a webhook from the deployed system.

**Production release:** tag `v1.0.0`.

**Portfolio checkpoint:** include the live API, production architecture, operational metrics, and failure-recovery demonstration.

## Phase 9: Optional extensions

Only begin these after the monitoring workflow is reliable:

- Email notification.
- Point-in-time research queries.
- Immutable datasets and checksums.
- Revision analytics dashboard.
- BEA or World Bank provider.
- Release-calendar awareness.
- Quantitative revision-bias or look-ahead-bias analysis.

Each extension requires a separate issue, measurable user value, and its own commit series.

## Milestones and Git workflow

| Point | Result | Suggested tag |
|---|---|---|
| Phase 1 | Working API foundation | optional `v0.0.1` |
| Phase 4 | Complete revision engine | optional `v0.0.2` |
| Phase 7 | Complete local product MVP | `v0.1.0` |
| Phase 8 | Secure deployed production service | `v1.0.0` |

Commit after every meaningful, tested change. Push at the end of each completed work session or feature. Milestone phases are for README polish, demonstrations, and releases—not the only times we push.
