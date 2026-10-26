"""Functional contracts for model-safe deterministic memory search."""

import json

from product.agentic.tools import ToolBox
from product.ai.ai_clients.llm_core.tool_call_batch import ToolCallBatchRuntime
from product.ai.ai_clients.protocols.protocol_chat import (
    BorisChatCompletionMessageFunctionToolCall,
    BorisToolFunction,
    coerce_toolspecs,
)
from product.application.memory_search import (
    MemorySearchFiltersDTO,
    MemorySearchNodeDTO,
    MemorySearchRelationshipDTO,
    MemorySearchResultDTO,
    MemorySearchSeedDTO,
    MemorySearchService,
)
from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.tools.memory_search import build_memory_search_toolbox


class MemorySearchToolBackend:
    """Deterministic fake exposing the internal request received from the tool."""

    def __init__(self) -> None:
        self.seed_backend_ids: list[str] = []

    def semantic_seeds(
        self,
        owner_id: str,
        query: str,
        *,
        filters: MemorySearchFiltersDTO,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        return [
            MemorySearchSeedDTO(
                backend_id="person-a-id",
                label="Person",
                title="Alice Example",
            )
        ]

    def deterministic_seeds(
        self,
        owner_id: str,
        filters: MemorySearchFiltersDTO,
        *,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        self.seed_backend_ids = list(filters.seed_backend_ids)
        return [
            MemorySearchSeedDTO(
                backend_id=backend_id,
                label="Person",
                title="Alice Example",
            )
            for backend_id in filters.seed_backend_ids[:limit]
        ]

    def hydrate(
        self,
        owner_id: str,
        seed_backend_ids: list[str],
        *,
        filters: MemorySearchFiltersDTO,
        depth: int,
        limit: int,
    ) -> MemorySearchResultDTO:
        nodes = [
            MemorySearchNodeDTO(
                backend_id="person-a-id",
                label="Person",
                title="Alice Example",
                summary="A friend from university.",
            ),
            MemorySearchNodeDTO(
                backend_id="person-b-id",
                label="Person",
                title="Bob Example",
                summary="Alice's partner.",
            ),
        ][:limit]
        relationships = []
        if len(nodes) == 2:
            relationships.append(
                MemorySearchRelationshipDTO(
                    backend_id="relationship-id",
                    relationship_type="IN_RELATIONSHIP_WITH",
                    from_backend_id="person-a-id",
                    to_backend_id="person-b-id",
                    summary="Alice and Bob are partners.",
                )
            )
        return MemorySearchResultDTO(
            seed_backend_ids=[value for value in seed_backend_ids if value == "person-a-id"],
            nodes=nodes,
            relationships=relationships,
            truncated=limit < 2,
        )


def _toolbox() -> tuple[ToolBox, MemorySearchToolBackend, ReferenceContext, str]:
    backend = MemorySearchToolBackend()
    context = ReferenceContext()
    seed = context.register_existing(
        "person-a-id",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Alice Example",
    )
    toolbox = build_memory_search_toolbox(
        owner_id="owner-id",
        service=MemorySearchService(backend),
        reference_context=context,
    )
    return toolbox, backend, context, seed.ref


def test_search_memory_schema_exposes_local_refs_but_no_backend_identifiers() -> None:
    toolbox, _backend, _context, _seed_ref = _toolbox()

    provider_schema = coerce_toolspecs(toolbox.definitions)[0]
    serialized_schema = json.dumps(provider_schema)

    assert provider_schema["function"]["name"] == "search_memory"
    assert "seed_refs" in serialized_schema
    assert "seed_backend_ids" not in serialized_schema
    assert "backend_id" not in serialized_schema
    assert "database IDs" in serialized_schema


def test_search_memory_resolves_inputs_and_reuses_refs_across_calls() -> None:
    toolbox, backend, context, seed_ref = _toolbox()
    search_memory = toolbox.tools_mapping["search_memory"]

    first = search_memory(
        filters={"seed_refs": [seed_ref]},
        neighborhood_depth=1,
        limit=2,
    )
    second = search_memory(
        semantic_query="Who is Alice's partner?",
        neighborhood_depth=1,
        limit=2,
    )

    assert backend.seed_backend_ids == ["person-a-id"]
    assert first.seed_refs == [seed_ref]
    assert second.objects[0].ref == first.objects[0].ref == seed_ref
    assert second.objects[1].ref == first.objects[1].ref
    assert first.relationships[0].from_ref == first.objects[0].ref
    assert first.relationships[0].to_ref == first.objects[1].ref
    assert context.resolve(first.relationships[0].ref) == "relationship-id"
    serialized = first.model_dump_json()
    assert "backend_id" not in serialized
    for backend_id in ("person-a-id", "person-b-id", "relationship-id"):
        assert backend_id not in serialized


def test_search_memory_keeps_bounded_result_packet() -> None:
    toolbox, _backend, _context, _seed_ref = _toolbox()

    result = toolbox.tools_mapping["search_memory"](
        semantic_query="Alice",
        limit=1,
    )

    assert len(result.objects) == 1
    assert result.relationships == []
    assert result.truncated is True


def test_unknown_seed_ref_becomes_a_normal_tool_error() -> None:
    toolbox, _backend, _context, _seed_ref = _toolbox()
    runtime = ToolCallBatchRuntime(
        log=lambda _message, _level: None,
        clamp_for_model=lambda content, _model: content,
    )
    tool_call = BorisChatCompletionMessageFunctionToolCall(
        id="search-call",
        type="function",
        function=BorisToolFunction(
            name="search_memory",
            arguments={"filters": {"seed_refs": ["unknown_ref"]}},
        ),
    )

    results = runtime.execute_batch(
        [tool_call],
        toolbox.tools_mapping,
        tools_enabled=True,
        state={"tool_calls_processed": 0, "tool_call_cap": 4},
    )

    assert isinstance(results, list)
    assert results[0].tool_output is not None
    assert results[0].tool_output.status == "error"
    assert results[0].tool_output.error is not None
    assert "Unknown reference" in results[0].tool_output.error.message


def test_backend_failure_is_recoverable_without_exposing_its_identifier() -> None:
    class FailingBackend(MemorySearchToolBackend):
        def semantic_seeds(
            self,
            owner_id: str,
            query: str,
            *,
            filters: MemorySearchFiltersDTO,
            limit: int,
        ) -> list[MemorySearchSeedDTO]:
            raise ValueError("Graph object secret-backend-id was not found.")

    context = ReferenceContext()
    toolbox = build_memory_search_toolbox(
        owner_id="owner-id",
        service=MemorySearchService(FailingBackend()),
        reference_context=context,
    )
    runtime = ToolCallBatchRuntime(
        log=lambda _message, _level: None,
        clamp_for_model=lambda content, _model: content,
    )
    tool_call = BorisChatCompletionMessageFunctionToolCall(
        id="failing-search-call",
        type="function",
        function=BorisToolFunction(
            name="search_memory",
            arguments={"semantic_query": "Find the missing memory"},
        ),
    )

    results = runtime.execute_batch(
        [tool_call],
        toolbox.tools_mapping,
        tools_enabled=True,
        state={"tool_calls_processed": 0, "tool_call_cap": 4},
    )

    assert isinstance(results, list)
    assert results[0].tool_output is not None
    assert results[0].tool_output.error is not None
    assert "Verify labels" in results[0].tool_output.error.message
    assert "secret-backend-id" not in results[0].tool_output.error.message
