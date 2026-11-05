"""Machine-readable validation result models."""

from dataclasses import asdict, dataclass
from typing import Any, Literal

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    variable: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    passed: bool
    row_count: int
    expected_row_count: int | None
    coverage_percent: float | None
    issues: tuple[ValidationIssue, ...]
    missing_by_variable: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "row_count": self.row_count,
            "expected_row_count": self.expected_row_count,
            "coverage_percent": self.coverage_percent,
            "issues": [asdict(issue) for issue in self.issues],
            "missing_by_variable": self.missing_by_variable,
            "summary": {
                "info": sum(issue.severity == "info" for issue in self.issues),
                "warnings": sum(issue.severity == "warning" for issue in self.issues),
                "errors": sum(issue.severity == "error" for issue in self.issues),
            },
        }
