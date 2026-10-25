"""Project assembled workflow and agentic configuration into read-only DTOs."""

from collections.abc import Callable
from functools import partial
from inspect import signature
from typing import Any, Literal, get_origin, get_type_hints

from pydantic import BaseModel, Field

from product.agentic.contracts.state import AgenticStageConfigurationDTO, AgenticStateInvocationDTO
from product.agentic.tools.toolbox import ToolBox
from product.application.workflows.base import BaseWorkflow, WorkflowStep


class FieldInspectionDTO(BaseModel):
    name: str
    type_name: str
    description: str | None
    required: bool


class ModelInspectionDTO(BaseModel):
    name: str
    fields: list[FieldInspectionDTO]


class ToolInspectionDTO(BaseModel):
    name: str
    description: str
    input_model: ModelInspectionDTO
    output_model: ModelInspectionDTO | None


class StageInspectionDTO(BaseModel):
    system_prompt: str
    response_model: ModelInspectionDTO | None
    toolbox_name: str | None
    tools: list[ToolInspectionDTO] = Field(default_factory=list)
    parallel_tool_calls: bool | None


class AgenticInspectionDTO(BaseModel):
    state_id: str
    invocation_request: str
    main: StageInspectionDTO
    reasoning: StageInspectionDTO | None
    planning: StageInspectionDTO | None


class StepInspectionDTO(BaseModel):
    step_id: str
    title: str
    description: str
    kind: Literal["deterministic", "agentic"]
    depends_on: list[str]
    input_model: ModelInspectionDTO
    output_model: ModelInspectionDTO
    agentic: AgenticInspectionDTO | None


class WorkflowInspectionDTO(BaseModel):
    workflow_id: str
    description: str
    steps: list[StepInspectionDTO]


def inspect_workflow(workflow: BaseWorkflow) -> WorkflowInspectionDTO:
    """Read live step, state, and toolbox objects; do not maintain a shadow diagram."""
    return WorkflowInspectionDTO(
        workflow_id=workflow.workflow_id,
        description=workflow.description,
        steps=[_inspect_step(step) for step in workflow.steps],
    )


def _inspect_step(step: WorkflowStep) -> StepInspectionDTO:
    input_model, output_model = _handler_models(step.handler)
    agentic = None
    if step.configuration is not None and step.state_id is not None:
        agentic = _agentic_configuration(step.state_id, step.configuration)
    return StepInspectionDTO(
        step_id=step.step_id,
        title=step.title,
        description=step.description,
        kind=step.kind,
        depends_on=list(step.depends_on),
        input_model=_model_contract(input_model),
        output_model=_model_contract(output_model),
        agentic=agentic,
    )


def _handler_models(handler: Callable[..., Any]) -> tuple[type[BaseModel], type[BaseModel]]:
    """Derive the handoff contracts from the handler's annotated DTOs."""
    target = handler.func if isinstance(handler, partial) else handler
    parameters = list(signature(handler).parameters.values())
    hints = get_type_hints(target)
    if len(parameters) != 1:
        raise TypeError(f"Workflow handler '{target}' must accept exactly one input DTO.")
    input_type = hints.get(parameters[0].name)
    output_type = hints.get("return")
    if not _is_model_type(input_type) or not _is_model_type(output_type):
        raise TypeError(f"Workflow handler '{target}' needs Pydantic input and output annotations.")
    return input_type, output_type


def _is_model_type(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def _model_contract(model: type[BaseModel]) -> ModelInspectionDTO:
    return ModelInspectionDTO(
        name=model.__name__,
        fields=[
            FieldInspectionDTO(
                name=name,
                type_name=(
                    getattr(field.annotation, "__name__", str(field.annotation))
                    if get_origin(field.annotation) is None
                    else str(field.annotation)
                ),
                description=field.description,
                required=field.is_required(),
            )
            for name, field in model.model_fields.items()
        ],
    )


def _toolbox_contract(toolbox: ToolBox | None) -> tuple[str | None, list[ToolInspectionDTO]]:
    if toolbox is None:
        return None, []
    tools = []
    for registered in toolbox.tools_by_name.values():
        target = (
            registered.handler.func
            if isinstance(registered.handler, partial)
            else registered.handler
        )
        output_type = get_type_hints(target).get("return")
        tools.append(
            ToolInspectionDTO(
                name=registered.definition.name,
                description=registered.definition.description,
                input_model=_model_contract(registered.definition.input_model),
                output_model=_model_contract(output_type) if _is_model_type(output_type) else None,
            )
        )
    return toolbox.name, tools


def _stage_configuration(stage: AgenticStageConfigurationDTO) -> StageInspectionDTO:
    toolbox_name, tools = _toolbox_contract(stage.toolbox)
    return StageInspectionDTO(
        system_prompt=stage.system_prompt,
        response_model=_model_contract(stage.response_model),
        toolbox_name=toolbox_name,
        tools=tools,
        parallel_tool_calls=stage.parallel_tool_calls,
    )


def _agentic_configuration(
    state_id: str, config: AgenticStateInvocationDTO
) -> AgenticInspectionDTO:
    toolbox_name, tools = _toolbox_contract(config.toolbox)
    return AgenticInspectionDTO(
        state_id=state_id,
        invocation_request=config.request,
        main=StageInspectionDTO(
            system_prompt=config.system_prompt,
            response_model=(
                _model_contract(config.response_model) if config.response_model else None
            ),
            toolbox_name=toolbox_name,
            tools=tools,
            parallel_tool_calls=config.parallel_tool_calls,
        ),
        reasoning=_stage_configuration(config.reasoning_stage) if config.reasoning_stage else None,
        planning=_stage_configuration(config.planning_stage) if config.planning_stage else None,
    )
