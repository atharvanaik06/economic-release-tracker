"""Explain stored recipe, input, and output differences between builds."""

from typing import Any

from research_data_builder.db.models import BuildRun


def compare_builds(left: BuildRun, right: BuildRun) -> dict[str, Any]:
    """Compare reproducibility identities without claiming row-level differences."""
    left_plan = left.plan
    right_plan = right.plan
    left_inputs = {
        (item["output_name"], item["indicator_fingerprint"]) for item in left_plan.get("inputs", [])
    }
    right_inputs = {
        (item["output_name"], item["indicator_fingerprint"])
        for item in right_plan.get("inputs", [])
    }
    return {
        "left_build_id": str(left.id),
        "right_build_id": str(right.id),
        "same_recipe": left_plan.get("recipe_content_hash")
        == right_plan.get("recipe_content_hash"),
        "same_inputs": left_inputs == right_inputs,
        "same_dataset": bool(left.dataset_checksum)
        and left.dataset_checksum == right.dataset_checksum,
        "left_dataset_checksum": left.dataset_checksum,
        "right_dataset_checksum": right.dataset_checksum,
        "left_row_count": left.row_count,
        "right_row_count": right.row_count,
        "added_inputs": sorted(right_inputs - left_inputs),
        "removed_inputs": sorted(left_inputs - right_inputs),
    }
