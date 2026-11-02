"""PostgreSQL integration tests for append-only economic history."""

import asyncio
import os
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from macromonitor.db.models import ChangeEvent, ChangeType, ObservationVersion, Series, SyncRun
from macromonitor.db.repositories import (
    ChangeEventInput,
    ChangeEventRepository,
    ObservationVersionInput,
    ObservationVersionRepository,
    SeriesInput,
    SeriesRepository,
    SyncCounts,
    SyncRunRepository,
)
from macromonitor.db.session import Database

TEST_DATABASE_URL = os.getenv("MACROMONITOR_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="PostgreSQL test URL is not configured"),
]


async def clear_history(database: Database) -> None:
    """Delete integration-test records in foreign-key order."""
    async with database.session() as session, session.begin():
        await session.execute(delete(ChangeEvent))
        await session.execute(delete(ObservationVersion))
        await session.execute(delete(SyncRun))
        await session.execute(delete(Series))


def test_postgres_preserves_versions_constraints_and_transactions() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        database = Database(TEST_DATABASE_URL)
        await clear_history(database)

        try:
            async with database.session() as session, session.begin():
                series_repository = SeriesRepository(session)
                run_repository = SyncRunRepository(session)
                version_repository = ObservationVersionRepository(session)
                event_repository = ChangeEventRepository(session)

                series = await series_repository.create(
                    SeriesInput(
                        provider="fred",
                        provider_series_id="CPIAUCSL",
                        title="Consumer Price Index",
                        units="Index 1982-1984=100",
                        frequency="Monthly",
                    )
                )
                run = await run_repository.start(series.id)
                period = date(2026, 9, 1)
                initial = await version_repository.append(
                    ObservationVersionInput(
                        series_id=series.id,
                        sync_run_id=run.id,
                        observation_date=period,
                        value=Decimal("325.3000000000"),
                        is_missing=False,
                        content_fingerprint="1" * 64,
                        first_observed_at=datetime(2026, 10, 1, tzinfo=UTC),
                    )
                )
                revised = await version_repository.append(
                    ObservationVersionInput(
                        series_id=series.id,
                        sync_run_id=run.id,
                        observation_date=period,
                        value=Decimal("325.5000000000"),
                        is_missing=False,
                        content_fingerprint="2" * 64,
                        first_observed_at=datetime(2026, 11, 1, tzinfo=UTC),
                    )
                )
                await event_repository.create(
                    ChangeEventInput(
                        series_id=series.id,
                        sync_run_id=run.id,
                        change_type=ChangeType.REVISED,
                        deterministic_key="3" * 64,
                        observation_date=period,
                        previous_version_id=initial.id,
                        new_version_id=revised.id,
                        change_amount=Decimal("0.2000000000"),
                        absolute_change=Decimal("0.2000000000"),
                    )
                )
                await run_repository.succeed(run, SyncCounts(revised=1))
                series_id = series.id
                run_id = run.id

            async with database.session() as session:
                versions = await ObservationVersionRepository(session).list_for_period(
                    series_id, period
                )
                latest = await ObservationVersionRepository(session).latest_for_period(
                    series_id, period
                )
                events = await ChangeEventRepository(session).list_for_sync_run(run_id)

                assert [version.value for version in versions] == [
                    Decimal("325.3000000000"),
                    Decimal("325.5000000000"),
                ]
                assert latest is not None
                assert latest.id == versions[-1].id
                assert events[0].change_amount == Decimal("0.2000000000")

            with pytest.raises(IntegrityError):
                async with database.session() as session, session.begin():
                    await SeriesRepository(session).create(
                        SeriesInput(
                            provider="fred",
                            provider_series_id="CPIAUCSL",
                            title="Duplicate CPI",
                            units="Index",
                            frequency="Monthly",
                        )
                    )

            with pytest.raises(IntegrityError):
                async with database.session() as session, session.begin():
                    duplicate_run = await SyncRunRepository(session).start(series_id)
                    await ObservationVersionRepository(session).append(
                        ObservationVersionInput(
                            series_id=series_id,
                            sync_run_id=duplicate_run.id,
                            observation_date=period,
                            value=Decimal("325.5000000000"),
                            is_missing=False,
                            content_fingerprint="2" * 64,
                        )
                    )

            with pytest.raises(RuntimeError, match="force rollback"):
                async with database.session() as session, session.begin():
                    await SeriesRepository(session).create(
                        SeriesInput(
                            provider="fred",
                            provider_series_id="ROLLBACK_TEST",
                            title="Must be rolled back",
                            units="Index",
                            frequency="Monthly",
                        )
                    )
                    raise RuntimeError("force rollback")

            async with database.session() as session:
                rolled_back = await SeriesRepository(session).get_by_provider_id(
                    "fred", "ROLLBACK_TEST"
                )
                assert rolled_back is None
        finally:
            await database.dispose()

    asyncio.run(scenario())
