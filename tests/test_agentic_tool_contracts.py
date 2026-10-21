from enum import StrEnum

from pydantic import BaseModel, Field

from product.agentic.tools import RegisteredTool, ToolDefinitionDTO


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
