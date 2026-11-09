"""Functional MemoryLog and Perception write-state boundaries."""

from pathlib import Path
from typing import cast

from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import Msg
from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.states.ingestion import IngestionReasoningResultDTO
from product.application.states.ingestion.memory_context import (
    MemoryContextWriteInputDTO,
    MemoryContextWriteState,
)
from product.application.tools.memory_context import build_memory_context_toolbox
from product.graph import (
    CreatePerceptionPersistenceDTO,
    GraphMemoryRepository,
    GraphMemoryService,
    MemoryLogWriteDTO,
    StoredMemoryLogDTO,
    StoredPerceptionDTO,
)
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class InMemoryGraphMemoryRepository(GraphMemoryRepository):
    """Capture trusted persistence payloads for functional tool tests."""

    def __init__(self) -> None:
        self.memory_logs: list[MemoryLogWriteDTO] = []
        self.perceptions: list[CreatePerceptionPersistenceDTO] = []

    def create_memory_log(
        self,
        owner_id: str,
        memory_log: MemoryLogWriteDTO,
    ) -> StoredMemoryLogDTO:
        self.memory_logs.append(memory_log)
        return StoredMemoryLogDTO(
            backend_id=f"memory-backend-{len(self.memory_logs)}",
            memory_log=memory_log,
        )

    def create_perception(
        self,
        owner_id: str,
        request: CreatePerceptionPersistenceDTO,
    ) -> StoredPerceptionDTO:
        self.perceptions.append(request)
        return StoredPerceptionDTO(
            backend_id=f"perception-backend-{len(self.perceptions)}",
            perception=request.perception,
        )


def _reasoning() -> IngestionReasoningResultDTO:
    return IngestionReasoningResultDTO(
        summary="The owner remembers a joyful lunch with Jacopo.",
        clarification_points=[],
        entity_observations=["Jacopo is involved."],
        alias_observations=[],
        relationship_observations=[],
        episodic_details=["The lunch felt joyful."],
    )


def test_memory_and_perception_tools_resolve_refs_and_bind_created_objects() -> None:
    reference_context = ReferenceContext()
    owner = reference_context.register_owner(
        "owner-backend",
        name="Mario",
        surname="Rossi",
    )
    person = reference_context.register_existing(
        "jacopo-backend",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Jacopo Brutti",
    )
    repository = InMemoryGraphMemoryRepository()
    toolbox = build_memory_context_toolbox(
        owner_id="owner-backend",
        service=GraphMemoryService(repository),
        reference_context=reference_context,
    )

    memory = toolbox.tools_by_name["create_memory_log"].invoke(
        title="Lunch with Jacopo",
        summary="Mario remembers a joyful lunch with Jacopo.",
        log_kind="episode",
        primary_host_ref=owner.id,
        involved_refs=[person.ref],
        happened_at="last Saturday",
        time_precision="day",
        original_user_words="a really joyful lunch",
    )
    perception = toolbox.tools_by_name["create_perception"].invoke(
        target_ref=person.ref,
        description="Mario experiences Jacopo as warm and welcoming.",
        perception_type="impression",
        emotional_valence="positive",
        emotion_tags=["warmth", "joy"],
        original_user_words="warm and welcoming",
        happened_at=None,
    )

    assert repository.memory_logs[0].primary_host_backend_id == "owner-backend"
    assert repository.memory_logs[0].involved_backend_ids == ["jacopo-backend"]
    assert repository.perceptions[0].target_backend_id == "jacopo-backend"
    assert reference_context.resolve(memory.object_ref) == "memory-backend-1"
    assert reference_context.resolve(perception.object_ref) == "perception-backend-1"
    assert memory.object_ref.startswith("memory_new_")
    assert perception.object_ref.startswith("context_new_")


def test_memory_context_state_exposes_only_typed_memory_and_perception_tools() -> None:
    reference_context = ReferenceContext()
    owner = reference_context.register_owner(
        "owner-backend",
        name="Mario",
        surname="Rossi",
    )
    reference_context.register_existing(
        "jacopo-backend",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Jacopo Brutti",
    )
    history = AgenticHistorySession(
        [Msg(role="user", content="I had a joyful lunch with Jacopo.")]
    )
    parent = history.start_state("conversation_entry", history.master_history)
    invocation_context = AgenticToolInvocationContext(
        history_session=history,
        parent_state_run_id=parent.state_run_id,
        parent_provider_call_id="ingest-call",
    )
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    state = MemoryContextWriteState(
        cast(LLMInterfaceCore, object()),
        history,
        PromptService(FilePromptTemplateSource(templates_root), PromptRenderer()),
        owner_id="owner-backend",
        graph_memory_service=GraphMemoryService(InMemoryGraphMemoryRepository()),
        reference_context=reference_context,
    )
    configuration = state.build_invocation(
        MemoryContextWriteInputDTO(
            reasoning=_reasoning(),
            node_resolution_results=[],
            owner=owner,
            references=reference_context.entries(),
        ),
        invocation_context,
    )

    assert configuration.parallel_tool_calls is True
    assert configuration.toolbox is not None
    assert list(configuration.toolbox.tools_by_name) == [
        "create_memory_log",
        "create_perception",
    ]
    perception_schema = configuration.toolbox.tools_by_name[
        "create_perception"
    ].definition.input_model.model_json_schema()
    assert "target_ref" in str(perception_schema)
    assert "target_backend_id" not in str(perception_schema)
    assert "RelationshipContext" not in configuration.system_prompt
    assert "relationship contexts" in configuration.system_prompt
    assert "owner-backend" not in configuration.system_prompt
    assert "jacopo-backend" not in configuration.system_prompt
    assert "Jacopo Brutti" in configuration.system_prompt
