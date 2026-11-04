"""Tests for bounded deterministic dataset previews."""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from research_data_builder.engine import ExecutionResult


def test_preview_is_bounded_and_reports_full_shape() -> None:
    result = ExecutionResult(
        frame=pl.DataFrame({"entity": ["CZE", "DEU"], "value": [1, 2]}),
        join_reports=(),
        entity_mapping_version="v1",
    )

    preview = result.preview(limit=1)

    assert preview.columns == ("entity", "value")
    assert preview.rows == ({"entity": "CZE", "value": 1},)
    assert preview.preview_row_count == 1
    assert preview.total_row_count == 2
    assert preview.truncated is True

    with pytest.raises(ValueError, match="between 1 and 1000"):
        result.preview(limit=0)


def test_preview_serializes_dates_and_decimals_for_json_storage() -> None:
    result = ExecutionResult(
        frame=pl.DataFrame(
            {"period": [date(2024, 1, 1)], "value": [Decimal("1.2500000000")]},
            schema_overrides={"value": pl.Decimal(30, 10)},
        ),
        join_reports=(),
        entity_mapping_version="v1",
    )

    assert result.preview().as_dict()["rows"] == [{"period": "2024-01-01", "value": "1.2500000000"}]
