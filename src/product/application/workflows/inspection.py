"""Project assembled workflow and agentic configuration into read-only DTOs."""

from collections.abc import Callable, Mapping
from functools import partial
from inspect import signature
from typing import Any, get_origin, get_type_hints

from pydantic import BaseModel

from product.agentic.contracts.state import AgenticStageConfigurationDTO, AgenticStateInvocationDTO
from product.agentic.tools.toolbox import ToolBox
from product.application.workflows.base import BaseWorkflow, WorkflowStep
from product.application.workflows.inspection_models import (
    AgenticInspectionDTO,
    ChildStateInspectionDTO,
    ConfiguredStateInspectionDTO,
    FieldInspectionDTO,
    ModelInspectionDTO,
    StageInspectionDTO,
    StepInspectionDTO,
    ToolInspectionDTO,
    WorkflowInspectionDTO,
)


def inspect_workflow(
    workflow: BaseWorkflow,
    state_configurations: Mapping[str, AgenticStateInvocationDTO] | None = None,
) -> WorkflowInspectionDTO:
    """Read live step, state, and toolbox objects; do not maintain a shadow diagram."""
    configurations = state_configurations or {}
    return WorkflowInspectionDTO(
        workflow_id=workflow.workflow_id,
        description=workflow.description,
        steps=[_inspect_step(step, configurations) for step in workflow.steps],
    )


def inspect_configured_state(
    *,
    state_id: str,
    title: str,
    description: str,
    input_model: type[BaseModel],
    configuration: AgenticStateInvocationDTO,
) -> ConfiguredStateInspectionDTO:
    """Project one actual state invocation configuration for local inspection."""
    agentic = _agentic_configuration(state_id, configuration)
    return ConfiguredStateInspectionDTO(
        state_id=state_id,
        title=title,
        description=description,
        input_model=_model_contract(input_model),
        output_model=(
            _model_contract(configuration.response_model)
            if configuration.response_model is not None
            else None
        ),
        agentic=agentic,
    )


def _inspect_step(
    step: WorkflowStep,
    state_configurations: Mapping[str, AgenticStateInvocationDTO],
) -> StepInspectionDTO:
    input_model, output_model = _handler_models(step.handler)
    agentic = None
    if step.state_id is not None:
        configuration = step.configuration or state_configurations.get(step.state_id)
        if configuration is not None:
            agentic = _agentic_configuration(step.state_id, configuration)
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
    target = _callable_target(handler)
    parameters = list(signature(target).parameters.values())
    hints = get_type_hints(target)
    if len(parameters) not in {1, 2}:
        raise TypeError(
            f"Workflow handler '{target}' must accept one input DTO and optional context."
        )
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
        target = _callable_target(registered.handler)
        output_type = get_type_hints(target).get("return")
        handler_owner = getattr(registered.handler, "__self__", registered.handler)
        child_state = getattr(handler_owner, "state", None)
        child_inspection = None
        if child_state is not None:
            child_toolbox_name, child_tools = _toolbox_contract(
                getattr(child_state, "toolbox", None)
            )
            child_inspection = ChildStateInspectionDTO(
                state_id=child_state.state_id,
                toolbox_name=child_toolbox_name,
                tools=child_tools,
            )
        tools.append(
            ToolInspectionDTO(
                name=registered.definition.name,
                description=registered.definition.description,
                input_model=_model_contract(registered.definition.input_model),
                output_model=_model_contract(output_type) if _is_model_type(output_type) else None,
                child_state=child_inspection,
            )
        )
    return toolbox.name, tools


def inspect_toolbox(toolbox: ToolBox) -> list[ToolInspectionDTO]:
    """Expose actual registered tools and nested agent-as-tool composition."""
    return _toolbox_contract(toolbox)[1]


def _callable_target(handler: Callable[..., Any]) -> Callable[..., Any]:
    if isinstance(handler, partial):
        return handler.func
    contextual_invoke = getattr(handler, "invoke_with_context", None)
    if callable(contextual_invoke):
        return contextual_invoke
    if not hasattr(handler, "__name__") and callable(handler):
        return handler.__call__
    return handler


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
