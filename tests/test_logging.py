"""Structured logging tests."""

import json
import logging

from research_data_builder.core.logging import JsonFormatter


def test_json_formatter_includes_context() -> None:
    record = logging.LogRecord(
        name="research_data_builder.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=12,
        msg="processed %s",
        args=("job",),
        exc_info=None,
    )
    record.request_id = "req_123"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "research_data_builder.test"
    assert payload["message"] == "processed job"
    assert payload["request_id"] == "req_123"
    assert payload["timestamp"].endswith("+00:00")
