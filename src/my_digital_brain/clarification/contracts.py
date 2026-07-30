from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from my_digital_brain.core.ids import new_uuid


class ClarificationModel(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class ClarificationDoubt(ClarificationModel):
    doubt_id: str = Field(default_factory=new_uuid)
    doubt: str = Field(min_length=1)
    refs: list[str] = Field(default_factory=list)
    missing_information: str | None = None
    why_blocking: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class ClarificationHandoffRequest(ClarificationModel):
    doubts: list[ClarificationDoubt] = Field(min_length=1)
    invoker_state_id: str
    invoker_tool_call_id: str | None = None
    parent_frame_id: str | None = None


class ClarificationSessionInput(ClarificationModel):
    handoff: ClarificationHandoffRequest
    conversation: Any | None = None
    master_history: list[dict[str, Any]] = Field(default_factory=list)
    context_payload: dict[str, Any] = Field(default_factory=dict)
    session_id: str
    parent_frame_id: str | None = None
    parent_tool_call_id: str | None = None


ClarificationResolutionStatus = Literal[
    "resolved",
    "partially_resolved",
    "unresolved",
    "user_declined",
    "not_needed",
]


class ClarificationResolutionEntry(ClarificationModel):
    doubt_id: str
    status: ClarificationResolutionStatus
    questions: list[str] = Field(default_factory=list)
    user_answers: list[str] = Field(default_factory=list)
    selected_refs: list[str] = Field(default_factory=list)
    clarified_values: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    remaining_uncertainty: str | None = None


class ClarificationResolutionReport(ClarificationModel):
    entries: list[ClarificationResolutionEntry] = Field(min_length=1)
    summary: str = ""

    def validate_against(self, handoff: ClarificationHandoffRequest) -> None:
        expected = {doubt.doubt_id for doubt in handoff.doubts}
        actual = [entry.doubt_id for entry in self.entries]
        if len(actual) != len(set(actual)):
            raise ValueError("Clarification resolution entries must have unique doubt_id values.")
        if set(actual) != expected:
            missing = sorted(expected - set(actual))
            unexpected = sorted(set(actual) - expected)
            raise ValueError(
                "Clarification resolution report must contain exactly one entry per doubt "
                f"(missing={missing}, unexpected={unexpected})."
            )


class ClarificationOption(ClarificationModel):
    option_id: str = Field(default_factory=new_uuid)
    target_ref: str | None = None
    label: str = Field(min_length=1)
    description: str | None = None
    recommended: bool = False


class ClarificationQuestion(ClarificationModel):
    question_id: str = Field(default_factory=new_uuid)
    question: str = Field(min_length=1)
    options: list[ClarificationOption] = Field(default_factory=list, max_length=5)
    free_text_allowed: bool = True
    required: bool = True
    selection_mode: str = Field(default="single", pattern="^(single|multiple)$")


class ClarificationHistoryMessage(ClarificationModel):
    role: Literal["user", "assistant"]
    content: str


class ClarificationPacket(ClarificationModel):
    packet_id: str = Field(default_factory=new_uuid)
    frame_id: str
    tool_call_id: str | None = None
    tool_name: str | None = None
    origin_state_id: str
    reason: str
    questions: list[ClarificationQuestion] = Field(min_length=1, max_length=3)
    target_refs: list[str] = Field(default_factory=list)
    history_delta: list[ClarificationHistoryMessage] = Field(default_factory=list)


class ClarificationAnswer(ClarificationModel):
    question_id: str
    selected_option_ids: list[str] = Field(default_factory=list)
    free_text: str | None = None


class ClarificationAnswerPacket(ClarificationModel):
    packet_id: str
    frame_id: str
    tool_call_id: str
    answers: list[ClarificationAnswer] = Field(min_length=1, max_length=3)


def clarification_doubts_schema() -> dict[str, Any]:
    """Return the strict tool schema shared by every invoker toolbox."""

    return {
        "type": "array",
        "description": (
            "Detailed doubts for the clarification agent. Include the uncertainty, "
            "supplied refs, missing information, and why it matters."
        ),
        "minItems": 1,
        "maxItems": 20,
        "items": {
            "type": "object",
            "properties": {
                "doubt_id": {
                    "type": "string",
                    "description": "Stable run-scoped doubt identifier.",
                },
                "doubt": {
                    "type": "string",
                    "description": "Detailed source-grounded uncertainty to resolve.",
                },
                "refs": {
                    "type": "array",
                    "description": "Model-facing refs supplied in the current context.",
                    "items": {"type": "string"},
                },
                "missing_information": {
                    "type": ["string", "null"],
                    "description": "Information that may resolve the doubt.",
                },
                "why_blocking": {
                    "type": ["string", "null"],
                    "description": "Why the uncertainty affects the next decision.",
                },
                "evidence_refs": {
                    "type": "array",
                    "description": "Model-facing evidence refs supporting the doubt.",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "doubt_id",
                "doubt",
                "refs",
                "missing_information",
                "why_blocking",
                "evidence_refs",
            ],
            "additionalProperties": False,
        },
    }
