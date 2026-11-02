# MacroMonitor

[![CI](https://github.com/atharvanaik06/economic-release-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/atharvanaik06/economic-release-tracker/actions/workflows/ci.yml)

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

## Quick start

Requirements: Python 3.12 or newer. Docker is optional for the containerized workflow.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cp .env.example .env
.venv/bin/uvicorn macromonitor.main:app --app-dir src --reload
```

Then open:

- API health: <http://localhost:8000/health>
- Interactive API documentation: <http://localhost:8000/docs>
- OpenAPI document: <http://localhost:8000/openapi.json>

Run all local quality checks:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src tests
.venv/bin/pytest --cov=macromonitor --cov-report=term-missing
```

Or start the API and PostgreSQL with Docker:

```bash
docker compose up --build
```

See the [development guide](docs/DEVELOPMENT.md) for configuration, locked dependency installation, and contributor commands.

## Project documents

- [Product requirements](docs/REQUIREMENTS.md)
- [System design](docs/SYSTEM_DESIGN.md)
- [Phased build and commit plan](docs/ROADMAP.md)
- [Development guide](docs/DEVELOPMENT.md)

## Current status

Phase 1 complete: FastAPI foundation, validated settings, structured logging, tests, containers, and continuous integration.

Next: Phase 2 will introduce PostgreSQL models and migrations for append-only economic observation history.
