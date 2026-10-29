# Economic Release Tracker

An API-first platform that records how economic data changes over time. It detects new observations and revisions, preserves what was known at each point in time, and creates reproducible dataset snapshots.

## The idea in plain English

Economic figures are not fixed forever. A GDP or employment number can be published today and revised later. Most data APIs make it easy to fetch the latest value, but they do not make it convenient to answer:

- What changed in the latest release?
- Was an old value revised?
- What data was available on a particular date?
- Can I reproduce an analysis using the same data version?

This project periodically saves provider data, compares each retrieval with the previous one, and exposes the differences through a REST API.

## Deliberately small first version

The MVP will support:

- one provider: FRED;
- a small configured set of economic series;
- manual synchronization;
- versioned observations in PostgreSQL;
- detection of new, revised, and unchanged observations;
- release/change history through FastAPI;
- point-in-time snapshots with CSV/JSON export and a checksum;
- automated tests for the comparison and snapshot logic.

Email, webhooks, AWS scheduling, additional providers, authentication, and a frontend are later phases. They are intentionally excluded from the MVP.

## Project documents

- [Product requirements](docs/REQUIREMENTS.md)
- [Phased build and commit plan](docs/ROADMAP.md)

## Current status

Phase 0: product scope and delivery plan.

