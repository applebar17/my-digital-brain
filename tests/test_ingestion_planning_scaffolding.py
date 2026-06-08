from __future__ import annotations

from my_digital_brain.ingestion import (
    GraphContextPackRendererService,
    build_entity_planning_context,
    build_missing_entity_planning_context,
    build_relationship_planning_context,
    entity_ingestion_planning_guidelines,
    missing_entity_planning_guidelines,
    relationship_ingestion_planning_guidelines,
)
from my_digital_brain.ingestion.contracts import (
    GraphContextDuplicateHintItem,
    GraphContextEntityItem,
    GraphContextKnownAliasItem,
    GraphContextMemoryItem,
    GraphContextPack,
    GraphContextRelationshipItem,
    GraphContextRelationshipSnippetItem,
    GraphContextRenderPurpose,
    IngestionReasoningCheckpointDraft,
    MissingEntityRequiredDraft,
    ResolvedEntityMap,
    ResolvedEntityMapEntry,
    ResolvedEntityStatus,
)


def test_graph_context_pack_renderer_selects_fields_by_purpose() -> None:
    pack = _context_pack()
    renderer = GraphContextPackRendererService()

    entity_view = renderer.render(pack, GraphContextRenderPurpose.ENTITY_PLANNING)
    relationship_view = renderer.render(pack, GraphContextRenderPurpose.RELATIONSHIP_PLANNING)
    reasoning_view = renderer.render(pack, GraphContextRenderPurpose.REASONING)

    entity_payload = entity_view.model_dump(mode="json", exclude_none=True)
    assert entity_payload["purpose"] == "entity_planning"
    assert "source_id" not in entity_payload
    assert "retrieval_strategy" not in entity_payload
    assert entity_view.selected_entities
    assert entity_view.duplicate_hints
    assert entity_view.selected_relationships == []

    assert relationship_view.selected_relationships
    assert relationship_view.relationship_context_snippets
    assert relationship_view.duplicate_hints == []
    assert "Matteo Mercoldi" in relationship_view.selected_entities[0]

    assert any(note.startswith("Memory memory:1") for note in reasoning_view.notes)


def test_ingestion_planning_guidelines_lock_step_boundaries() -> None:
    entity = entity_ingestion_planning_guidelines()
    relationship = relationship_ingestion_planning_guidelines()
    missing = missing_entity_planning_guidelines()

    assert entity.purpose_id == "entity_ingestion_planning"
    assert any("aliases" in item.lower() for item in entity.instructions)
    assert relationship.purpose_id == "relationship_ingestion_planning"
    assert any("missing" in item.lower() for item in relationship.instructions)
    assert missing.purpose_id == "missing_entity_planning"
    assert any("only the missing endpoint" in item for item in missing.instructions)


def test_entity_and_relationship_planning_context_builders_are_llm_friendly() -> None:
    renderer = GraphContextPackRendererService()
    pack = _context_pack()
    reasoning = _reasoning()
    resolved_map = _resolved_entity_map()

    entity_context = build_entity_planning_context(
        source_text="Merc is Matteo Mercoldi.",
        graph_context_view=renderer.render(pack, GraphContextRenderPurpose.ENTITY_PLANNING),
        reasoning=reasoning,
        timezone="Europe/Rome",
    )
    relationship_context = build_relationship_planning_context(
        source_text="Merc is my brother.",
        graph_context_view=renderer.render(pack, GraphContextRenderPurpose.RELATIONSHIP_PLANNING),
        reasoning=reasoning,
        resolved_entity_map=resolved_map,
        timezone="Europe/Rome",
    )

    assert entity_context.purpose.purpose_id == "entity_ingestion_planning"
    assert entity_context.expected_output_schema == "EntityIngestionPlanDraft"
    assert entity_context.input_context["planning_scope"] == "entities_only"
    assert entity_context.input_context["graph_context_view"]["purpose"] == "entity_planning"
    assert "source_id" not in entity_context.input_context["graph_context_view"]

    resolved_view = relationship_context.input_context["resolved_entity_map_view"]
    assert relationship_context.purpose.purpose_id == "relationship_ingestion_planning"
    assert relationship_context.expected_output_schema == "RelationshipIngestionPlanDraft"
    assert resolved_view["relationship_usable_refs"] == {
        "CANDIDATE_PERSON_001": "NODE_000001",
    }
    assert resolved_view["entries"][1]["relationship_ref"] is None


