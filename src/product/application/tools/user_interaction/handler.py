"""Deterministic handler for questions that await a user response."""

from product.ai.ai_clients.protocols.protocol_tools import ToolInteractionRequestDTO
from product.application.interactions import (
    PendingUserQuestionDTO,
    UserInteractionService,
    UserQuestionRequestDTO,
)


class AskUserToolHandler:
    """Create an external interaction request through the application service."""

    def __init__(self, service: UserInteractionService) -> None:
        self.service = service

    def ask_user(
        self,
        request: UserQuestionRequestDTO,
    ) -> ToolInteractionRequestDTO[PendingUserQuestionDTO]:
        """Return a typed pause request for the generic AI client tool loop.

        Dependencies:
            `UserInteractionService` owns interaction identity and deadline.
            The generic client/runtime owns provider call correlation and pause.
        """
        return ToolInteractionRequestDTO(
            interaction_packet=self.service.create_question(request)
        )

