"""Agent-as-tool handoff between a parent state and clarification child."""

from datetime import UTC, datetime

from product.agentic.contracts import PausedStateContinuationDTO, ToolCallResultDTO
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.protocols.protocol_tools import (
    ToolErrorDTO,
    ToolInteractionRequestDTO,
    ToolOutputDTO,
)
from product.application.interactions import (
    InteractionContinuationStore,
    ParentToolResumeDTO,
    PendingNestedInteractionDTO,
    PendingUserQuestionDTO,
    QuestionMode,
    UserQuestionAnswerDTO,
    UserQuestionResolutionDTO,
    UserQuestionResolutionOutcome,
)
from product.application.states.clarification import (
    ClarificationRequestDTO,
    ClarificationResultDTO,
    ClarificationState,
)


class ClarificationAgentToolHandler:
    """Invoke, pause, and resume a clarification child behind one parent tool call."""

    def __init__(
        self,
        state: ClarificationState,
        continuation_store: InteractionContinuationStore,
    ) -> None:
        self.state = state
        self.continuation_store = continuation_store

    def invoke_with_context(
        self,
        request: ClarificationRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> ClarificationResultDTO | ToolInteractionRequestDTO[PendingUserQuestionDTO]:
        """Return a completed child result or propagate its user interaction pause."""
        outcome = self.state.clarify(request, invocation_context)
        if outcome.outcome == "failed":
            message = outcome.error.message if outcome.error else "Unknown clarification failure."
            raise ValueError(f"Clarification state failed: {message}")
        if outcome.outcome == "awaiting_input":
            if outcome.continuation is None:
                raise ValueError("Clarification state paused without a continuation.")
            packet = self.continuation_store.register_child(outcome.continuation)
            return ToolInteractionRequestDTO(interaction_packet=packet)
        if not isinstance(outcome.structured_output, ClarificationResultDTO):
            raise ValueError("Clarification state completed without its expected result contract.")
        return outcome.structured_output

    def bind_parent_continuation(
        self,
        continuation: PausedStateContinuationDTO[PendingUserQuestionDTO],
    ) -> None:
        """Store the materialized parent pause for children linked when they started."""
        for call in continuation.tool_batch.calls:
            if call.interaction_request is None:
                continue
            packet = call.interaction_request.interaction_packet
            interaction_ref = getattr(packet, "interaction_ref", None)
            if not isinstance(interaction_ref, str) or not self.continuation_store.contains(
                interaction_ref
            ):
                continue
            self.continuation_store.attach_parent(
                interaction_ref,
                continuation,
                call.provider_call_id,
            )

    def resolve_answer(
        self,
        answer: UserQuestionAnswerDTO,
        *,
        resolved_at: datetime | None = None,
    ) -> ParentToolResumeDTO | ToolInteractionRequestDTO[PendingUserQuestionDTO]:
        """Resolve a timely answer, or a timeout when the backend deadline passed."""
        timestamp = resolved_at or datetime.now(UTC)
        record = self.continuation_store.get(answer.interaction_ref)
        if timestamp >= record.interaction.deadline:
            resolution = self._timeout_resolution(record)
        else:
            resolution = self._answer_resolution(record, answer)
        claimed = self.continuation_store.claim(answer.interaction_ref)
        return self._resume_child(claimed, resolution)

    def resolve_timeout(
        self,
        interaction_ref: str,
        *,
        resolved_at: datetime | None = None,
    ) -> ParentToolResumeDTO | ToolInteractionRequestDTO[PendingUserQuestionDTO]:
        """Resolve an expired interaction without turning timeout into an error."""
        timestamp = resolved_at or datetime.now(UTC)
        record = self.continuation_store.get(interaction_ref)
        if timestamp < record.interaction.deadline:
            raise ValueError(
                f"Interaction '{interaction_ref}' has not reached its backend deadline."
            )
        claimed = self.continuation_store.claim(interaction_ref)
        return self._resume_child(claimed, self._timeout_resolution(claimed))

    def _resume_child(
        self,
        record: PendingNestedInteractionDTO,
        resolution: UserQuestionResolutionDTO,
    ) -> ParentToolResumeDTO | ToolInteractionRequestDTO[PendingUserQuestionDTO]:
        child_provider_call_id = self._child_provider_call_id(record)
        child_outcome = self.state.resume_clarification(
            record.child_continuation,
            [
                ToolCallResultDTO(
                    provider_call_id=child_provider_call_id,
                    tool_output=ToolOutputDTO(
                        status="ok",
                        data=resolution.model_dump(mode="json"),
                    ),
                )
            ],
        )
        if child_outcome.outcome == "awaiting_input":
            if child_outcome.continuation is None:
                raise ValueError("Clarification state paused again without a continuation.")
            packet = self.continuation_store.register_child(child_outcome.continuation)
            self.continuation_store.attach_parent(
                packet.interaction_ref,
                self._required_parent_continuation(record),
                self._required_parent_call_id(record),
            )
            return ToolInteractionRequestDTO(interaction_packet=packet)

        if child_outcome.outcome == "failed":
            error = child_outcome.error or ToolErrorDTO(
                code="clarification_child_failed",
                message="The clarification child could not complete after user interaction.",
            )
            parent_output = ToolOutputDTO(status="error", error=error)
        elif isinstance(child_outcome.structured_output, ClarificationResultDTO):
            parent_output = ToolOutputDTO(
                status="ok",
                data=child_outcome.structured_output.model_dump(mode="json"),
            )
        else:
            parent_output = ToolOutputDTO(
                status="error",
                error=ToolErrorDTO(
                    code="clarification_result_missing",
                    message="The clarification child completed without its expected result.",
                ),
            )

        return ParentToolResumeDTO(
            parent_continuation=self._required_parent_continuation(record),
            tool_result=ToolCallResultDTO(
                provider_call_id=self._required_parent_call_id(record),
                tool_output=parent_output,
            ),
        )

    @staticmethod
    def _answer_resolution(
        record: PendingNestedInteractionDTO,
        answer: UserQuestionAnswerDTO,
    ) -> UserQuestionResolutionDTO:
        packet = record.interaction
        options_by_ref = {option.option_ref: option for option in packet.options}
        unknown_refs = sorted(set(answer.selected_option_refs) - options_by_ref.keys())
        if unknown_refs:
            raise ValueError(
                f"Answer contains options not available for this interaction: {unknown_refs}."
            )
        if packet.mode == QuestionMode.SINGLE_CHOICE and len(answer.selected_option_refs) > 1:
            raise ValueError("A single-choice interaction accepts at most one selected option.")
        if packet.mode in {QuestionMode.FREE_RESPONSE, QuestionMode.CONFIRMATION} and (
            answer.selected_option_refs
        ):
            raise ValueError(f"{packet.mode.value} answers do not use option references.")

        selected_labels = [
            options_by_ref[option_ref].label for option_ref in answer.selected_option_refs
        ]
        text = (answer.text or "").strip()
        answer_parts = [*selected_labels, *([text] if text else [])]
        if not answer_parts:
            raise ValueError("Provide a selected option or a non-empty free-text answer.")
        return UserQuestionResolutionDTO(
            clarification_ref=packet.clarification_ref,
            outcome=UserQuestionResolutionOutcome.ANSWERED,
            answer="; ".join(answer_parts),
        )

    @staticmethod
    def _timeout_resolution(
        record: PendingNestedInteractionDTO,
    ) -> UserQuestionResolutionDTO:
        packet = record.interaction
        return UserQuestionResolutionDTO(
            clarification_ref=packet.clarification_ref,
            outcome=UserQuestionResolutionOutcome.TIMED_OUT,
        )

    @staticmethod
    def _child_provider_call_id(record: PendingNestedInteractionDTO) -> str:
        matches = [
            call.provider_call_id
            for call in record.child_continuation.tool_batch.calls
            if call.interaction_request is not None
            and getattr(
                call.interaction_request.interaction_packet,
                "interaction_ref",
                None,
            )
            == record.interaction.interaction_ref
        ]
        if len(matches) != 1:
            raise ValueError("Clarification interaction does not match one child provider call.")
        return matches[0]

    @staticmethod
    def _required_parent_continuation(
        record: PendingNestedInteractionDTO,
    ) -> PausedStateContinuationDTO[PendingUserQuestionDTO]:
        if record.parent_continuation is None:
            raise ValueError("Clarification interaction has no parent continuation.")
        return record.parent_continuation

    @staticmethod
    def _required_parent_call_id(record: PendingNestedInteractionDTO) -> str:
        if record.parent_provider_call_id is None:
            raise ValueError("Clarification interaction has no parent provider call ID.")
        return record.parent_provider_call_id

