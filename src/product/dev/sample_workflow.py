"""Inspectable sample composition until a product workflow is assembled."""

from pydantic import BaseModel, Field

from product.agentic.contracts.state import AgenticStageConfigurationDTO, AgenticStateInvocationDTO
from product.agentic.tools.contracts import RegisteredTool
from product.agentic.tools.toolbox import ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.workflows import BaseWorkflow, WorkflowContext, WorkflowStep


class SampleRequestDTO(BaseModel):
    text: str = Field(description="User-provided memory text.")


class PreparedSourceDTO(BaseModel):
    source_text: str = Field(description="Normalized source text supplied to the AI state.")


class InterpretationDTO(BaseModel):
    summary: str = Field(description="Concise interpretation of the supplied memory.")
    gaps: list[str] = Field(description="Material gaps identified from the source.")


class ReferenceLookupInputDTO(BaseModel):
    name: str = Field(description="Name or alias to look up in bounded context.")


class ReferenceLookupOutputDTO(BaseModel):
    possible_matches: list[str] = Field(
        description="Possible existing references, not identity decisions."
    )


def _lookup_reference(request: ReferenceLookupInputDTO) -> ReferenceLookupOutputDTO:
    return ReferenceLookupOutputDTO(possible_matches=[])


def _prepare_input(context: WorkflowContext) -> SampleRequestDTO:
    return SampleRequestDTO.model_validate(context.request)


def _prepare_source(request: SampleRequestDTO) -> PreparedSourceDTO:
    return PreparedSourceDTO(source_text=request.text.strip())


def _interpretation_input(context: WorkflowContext) -> PreparedSourceDTO:
    return PreparedSourceDTO.model_validate(context.results["prepare"])


def _not_yet_wired(_: PreparedSourceDTO) -> InterpretationDTO:
    raise NotImplementedError("The sample AI state is configuration-only; no provider is called.")


def sample_workflow() -> BaseWorkflow:
    """Assemble a truthful example of the future configuration inspection surface."""
    toolbox = ToolBox(
        "sample_read_tools",
        [
            RegisteredTool(
                definition=ToolDefinitionDTO(
                    name="lookup_reference",
                    description="Look up possible existing references before an identity decision.",
                    input_model=ReferenceLookupInputDTO,
                ),
                handler=_lookup_reference,
            )
        ],
    )
    configuration = AgenticStateInvocationDTO(
        system_prompt="Interpret the supplied memory. Do not claim that a lookup proves identity.",
        request="Interpret the prepared source.",
        response_model=InterpretationDTO,
        toolbox=toolbox,
        reasoning_stage=AgenticStageConfigurationDTO(
            system_prompt="Identify facts, ambiguities, and possible context gaps.",
            response_model=InterpretationDTO,
        ),
    )
    return BaseWorkflow(
        workflow_id="sample_memory_ingestion",
        description=(
            "Configuration sample only. The AI handler is intentionally not wired to a provider; "
            "real ingestion states will replace it as they are implemented."
        ),
        steps=[
            WorkflowStep(
                step_id="prepare",
                title="Prepare source",
                description="Normalize the source before interpretation.",
                make_input=_prepare_input,
                handler=_prepare_source,
            ),
            WorkflowStep(
                step_id="interpret",
                title="Interpret memory",
                description="Example AI state configuration; not yet executable in this sample.",
                make_input=_interpretation_input,
                handler=_not_yet_wired,
                depends_on=("prepare",),
                kind="agentic",
                state_id="sample_interpretation",
                configuration=configuration,
            ),
        ],
    )
