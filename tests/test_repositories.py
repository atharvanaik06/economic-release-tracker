"""Fast repository behavior tests using a mocked SQLAlchemy session."""

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from macromonitor.db.models import ChangeType, SyncStatus
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


def mock_session() -> MagicMock:
    """Return a session double with awaitable SQLAlchemy methods."""
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    return session


def test_series_repository_creates_and_finds_series() -> None:
    async def scenario() -> None:
        session = mock_session()
        repository = SeriesRepository(session)
        values = SeriesInput(
            provider="fred",
            provider_series_id="CPIAUCSL",
            title="Consumer Price Index",
            units="Index",
            frequency="Monthly",
            provider_metadata={"seasonal_adjustment": "adjusted"},
        )

        series = await repository.create(values)
        session.scalar.return_value = series
        found = await repository.get_by_provider_id("fred", "CPIAUCSL")

        assert found is series
        assert series.provider_series_id == "CPIAUCSL"
        session.add.assert_called_once_with(series)
        assert session.flush.await_count == 1
        session.scalar.assert_awaited_once()

    asyncio.run(scenario())


def test_sync_run_repository_records_success_and_failure() -> None:
    async def scenario() -> None:
        session = mock_session()
        repository = SyncRunRepository(session)
        run = await repository.start(uuid4())

        await repository.succeed(run, SyncCounts(new=1, revised=2, unchanged=3))
        assert run.status is SyncStatus.SUCCEEDED
        assert run.finished_at is not None
        assert (run.new_count, run.revised_count, run.unchanged_count) == (1, 2, 3)

        failed_run = await repository.start(uuid4())
        await repository.fail(failed_run, error_code="provider_timeout", error_message="timed out")
        assert failed_run.status is SyncStatus.FAILED
        assert failed_run.error_code == "provider_timeout"
        assert failed_run.finished_at is not None
        assert session.flush.await_count == 4

    asyncio.run(scenario())


def test_observation_repository_appends_and_orders_versions() -> None:
    async def scenario() -> None:
        session = mock_session()
        repository = ObservationVersionRepository(session)
        series_id = uuid4()
        run_id = uuid4()
        period = date(2026, 9, 1)
        values = ObservationVersionInput(
            series_id=series_id,
            sync_run_id=run_id,
            observation_date=period,
            value=Decimal("325.3000000000"),
            is_missing=False,
            content_fingerprint="a" * 64,
            first_observed_at=datetime(2026, 10, 1, tzinfo=UTC),
        )

        version = await repository.append(values)
        session.scalar.return_value = version
        assert await repository.get_by_fingerprint("a" * 64) is version
        assert await repository.latest_for_period(series_id, period) is version

        scalar_result = MagicMock()
        scalar_result.__iter__.return_value = iter([version])
        session.scalars.return_value = scalar_result
        assert await repository.list_for_period(series_id, period) == [version]

        assert version.value == Decimal("325.3000000000")
        session.add.assert_called_once_with(version)
        assert session.scalar.await_count == 2
        session.scalars.assert_awaited_once()

    asyncio.run(scenario())


def test_change_event_repository_creates_and_lists_events() -> None:
    async def scenario() -> None:
        session = mock_session()
        repository = ChangeEventRepository(session)
        run_id = uuid4()
        new_version_id = uuid4()
        values = ChangeEventInput(
            series_id=uuid4(),
            sync_run_id=run_id,
            change_type=ChangeType.NEW,
            deterministic_key="b" * 64,
            observation_date=date(2026, 10, 1),
            new_version_id=new_version_id,
        )

        event = await repository.create(values)
        scalar_result = MagicMock()
        scalar_result.__iter__.return_value = iter([event])
        session.scalars.return_value = scalar_result

        assert await repository.list_for_sync_run(run_id) == [event]
        assert event.change_type is ChangeType.NEW
        assert event.new_version_id == new_version_id
        session.add.assert_called_once_with(event)
        session.flush.assert_awaited_once()

    asyncio.run(scenario())
