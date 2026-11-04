"""Tests for bounded deterministic dataset previews."""

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
