from __future__ import annotations

from my_digital_brain.agentic import PlanningPurposeGuidelines


def entity_ingestion_planning_guidelines() -> PlanningPurposeGuidelines:
    return PlanningPurposeGuidelines(
        purpose_id="entity_ingestion_planning",
        goal="Plan entity-only preparation from source text, reasoning notes, and graph context.",
        focus_areas=[
            "entity anchors",
            "aliases and nicknames",
            "duplicate hints",
            "node versus detail decisions",
            "SocialCircle caution",
        ],
        instructions=[
            "Produce entity actions only; do not plan relationships or graph writes.",
            "Treat aliases as extraction and resolution hints, not identity.",
            "Use graph context duplicate hints before planning a new entity action.",
            "Keep low-salience details as context unless durable memory value is clear.",
            "Do not output backend ids, source ids, metadata dicts, or persistence fields.",
        ],
        output_usage="EntityIngestionPlanDraft for later entity candidate preparation.",
        forbidden_assumptions=[
            "Do not assume a nickname is a separate Person.",
            "Do not create SocialCircle actions for vague groups unless meaningful.",
        ],
    )


def relationship_ingestion_planning_guidelines() -> PlanningPurposeGuidelines:
    return PlanningPurposeGuidelines(
        purpose_id="relationship_ingestion_planning",
        goal="Plan relationship-only preparation from source text and resolved entity refs.",
        focus_areas=[
            "resolved endpoints",
            "relationship intent",
            "relationship context",
            "owner/user endpoint handling",
            "missing endpoints",
        ],
        instructions=[
            "Plan relationships only between refs usable from the resolved entity map or provided graph aliases.",
            "Use RELATIONSHIP_WITH plus relationship detail for social wording such as brother or roommate.",
            "Emit MissingEntityRequiredDraft guidance when an endpoint is missing.",
            "Do not freely create new entities during relationship planning.",
            "Do not output graph write operations or backend-owned ids.",
        ],
        output_usage="RelationshipIngestionPlanDraft for later relationship candidate preparation.",
        forbidden_assumptions=[
            "Do not invent unresolved endpoints.",
            "Do not infer owner/user graph ids unless provided by context.",
            "Do not produce unsupported edge types.",
        ],
    )


def missing_entity_planning_guidelines() -> PlanningPurposeGuidelines:
    return PlanningPurposeGuidelines(
        purpose_id="missing_entity_planning",
        goal="Plan only the missing entity required to resume a blocked relationship.",
        focus_areas=[
            "missing endpoint mention",
            "required relationship role",
            "duplicate hints",
            "minimal entity action",
        ],
        instructions=[
            "Plan only the missing endpoint described by MissingEntityRequiredDraft.",
            "Preserve relationship resume guidance for the later relationship pass.",
            "Use aliases and duplicate hints as resolution context, not identity.",
            "Do not plan unrelated entities or relationships.",
        ],
        output_usage="EntityIngestionPlanDraft for supplemental missing-entity preparation.",
        forbidden_assumptions=[
            "Do not infer extra entities from unrelated context.",
            "Do not complete the blocked relationship in this step.",
            "Do not decide durable writes or duplicate merges.",
        ],
    )
