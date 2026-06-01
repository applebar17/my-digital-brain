from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from my_digital_brain.ingestion.contracts.base import IngestionModel


class ValidationIssue(IngestionModel):
    field_path: str = Field(description="Path to the invalid or risky field.")
    message: str = Field(description="Verbose message that can guide an LLM tool retry.")
    code: str = Field(description="Stable machine-readable validation code.")
    severity: Literal["error", "warning"] = "error"
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(IngestionModel):
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def ok(cls) -> ValidationResult:
        return cls(is_valid=True)

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue]) -> ValidationResult:
        return cls(
            is_valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )
