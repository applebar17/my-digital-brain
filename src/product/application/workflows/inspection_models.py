"""Read-only contracts exposed by the local workflow inspector."""

from typing import Literal

from pydantic import BaseModel, Field


class FieldInspectionDTO(BaseModel):
    name: str
    type_name: str
    description: str | None
    required: bool


class ModelInspectionDTO(BaseModel):
    name: str
    fields: list[FieldInspectionDTO]


class ChildStateInspectionDTO(BaseModel):
    """Configured child state exposed by one agent-as-tool registration."""

    state_id: str
    toolbox_name: str | None
    tools: list["ToolInspectionDTO"] = Field(default_factory=list)


class ToolInspectionDTO(BaseModel):
    name: str
    description: str
    input_model: ModelInspectionDTO
    output_model: ModelInspectionDTO | None
    child_state: ChildStateInspectionDTO | None = None


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


class ConfiguredStateInspectionDTO(BaseModel):
    """One currently assembled AI state and its functional contracts."""

    state_id: str
    title: str
    description: str
    input_model: ModelInspectionDTO
    output_model: ModelInspectionDTO | None
    agentic: AgenticInspectionDTO


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


class ApplicationConfigurationInspectionDTO(BaseModel):
    """Current state and workflow composition rendered by the local inspector."""

    states: list[ConfiguredStateInspectionDTO]
    workflows: list[WorkflowInspectionDTO]
