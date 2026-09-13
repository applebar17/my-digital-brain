from __future__ import annotations

from dataclasses import dataclass

from my_digital_brain.agentic.enums import AgenticStateId


@dataclass(frozen=True, slots=True)
class ActivityPresentation:
    activity_group: str
    titles: tuple[str, ...]
    summary: str


_PRESENTATIONS: dict[str, ActivityPresentation] = {
    AgenticStateId.CONVERSATION_ENTRY.value: ActivityPresentation(
        activity_group="understanding",
        titles=(
            "Understanding your request",
            "Getting oriented",
            "Working out what you need",
        ),
        summary="Working out the best way to help.",
    ),
    AgenticStateId.REASONING_CHECKPOINT.value: ActivityPresentation(
        activity_group="understanding",
        titles=(
            "Thinking this through",
            "Considering the details",
            "Working through the important points",
        ),
        summary="Considering the relevant details before continuing.",
    ),
    AgenticStateId.PLANNING_CHECKPOINT.value: ActivityPresentation(
        activity_group="planning",
        titles=(
            "Planning the next steps",
            "Organizing the work",
            "Building a plan",
        ),
        summary="Organizing the next steps for this request.",
    ),
    AgenticStateId.MEMORY_LOG_EXTRACTION.value: ActivityPresentation(
        activity_group="memory",
        titles=(
            "Picking out meaningful details",
            "Finding the key moments",
            "Extracting memories",
        ),
        summary="Identifying the details that may be useful to remember.",
    ),
    AgenticStateId.MEMORY_QUERY.value: ActivityPresentation(
        activity_group="memory",
        titles=(
            "Searching your memories",
            "Looking through related memories",
            "Finding relevant context",
        ),
        summary="Checking related memories and existing context.",
    ),
    AgenticStateId.MEMORY_INGESTION.value: ActivityPresentation(
        activity_group="memory",
        titles=(
            "Organizing what you shared",
            "Preparing your memories",
            "Structuring this information",
        ),
        summary="Preparing the information for careful review.",
    ),
    AgenticStateId.MEMORY_CREATION.value: ActivityPresentation(
        activity_group="saving",
        titles=(
            "Saving the selected memories",
            "Adding this to your memory",
            "Creating memory entries",
        ),
        summary="Saving the memory details that are ready to keep.",
    ),
    AgenticStateId.GRAPH_UPDATE.value: ActivityPresentation(
        activity_group="saving",
        titles=(
            "Updating your memory graph",
            "Connecting related information",
            "Applying the updates",
        ),
        summary="Updating the connections between related information.",
    ),
    AgenticStateId.CONTRADICTION_REVIEW.value: ActivityPresentation(
        activity_group="checking",
        titles=(
            "Checking for conflicts",
            "Comparing with existing memories",
            "Making sure this fits",
        ),
        summary="Comparing this request with existing information.",
    ),
    AgenticStateId.PROFILE_DUPLICATION.value: ActivityPresentation(
        activity_group="checking",
        titles=(
            "Checking your profile context",
            "Reviewing saved preferences",
            "Comparing profile details",
        ),
        summary="Reviewing approved profile context for this request.",
    ),
    AgenticStateId.CLARIFICATION_AGENT.value: ActivityPresentation(
        activity_group="waiting",
        titles=(
            "Preparing a question",
            "Checking what needs clarification",
            "Putting together a quick question",
        ),
        summary="Preparing a focused question before continuing.",
    ),
    "ingestion.prepare_context": ActivityPresentation(
        activity_group="memory",
        titles=(
            "Preparing the memory context",
            "Gathering the relevant context",
            "Getting the memory details ready",
        ),
        summary="Preparing the information needed for the memory process.",
    ),
    "ingestion.resolve_identities": ActivityPresentation(
        activity_group="checking",
        titles=(
            "Checking the people and places",
            "Matching names with your memories",
            "Reviewing possible matches",
        ),
        summary="Checking names and references against existing information.",
    ),
    "ingestion.validate_changes": ActivityPresentation(
        activity_group="checking",
        titles=(
            "Reviewing the proposed changes",
            "Checking the details before saving",
            "Making sure the updates are consistent",
        ),
        summary="Checking the proposed changes before they are saved.",
    ),
}

_FALLBACK_PRESENTATION = ActivityPresentation(
    activity_group="understanding",
    titles=(
        "Working on your request",
        "Making progress",
        "Taking a closer look",
    ),
    summary="Working through the request and preparing the next step.",
)


def activity_presentation(activity_key: str) -> ActivityPresentation:
    """Return safe copy for a state or process step, with a future-proof fallback."""

    return _PRESENTATIONS.get(activity_key, _FALLBACK_PRESENTATION)


def activity_title(activity_key: str, occurrence: int = 0) -> str:
    presentation = activity_presentation(activity_key)
    index = max(0, occurrence) % len(presentation.titles)
    return presentation.titles[index]


def known_activity_keys() -> tuple[str, ...]:
    return tuple(_PRESENTATIONS)