def test_missing_entity_planning_context_carries_resume_guidance_only() -> None:
    renderer = GraphContextPackRendererService()
    missing = MissingEntityRequiredDraft(
        missing_ref="MISSING_ENTITY_001",
        reason="The brother endpoint was not resolved.",
        mention_text="mio fratello",
        suggested_entity_type="Person",
        needed_for_relationship_ref="REL_ACTION_001",
        relationship_goal="Store the user's brother relationship.",
        relationship_endpoint_role="to",
        evidence_text="mio fratello",
        entity_planning_guidance="Plan one person endpoint.",
        relationship_resume_guidance="Resume REL_ACTION_001 after resolution.",
    )

    context = build_missing_entity_planning_context(
        source_text="mio fratello vive a Milano",
        graph_context_view=renderer.render(
            _context_pack(),
            GraphContextRenderPurpose.MISSING_ENTITY_PLANNING,
        ),
        reasoning=_reasoning(),
        missing_entity=missing,
        resolved_entity_map=_resolved_entity_map(),
        timezone="Europe/Rome",
    )

    assert context.purpose.purpose_id == "missing_entity_planning"
    assert context.expected_output_schema == "EntityIngestionPlanDraft"
    assert context.input_context["planning_scope"] == "missing_entity_only"
    assert context.input_context["missing_entity_required"]["missing_ref"] == (
        "MISSING_ENTITY_001"
    )
    assert "Do not plan unrelated entities" in context.input_context["rules"][2]


def _context_pack() -> GraphContextPack:
    return GraphContextPack(
        source_id="source-1",
        retrieval_strategy="whole_source_hybrid",
        compact_summary="Matteo Mercoldi is known as Merc.",
        known_aliases=[
            GraphContextKnownAliasItem(
                alias="Merc",
                label="Matteo Mercoldi",
                note="Nickname used by the user.",
                source_id="source-1",
            ),
        ],
        entities=[
            GraphContextEntityItem(
                ref="NODE_000001",
                display_label="Matteo Mercoldi",
                entity_type="Person",
                compact_summary="Known person with alias Merc.",
                aliases=["Merc"],
                source_id="source-1",
                retrieval_strategy="hybrid",
            ),
        ],
        relationships=[
            GraphContextRelationshipItem(
                ref="REL_000001",
                from_ref="OWNER",
                to_ref="NODE_000001",
                relationship_type="RELATIONSHIP_WITH",
                relationship_kind="family",
                relationship_detail="brother",
                compact_summary="The user may refer to Matteo as a brother.",
                source_id="source-1",
            ),
        ],
        memories=[
            GraphContextMemoryItem(
                ref="memory:1",
                compact_summary="The user previously mentioned Merc.",
                related_refs=["NODE_000001"],
                source_id="source-1",
            ),
        ],
        duplicate_hints=[
            GraphContextDuplicateHintItem(
                candidate_text="Merc",
                possible_match_refs=["NODE_000001"],
                reason="Exact alias match.",
                score=0.98,
                source_id="source-1",
            ),
        ],
        relationship_context_snippets=[
            GraphContextRelationshipSnippetItem(
                ref="SNIPPET_000001",
                endpoint_refs=["OWNER", "NODE_000001"],
                compact_summary="Merc appears in a family-context phrase.",
                source_id="source-1",
            ),
        ],
        notes=["Aliases remain hints only."],
    )


def _reasoning() -> IngestionReasoningCheckpointDraft:
    return IngestionReasoningCheckpointDraft(
        summary="Merc likely refers to Matteo Mercoldi.",
        alias_notes=["Merc should be treated as an alias hint."],
        relationship_notes=["Brother wording should be handled after entity resolution."],
    )


def _resolved_entity_map() -> ResolvedEntityMap:
    return ResolvedEntityMap(
        entries=[
            ResolvedEntityMapEntry(
                local_ref="CANDIDATE_PERSON_001",
                status=ResolvedEntityStatus.MATCHED_EXISTING,
                display_label="Matteo Mercoldi",
                entity_type="Person",
                graph_alias="NODE_000001",
            ),
            ResolvedEntityMapEntry(
                local_ref="CANDIDATE_PERSON_002",
                status=ResolvedEntityStatus.PENDING_DUPLICATE_REVIEW,
                display_label="Merc",
                entity_type="Person",
            ),
        ],
    )
