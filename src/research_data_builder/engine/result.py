"""Provider-independent transformation and preview results."""

from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass(frozen=True, slots=True)
class JoinReport:
    """Unmatched key counts contributed by one variable join."""

    variable: str
    left_only_keys: int
    right_only_keys: int


@dataclass(frozen=True, slots=True)
class DatasetPreview:
    """Bounded JSON-compatible preview with full result dimensions."""

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    preview_row_count: int
    total_row_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """One in-memory deterministic table plus explainable join metadata."""

    frame: pl.DataFrame
    join_reports: tuple[JoinReport, ...]
    entity_mapping_version: str

    def preview(self, *, limit: int = 100) -> DatasetPreview:
        if not 1 <= limit <= 1_000:
            raise ValueError("preview limit must be between 1 and 1000")
        rows = tuple(self.frame.head(limit).to_dicts())
        return DatasetPreview(
            columns=tuple(self.frame.columns),
            rows=rows,
            preview_row_count=len(rows),
            total_row_count=self.frame.height,
            truncated=self.frame.height > limit,
        )
