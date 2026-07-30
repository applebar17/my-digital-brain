from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from my_digital_brain.core.ids import new_uuid


class ClarificationModel(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class ClarificationKind(StrEnum):
    IDENTITY_NO_MATCH = "identity_no_match"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    MISSING_ATTRIBUTE = "missing_attribute"
    CONFIRM_PROPOSAL = "confirm_proposal"
    CORRECT_CONFLICT = "correct_conflict"
    RELATIONSHIP_TARGET = "relationship_target"
    EXPLICIT_DISCARD = "explicit_discard"


class ClarificationResponseMode(StrEnum):
    FREE_TEXT = "free_text"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    CONFIRMATION = "confirmation"
    CHOICE_OR_TEXT = "choice_or_text"
    TEXT_OR_AUDIO = "text_or_audio"


OPTION_SUMMARY_REQUIRED_KINDS = frozenset(
    {
        ClarificationKind.IDENTITY_AMBIGUOUS,
        ClarificationKind.CORRECT_CONFLICT,
        ClarificationKind.RELATIONSHIP_TARGET,
    }
)


def option_summaries_required(kind: ClarificationKind | str) -> bool:
    return kind in OPTION_SUMMARY_REQUIRED_KINDS


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
    summary: str | None = Field(default=None, max_length=160)
    recommended: bool = False


class ClarificationQuestion(ClarificationModel):
    question_id: str = Field(default_factory=new_uuid)
    question: str = Field(min_length=1)
    kind: ClarificationKind
    response_mode: ClarificationResponseMode
    options: list[ClarificationOption] = Field(default_factory=list, max_length=5)
    target_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    allow_custom_answer: bool = True
    required: bool = True

    @model_validator(mode="after")
    def _validate_semantics(self) -> ClarificationQuestion:
        mode = str(self.response_mode)
        if (
            self.response_mode
            in {
                ClarificationResponseMode.FREE_TEXT,
                ClarificationResponseMode.TEXT_OR_AUDIO,
            }
            and self.options
        ):
            raise ValueError(f"{mode} questions cannot provide choice options.")
        if (
            self.response_mode
            in {
                ClarificationResponseMode.SINGLE_CHOICE,
                ClarificationResponseMode.MULTIPLE_CHOICE,
                ClarificationResponseMode.CONFIRMATION,
                ClarificationResponseMode.CHOICE_OR_TEXT,
            }
            and not self.options
        ):
            raise ValueError(f"{mode} questions require options.")
        if self.response_mode == ClarificationResponseMode.CONFIRMATION and len(self.options) != 2:
            raise ValueError("Confirmation questions require exactly two options.")
        if option_summaries_required(self.kind):
            missing_summaries = [
                option.label
                for option in self.options
                if not option.summary or not option.summary.strip()
            ]
            if missing_summaries:
                raise ValueError(
                    f"Disambiguation options require brief summaries: {missing_summaries}."
                )
        if not self.allow_custom_answer and self.response_mode in {
            ClarificationResponseMode.FREE_TEXT,
            ClarificationResponseMode.TEXT_OR_AUDIO,
            ClarificationResponseMode.CHOICE_OR_TEXT,
        }:
            raise ValueError("Free-form response modes cannot disable custom answers.")
        return self


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
    questions: list[ClarificationQuestion] = Field(min_length=1, max_length=5)
    target_refs: list[str] = Field(default_factory=list)
    history_delta: list[ClarificationHistoryMessage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_question_ids(self) -> ClarificationPacket:
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Clarification question IDs must be unique within a packet.")
        option_ids = [
            option.option_id for question in self.questions for option in question.options
        ]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Clarification option IDs must be unique within a packet.")
        return self

    def validate_model_refs(self, allowed_refs: set[str] | None = None) -> None:
        refs = [
            *self.target_refs,
            *[
                ref
                for question in self.questions
                for ref in [
                    *question.target_refs,
                    *question.evidence_refs,
                    *[option.target_ref for option in question.options],
                ]
                if ref
            ],
        ]
        persisted_ids = [ref for ref in refs if _looks_like_persisted_id(ref)]
        if persisted_ids:
            raise ValueError(
                "Clarification packets may contain model-facing refs only; "
                f"persisted graph IDs found: {sorted(set(persisted_ids))}."
            )
        if allowed_refs is not None:
            unknown = sorted(set(refs) - allowed_refs)
            if unknown:
                raise ValueError(
                    "Clarification packet contains refs not supplied in the active context: "
                    f"{unknown}."
                )


class ClarificationAnswer(ClarificationModel):
    question_id: str
    selected_option_ids: list[str] = Field(default_factory=list)
    text: str | None = None
    audio_media_ref: str | None = None
    normalized_text: str | None = None


class ClarificationAnswerPacket(ClarificationModel):
    packet_id: str
    frame_id: str
    tool_call_id: str
    answers: list[ClarificationAnswer] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def _validate_answer_ids(self) -> ClarificationAnswerPacket:
        question_ids = [answer.question_id for answer in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Clarification answers must contain unique question IDs.")
        return self


def _looks_like_persisted_id(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return ":" in value or value.startswith("neo4j-")


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
