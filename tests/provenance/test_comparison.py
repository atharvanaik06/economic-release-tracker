"""Tests for explainable stored build comparisons."""

from uuid import uuid4

from research_data_builder.db.models import BuildRun, BuildStatus
from research_data_builder.provenance import compare_builds


def build(checksum: str, fingerprint: str) -> BuildRun:
    return BuildRun(
        id=uuid4(),
        recipe_version_id=uuid4(),
        status=BuildStatus.SUCCEEDED,
        build_identity="a" * 64,
        plan={
            "recipe_content_hash": "b" * 64,
            "inputs": [{"output_name": "gdp", "indicator_fingerprint": fingerprint}],
        },
        dataset_checksum=checksum,
        row_count=10,
    )


def test_comparison_distinguishes_input_and_output_changes() -> None:
    left = build("c" * 64, "d" * 64)
    identical = build("c" * 64, "d" * 64)
    changed = build("e" * 64, "f" * 64)

    same = compare_builds(left, identical)
    assert same["same_recipe"] is True
    assert same["same_inputs"] is True
    assert same["same_dataset"] is True

    difference = compare_builds(left, changed)
    assert difference["same_inputs"] is False
    assert difference["same_dataset"] is False
    assert difference["added_inputs"] == [("gdp", "f" * 64)]
