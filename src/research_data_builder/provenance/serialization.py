"""Stable logical dataset serialization and SHA-256 identity."""

import hashlib
import json

import polars as pl

from research_data_builder.engine.result import json_value


def canonical_dataset_bytes(frame: pl.DataFrame) -> bytes:
    """Serialize schema and rows without presentation-only or timestamp fields."""
    payload = {
        "columns": frame.columns,
        "schema": {name: str(dtype) for name, dtype in frame.schema.items()},
        "rows": [[json_value(row[column]) for column in frame.columns] for row in frame.to_dicts()],
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def dataset_checksum(frame: pl.DataFrame) -> str:
    """Hash canonical logical content independently from CSV or Parquet encoding."""
    return hashlib.sha256(canonical_dataset_bytes(frame)).hexdigest()
