from enum import StrEnum

from pydantic import BaseModel, Field

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_chat import coerce_toolspecs
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO


class MemorySearchMode(StrEnum):
    semantic = "semantic"
    exact = "exact"


class MemorySearchInputDTO(BaseModel):
    query: str = Field(description="The user's question or phrase to search for.")
    mode: MemorySearchMode = Field(description="Whether to search by meaning or exact wording.")


class MemorySearchOutputDTO(BaseModel):
    summary: str = Field(description="Brief answer grounded in matching memories.")


def search_memory(input_dto: MemorySearchInputDTO) -> MemorySearchOutputDTO:
    return MemorySearchOutputDTO(summary=f"Found results for {input_dto.query}.")


def test_tool_definition_and_handler_share_typed_input_and_output_contracts() -> None:
    definition = ToolDefinitionDTO[MemorySearchInputDTO](
        name="search_memory",
        description="Find memories relevant to the user's question.",
        input_model=MemorySearchInputDTO,
    )
    registered_tool = RegisteredTool[MemorySearchInputDTO, MemorySearchOutputDTO](
        definition=definition,
        handler=search_memory,
    )

    input_schema = registered_tool.definition.input_model.model_json_schema()
    input_dto = registered_tool.definition.input_model(query="a trip", mode="semantic")
    output_dto = registered_tool.handler(input_dto)

    assert input_schema["properties"]["query"]["description"] == (
        "The user's question or phrase to search for."
    )
    mode_schema = input_schema["$defs"]["MemorySearchMode"]
    assert mode_schema["enum"] == ["semantic", "exact"]
    assert isinstance(output_dto, MemorySearchOutputDTO)
    assert output_dto.summary == "Found results for a trip."


def test_toolbox_derives_provider_definitions_and_validating_mapping_from_same_tools() -> None:
    definition = ToolDefinitionDTO[MemorySearchInputDTO](
        name="search_memory",
        description="Find memories relevant to the user's question.",
        input_model=MemorySearchInputDTO,
    )
    toolbox = ToolBox(
        "memory_query",
        [RegisteredTool(definition=definition, handler=search_memory)],
    )

    assert toolbox.definitions == [definition]
    assert set(toolbox.tools_mapping) == {definition.name}
    schema = coerce_toolspecs(toolbox.definitions)[0]["function"]["parameters"]
    assert schema["properties"]["query"]["description"] == (
        "The user's question or phrase to search for."
    )
    assert schema["$defs"]["MemorySearchMode"]["enum"] == ["semantic", "exact"]
    result = toolbox.tools_mapping[definition.name](query="a trip", mode="semantic")
    assert isinstance(result, MemorySearchOutputDTO)
    assert result.summary == "Found results for a trip."


def test_toolbox_rejects_duplicate_names_before_call_configuration() -> None:
    definition = ToolDefinitionDTO[MemorySearchInputDTO](
        name="search_memory",
        description="Find memories relevant to the user's question.",
        input_model=MemorySearchInputDTO,
    )
    registration = RegisteredTool(definition=definition, handler=search_memory)

    try:
        ToolBox("memory_query", [registration, registration])
    except ValueError as error:
        assert "duplicate tool name 'search_memory'" in str(error)
    else:
        raise AssertionError("duplicate tool names must not be ambiguous")


def test_toolbox_validates_child_state_arguments_before_invoking_handler() -> None:
    class ChildInvocationInputDTO(BaseModel):
        request: str = Field(description="The request passed to the child state.")

    class ChildInvocationOutputDTO(BaseModel):
        answer: str

    class ChildState:
        def invoke(self, request: str) -> ChildInvocationOutputDTO:
            return ChildInvocationOutputDTO(answer=f"Child handled: {request}")

    child = ChildState()

    def invoke_child(input_dto: ChildInvocationInputDTO) -> ChildInvocationOutputDTO:
        return child.invoke(request=input_dto.request)

    definition = ToolDefinitionDTO[ChildInvocationInputDTO](
        name="delegate",
        description="Delegate a focused request to the child state.",
        input_model=ChildInvocationInputDTO,
    )
    toolbox = ToolBox(
        "parent",
        [RegisteredTool(definition=definition, handler=invoke_child)],
    )

    output = toolbox.tools_mapping["delegate"](request="summarize this")
    assert output == ChildInvocationOutputDTO(answer="Child handled: summarize this")
