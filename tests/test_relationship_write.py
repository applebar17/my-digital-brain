"""Functional relationship edge, context, state, and consumption behavior."""

from pathlib import Path
from typing import cast

import pytest

from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import Msg
from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.relationships import RelationshipContextProjectionService
from product.application.states.ingestion import (
    IngestionReasoningResultDTO,
    MemoryContextWriteResultDTO,
    RelationshipWriteInputDTO,
    RelationshipWriteState,
)
from product.application.tools.relationship_write import build_relationship_toolbox
from product.graph import (
    AppendRelationshipStatePersistenceDTO,
    CreateRelationshipContextPersistenceDTO,
    CreateRelationshipPersistenceDTO,
    GraphRelationshipRepository,
    GraphRelationshipService,
    RelationshipContextDetailDTO,
    StoredDirectRelationshipDTO,
    StoredRelationshipContextDTO,
    StoredRelationshipStateDTO,
    UpdateRelationshipPersistenceDTO,
)
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class InMemoryRelationshipRepository(GraphRelationshipRepository):
    """Exercise relationship semantics without storage implementation details."""

    def __init__(self) -> None:
        self.relationships: dict[tuple[str, str, str], StoredDirectRelationshipDTO] = {}
        self.contexts: dict[tuple[str, tuple[str, ...], str], StoredRelationshipContextDTO] = {}
        self.states: dict[tuple[str, str], StoredRelationshipStateDTO] = {}

    def create_or_get_relationship(
        self,
        owner_id: str,
        request: CreateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO:
        key = (
            request.from_backend_id,
            request.relationship.relationship_type.value,
            request.to_backend_id,
        )
        existing = self.relationships.get(key)
        if existing is not None:
            return existing.model_copy(update={"created": False})
        stored = StoredDirectRelationshipDTO(
            backend_id=f"edge-{len(self.relationships) + 1}",
            from_backend_id=request.from_backend_id,
            to_backend_id=request.to_backend_id,
            relationship=request.relationship,
            created=True,
        )
        self.relationships[key] = stored
        return stored

    def update_relationship(
        self,
        owner_id: str,
        request: UpdateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO:
        key, existing = next(
            item
            for item in self.relationships.items()
            if item[1].backend_id == request.relationship_backend_id
        )
        updates = request.patch.model_dump(exclude_none=True)
        stored = existing.model_copy(
            update={
                "relationship": existing.relationship.model_copy(update=updates),
                "created": False,
            }
        )
        self.relationships[key] = stored
        return stored

    def create_or_get_context(
        self,
        owner_id: str,
        request: CreateRelationshipContextPersistenceDTO,
    ) -> StoredRelationshipContextDTO:
        key = (
            owner_id,
            tuple(sorted(request.participant_backend_ids)),
            request.context.category.value,
        )
        existing = self.contexts.get(key)
        if existing is not None:
            memories = list(
                dict.fromkeys(
                    [*existing.memory_log_backend_ids, *request.memory_log_backend_ids]
                )
            )
            reused = existing.model_copy(
                update={"memory_log_backend_ids": memories, "created": False}
            )
            self.contexts[key] = reused
            return reused
        stored = StoredRelationshipContextDTO(
            backend_id=f"context-{len(self.contexts) + 1}",
            participant_backend_ids=sorted(request.participant_backend_ids),
            memory_log_backend_ids=list(request.memory_log_backend_ids),
            context=request.context,
            created=True,
        )
        self.contexts[key] = stored
        return stored

    def append_state(
        self,
        owner_id: str,
        request: AppendRelationshipStatePersistenceDTO,
    ) -> StoredRelationshipStateDTO:
        fingerprint = request.state.model_dump_json()
        key = (request.context_backend_id, fingerprint)
        existing = self.states.get(key)
        if existing is not None:
            return existing.model_copy(update={"created": False})
        stored = StoredRelationshipStateDTO(
            backend_id=f"state-{len(self.states) + 1}",
            context_backend_id=request.context_backend_id,
            memory_log_backend_ids=list(request.memory_log_backend_ids),
            state=request.state,
            created=True,
        )
        self.states[key] = stored
        return stored

    def get_context_detail(
        self,
        owner_id: str,
        context_backend_id: str,
        *,
        state_limit: int,
    ) -> RelationshipContextDetailDTO:
        context = next(
            item for item in self.contexts.values() if item.backend_id == context_backend_id
        )
        states = [
            state
            for state in reversed(list(self.states.values()))
            if state.context_backend_id == context_backend_id
        ][:state_limit]
        return RelationshipContextDetailDTO(
            relationship_context=context.model_copy(update={"created": False}),
            states=[state.model_copy(update={"created": False}) for state in states],
        )


def _reasoning() -> IngestionReasoningResultDTO:
    return IngestionReasoningResultDTO(
        summary="Mario and Elena are partners and became closer in 2026.",
        clarification_points=[],
        entity_observations=["Elena is a resolved person."],
        alias_observations=[],
        relationship_observations=["Mario and Elena have a romantic relationship."],
        episodic_details=[],
    )


def _references() -> tuple[ReferenceContext, str, str, str]:
    context = ReferenceContext()
    owner = context.register_owner("owner-backend", name="Mario", surname="Rossi")
    elena = context.register_existing(
        "elena-backend",
        object_kind=ReferenceObjectKind.NODE,
        label="Person",
        display_name="Elena Verdi",
    )
    memory = context.register_existing(
        "memory-backend",
        object_kind=ReferenceObjectKind.MEMORY_LOG,
        label="MemoryLog",
        display_name="A closer relationship",
    )
    return context, owner.id, elena.ref, memory.ref


def test_relationship_tools_reuse_edges_contexts_and_identical_states() -> None:
    references, owner_ref, elena_ref, memory_ref = _references()
    repository = InMemoryRelationshipRepository()
    toolbox = build_relationship_toolbox(
        owner_id="owner-backend",
        service=GraphRelationshipService(repository),
        reference_context=references,
    )
    tool = toolbox.tools_by_name["write_relationship"]

    direct_arguments = {
        "action": {
            "operation": "create_direct",
            "relationship_type": "KNOWS",
            "from_ref": owner_ref,
            "to_ref": elena_ref,
            "description": "Mario knows Elena.",
            "relationship_detail": None,
            "valid_from": None,
            "valid_to": None,
            "original_user_words": None,
        }
    }
    direct = tool.invoke(**direct_arguments)
    repeated_direct = tool.invoke(**direct_arguments)
    assert direct.object_ref == repeated_direct.object_ref
    assert repeated_direct.outcome == "reused"

    context_arguments = {
        "action": {
            "operation": "create_or_reuse_context",
            "participant_refs": [owner_ref, elena_ref],
            "category": "romantic",
            "description": "Mario and Elena are romantic partners.",
            "relationship_kind": "partners",
            "original_user_words": "we are together",
            "memory_refs": [memory_ref],
        }
    }
    relationship_context = tool.invoke(**context_arguments)
    repeated_context = tool.invoke(**context_arguments)
    assert relationship_context.object_ref == repeated_context.object_ref
    assert repeated_context.outcome == "reused"

    state_arguments = {
        "action": {
            "operation": "append_state",
            "context_ref": relationship_context.object_ref,
            "status": "together",
            "closeness": "closer",
            "description": "They became closer during 2026.",
            "emotional_summary": "A warm and growing bond.",
            "emotional_valence": "positive",
            "emotion_tags": ["warmth"],
            "original_user_words": "we became closer",
            "valid_from": "2026",
            "valid_to": None,
            "time_precision": "year",
            "memory_refs": [memory_ref],
        }
    }
    state = tool.invoke(**state_arguments)
    repeated_state = tool.invoke(**state_arguments)
    assert state.object_ref == repeated_state.object_ref
    assert repeated_state.outcome == "reused"
    assert len(repository.relationships) == 1
    assert len(repository.contexts) == 1
    assert len(repository.states) == 1


def test_relationship_endpoint_validation_and_empty_state_are_actionable() -> None:
    references, owner_ref, elena_ref, memory_ref = _references()
    tool = build_relationship_toolbox(
        owner_id="owner-backend",
        service=GraphRelationshipService(InMemoryRelationshipRepository()),
        reference_context=references,
    ).tools_by_name["write_relationship"]

    with pytest.raises(ValueError, match="WORKS_AT requires"):
        tool.invoke(
            action={
                "operation": "create_direct",
                "relationship_type": "WORKS_AT",
                "from_ref": owner_ref,
                "to_ref": elena_ref,
                "description": None,
                "relationship_detail": None,
                "valid_from": None,
                "valid_to": None,
                "original_user_words": None,
            }
        )
    relationship_context = tool.invoke(
        action={
            "operation": "create_or_reuse_context",
            "participant_refs": [owner_ref, elena_ref],
            "category": "friendship",
            "description": "Mario and Elena know each other.",
            "relationship_kind": "friends",
            "original_user_words": None,
            "memory_refs": [memory_ref],
        }
    )
    with pytest.raises(ValueError, match="empty initial state"):
        tool.invoke(
            action={
                "operation": "append_state",
                "context_ref": relationship_context.object_ref,
                "status": None,
                "closeness": None,
                "description": None,
                "emotional_summary": None,
                "emotional_valence": None,
                "emotion_tags": [],
                "original_user_words": None,
                "valid_from": None,
                "valid_to": None,
                "time_precision": None,
                "memory_refs": [memory_ref],
            }
        )


def test_relationship_state_configuration_and_consumption_are_model_safe() -> None:
    references, owner_ref, elena_ref, memory_ref = _references()
    repository = InMemoryRelationshipRepository()
    service = GraphRelationshipService(repository)
    tool = build_relationship_toolbox(
        owner_id="owner-backend",
        service=service,
        reference_context=references,
    ).tools_by_name["write_relationship"]
    context_result = tool.invoke(
        action={
            "operation": "create_or_reuse_context",
            "participant_refs": [owner_ref, elena_ref],
            "category": "romantic",
            "description": "Mario and Elena are partners.",
            "relationship_kind": "partners",
            "original_user_words": None,
            "memory_refs": [memory_ref],
        }
    )
    tool.invoke(
        action={
            "operation": "append_state",
            "context_ref": context_result.object_ref,
            "status": "together",
            "closeness": None,
            "description": None,
            "emotional_summary": None,
            "emotional_valence": None,
            "emotion_tags": [],
            "original_user_words": None,
            "valid_from": "2026",
            "valid_to": None,
            "time_precision": "year",
            "memory_refs": [memory_ref],
        }
    )
    packet = RelationshipContextProjectionService(
        service=service,
        reference_context=references,
        owner_id="owner-backend",
    ).project(context_result.object_ref, state_limit=1)
    assert len(packet.states) == 1
    assert "owner-backend" not in packet.model_dump_json()
    assert "elena-backend" not in packet.model_dump_json()
    assert "memory-backend" not in packet.model_dump_json()

    history = AgenticHistorySession(
        [Msg(role="user", content="Elena and I are partners and became closer in 2026.")]
    )
    parent = history.start_state("conversation_entry", history.master_history)
    invocation_context = AgenticToolInvocationContext(
        history_session=history,
        parent_state_run_id=parent.state_run_id,
        parent_provider_call_id="ingest-call",
    )
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    state = RelationshipWriteState(
        cast(LLMInterfaceCore, object()),
        history,
        PromptService(FilePromptTemplateSource(templates_root), PromptRenderer()),
        owner_id="owner-backend",
        graph_relationship_service=service,
        reference_context=references,
    )
    configuration = state.build_invocation(
        RelationshipWriteInputDTO(
            reasoning=_reasoning(),
            node_resolution_results=[],
            memory_context_result=MemoryContextWriteResultDTO(
                writes=[],
                deferred_items=[],
                summary="The supporting memory was stored.",
            ),
            owner=references.register_owner(
                "owner-backend",
                name="Mario",
                surname="Rossi",
            ),
            references=references.entries(),
        ),
        invocation_context,
    )
    assert configuration.toolbox is not None
    assert list(configuration.toolbox.tools_by_name) == ["write_relationship"]
    schema = str(configuration.toolbox.definitions[0].input_model.model_json_schema())
    assert "target_backend_id" not in schema
    assert "HAS_RELATIONSHIP_STATE" not in schema
    assert "KNOWS" in schema
    assert "owner-backend" not in configuration.system_prompt
    assert "Elena Verdi" in configuration.system_prompt
