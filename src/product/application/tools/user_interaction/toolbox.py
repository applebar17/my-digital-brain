"""Registration of the deterministic `ask_user` tool."""

from product.agentic.tools import RegisteredTool
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.interactions import (
    UserInteractionService,
    UserQuestionRequestDTO,
    UserQuestionResolutionDTO,
)
from product.application.tools.user_interaction.handler import AskUserToolHandler


def build_ask_user_tool(
    service: UserInteractionService,
) -> RegisteredTool[
    UserQuestionRequestDTO,
    UserQuestionResolutionDTO,
]:
    """Bind the shared interaction service to one model-visible question tool."""
    handler = AskUserToolHandler(service)
    return RegisteredTool[UserQuestionRequestDTO, UserQuestionResolutionDTO](
        definition=ToolDefinitionDTO(
            name="ask_user",
            description=(
                "Ask the user one concise question when supplied context cannot resolve the "
                "current doubt. Configure it as free response, confirmation, single choice, "
                "or multiple choice; never expose internal references in the question."
            ),
            input_model=UserQuestionRequestDTO,
        ),
        handler=handler.ask_user,
    )

