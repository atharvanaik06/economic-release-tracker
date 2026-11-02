# MacroMonitor

MacroMonitor is a backend service that monitors selected economic indicators, detects new releases and historical revisions, and sends reliable webhook notifications describing exactly what changed.

The GitHub repository remains named `economic-release-tracker`; **MacroMonitor** is the product name.

## The idea in plain English

MacroMonitor works like a price tracker for government economic data:

1. A user selects indicators such as CPI, GDP, unemployment, or interest rates.
2. Scheduled workers retrieve the latest data from FRED.
3. The service compares the response with its append-only PostgreSQL history.
4. It identifies new, revised, removed, or missing observations.
5. It stores an auditable change event.
6. It sends a signed webhook to subscribed applications.

Example:

```text
New observation:
October 2026: 326.4

Revisions:
August 2026:    324.1 -> 324.0
September 2026: 325.3 -> 325.5
```

FRED provides the underlying data. MacroMonitor provides the monitoring, comparison, history, and notification workflow.

## Product MVP

The first complete product will support:

- FRED economic series;
- user watchlists;
- manual and scheduled synchronization;
- append-only observation versions;
- new, revised, unchanged, removed, and missing classifications;
- release and revision history through FastAPI;
- webhook subscriptions;
- asynchronous delivery with retries and attempt history;
- idempotent processing so retries do not duplicate versions or notifications;
- deterministic fixtures and automated tests.

Authentication and AWS deployment are added before the public production release. Email, extra data providers, a browser frontend, point-in-time research snapshots, and quantitative analysis are optional extensions.

## Technology direction

- FastAPI and Pydantic
- PostgreSQL, SQLAlchemy, and Alembic
- Background workers and a queue
- Docker Compose for local development
- AWS ECS Fargate, RDS, SQS, EventBridge, ECR, and CloudWatch for production
- pytest and GitHub Actions

## Project documents

- [Product requirements](docs/REQUIREMENTS.md)
- [System design](docs/SYSTEM_DESIGN.md)
- [Phased build and commit plan](docs/ROADMAP.md)

## Current status

Phase 0: product definition aligned around monitoring, watchlists, and reliable notifications.
