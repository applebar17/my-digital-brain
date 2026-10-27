"""Deterministic creation of backend-owned user interactions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from product.application.interactions.models import (
    PendingUserQuestionDTO,
    QuestionMode,
    UserQuestionRequestDTO,
)


class UserInteractionService:
    """Create pending question packets with a configurable backend deadline."""

    def __init__(self, *, response_timeout: timedelta = timedelta(minutes=15)) -> None:
        if response_timeout <= timedelta(0):
            raise ValueError("User interaction response timeout must be greater than zero.")
        self.response_timeout = response_timeout

    def create_question(self, request: UserQuestionRequestDTO) -> PendingUserQuestionDTO:
        """Create one interaction attempt without persisting or rendering it.

        Dependencies:
            The caller supplies LLM-authored question content. The service owns the
            backend interaction identifier and deadline; Task 4.2.2 supplies the
            persistence and channel adapters that store and resolve this packet.
        """
        choice_modes = {QuestionMode.SINGLE_CHOICE, QuestionMode.MULTIPLE_CHOICE}
        if request.mode in choice_modes and not request.options:
            raise ValueError(
                "A choice question needs at least one understandable option. "
                "Provide options or use free_response."
            )
        if request.mode not in choice_modes and request.options:
            raise ValueError(
                "Options are only used with single_choice or multiple_choice. "
                "Remove them or change the mode."
            )
        return PendingUserQuestionDTO(
            interaction_ref=str(uuid4()),
            clarification_ref=request.clarification_ref,
            question=request.question,
            mode=request.mode,
            options=[
                {
                    **option.model_dump(),
                    "option_ref": str(uuid4()),
                }
                for option in request.options
            ],
            allow_other=request.mode != QuestionMode.FREE_RESPONSE,
            deadline=datetime.now(UTC) + self.response_timeout,
        )

