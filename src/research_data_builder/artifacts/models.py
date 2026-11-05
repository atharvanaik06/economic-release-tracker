"""Artifact bundle result objects."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExportedArtifact:
    name: str
    kind: str
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BundleResult:
    directory: Path
    dataset_checksum: str
    artifacts: tuple[ExportedArtifact, ...]
    manifest: dict[str, Any]
    lineage: dict[str, Any]
