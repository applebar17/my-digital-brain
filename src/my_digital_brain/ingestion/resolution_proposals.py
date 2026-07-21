"""Validation and compilation of LLM resolution tool requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    ClarificationRequest,
    EntityLookupContextPacket,
    ReferenceObjectKind,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
    ResolvedEntityMap,
    ResolvedEntityMapEntry,
    ResolvedEntityStatus,
    ResolutionDecision,
)
from my_digital_brain.ingestion.enums import ResolutionDecisionType
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry


class ResolutionProposalValidationError(ValueError):
    """Actionable backend validation failure returned to the calling agent."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(slots=True)
class ResolutionProposalValidator:
    registry: RunReferenceRegistry

    def validate(
        self,
        action: ResolutionToolAction,
        *,
        supplied_candidate_refs: Iterable[str],
        packets: Iterable[EntityLookupContextPacket] = (),
    ) -> ResolutionToolAction:
        errors: list[str] = []
        candidate_refs = set(supplied_candidate_refs)
        packet_by_candidate = {packet.candidate_ref: packet for packet in packets}
        if action.candidate_ref not in candidate_refs and action.candidate_ref not in packet_by_candidate:
            errors.append(f"candidate_ref '{action.candidate_ref}' was not supplied for this step.")

        refs_to_check = [
            ("target_ref", action.target_ref),
            ("from_ref", action.from_ref),
            ("to_ref", action.to_ref),
            *[(f"evidence_refs[{index}]", ref) for index, ref in enumerate(action.evidence_refs)],
        ]
        for field_name, ref in refs_to_check:
            if ref is None:
                continue
            if ref in candidate_refs:
                continue
            try:
                entry = self.registry.entry_for(ref)
            except ValueError:
                errors.append(f"{field_name} '{ref}' is unknown, stale, or outside this run.")
                continue
            if entry.graph_scope != self.registry.graph_scope or entry.session_scope != self.registry.run_scope:
                errors.append(f"{field_name} '{ref}' is outside the active graph/session scope.")

        if action.tool_name in {
            ResolutionToolName.UPDATE_NODE,
            ResolutionToolName.UPDATE_MEMORY,
            ResolutionToolName.UPDATE_RELATIONSHIP,
        } and action.target_ref:
            self._require_existing(action.target_ref, errors, "target_ref")
        if action.tool_name in {
            ResolutionToolName.CREATE_RELATIONSHIP,
            ResolutionToolName.UPDATE_RELATIONSHIP,
        }:
            self._require_known(action.from_ref, errors, "from_ref", candidate_refs)
            self._require_known(action.to_ref, errors, "to_ref", candidate_refs)

        if action.tool_name == ResolutionToolName.CREATE_NODE:
            owner_value = action.payload.get("is_owner")
            if owner_value is True:
                errors.append("LLM actions cannot create an owner node.")
        if _contains_protected_person_fields(action.payload):
            errors.append(
                "Stable Person traits and owner identity fields must be represented by "
                "the governed profile-memory flow, not a direct node action."
            )
        if errors:
            raise ResolutionProposalValidationError(errors)
        return action

    def _require_known(
        self,
        ref: str | None,
        errors: list[str],
        field_name: str,
        candidate_refs: set[str],
    ) -> None:
        if not ref:
            return
        if ref in candidate_refs:
            return
        try:
            self.registry.entry_for(ref)
        except ValueError:
            errors.append(f"{field_name} '{ref}' is not supplied by the backend registry.")

    def _require_existing(self, ref: str, errors: list[str], field_name: str) -> None:
        try:
            entry = self.registry.entry_for(ref)
        except ValueError:
            errors.append(f"{field_name} '{ref}' is not supplied by the backend registry.")
            return
        if str(entry.status) != "existing":
            errors.append(f"{field_name} '{ref}' is proposed and cannot be updated yet.")


@dataclass(slots=True)
class ResolutionProposalCompiler:
    validator: ResolutionProposalValidator

    def compile(
        self,
        actions: Iterable[ResolutionToolAction],
        *,
        candidate_graph: CandidateMemoryGraph,
        packets: Iterable[EntityLookupContextPacket] = (),
        supplied_candidate_refs: Iterable[str] | None = None,
    ) -> ResolutionResult:
        candidate_refs = set(supplied_candidate_refs or [])
        candidate_refs.update(entity.local_ref for entity in candidate_graph.candidate_entities)
        packets_list = list(packets)
        validated = self.validate_actions(
            actions,
            supplied_candidate_refs=candidate_refs,
            packets=packets_list,
        )

        node_actions = [action for action in validated if action.step == ResolutionStep.NODE]
        entity_refs = {entity.local_ref for entity in candidate_graph.candidate_entities}
        self._require_actions_for_refs(node_actions, entity_refs, "node")

        decisions: list[ResolutionDecision] = []
        clarifications: list[ClarificationRequest] = []
        actions_by_ref: dict[str, list[ResolutionToolAction]] = {}
        for action in node_actions:
            actions_by_ref.setdefault(action.candidate_ref, []).append(action)
        for candidate_ref, candidate_actions in actions_by_ref.items():
            clarifying_actions = [
                action
                for action in candidate_actions
                if action.tool_name == ResolutionToolName.ASK_CLARIFICATION
            ]
            clarifications.extend(
                self._clarification(action, ResolutionStep.NODE)
                for action in clarifying_actions
            )
            actionable = [action for action in candidate_actions if action not in clarifying_actions]
            if clarifying_actions and actionable:
                raise ResolutionProposalValidationError(
                    [
                        f"Candidate {candidate_ref} cannot combine clarification and "
                        "mutation actions in one resolution step."
                    ]
                )
            action = actionable[0] if actionable else clarifying_actions[0]
            if action.tool_name == ResolutionToolName.CREATE_NODE:
                decision_type = ResolutionDecisionType.CREATE
                target_id = None
            elif action.tool_name == ResolutionToolName.UPDATE_NODE:
                decision_type = ResolutionDecisionType.MATCH_EXISTING
                target_id = self.validator.registry.resolve(
                    action.target_ref or "",
                    expected_kind=ReferenceObjectKind.NODE,
                )
            elif action.tool_name == ResolutionToolName.DEFER_OR_IGNORE:
                decision_type = ResolutionDecisionType.KEEP_PENDING
                target_id = None
            elif action.tool_name == ResolutionToolName.ASK_CLARIFICATION:
                decision_type = ResolutionDecisionType.ASK_CLARIFICATION
                target_id = None
            else:
                raise ResolutionProposalValidationError(
                    [f"Tool '{action.tool_name}' is not a node resolution action."]
                )
            decisions.append(
                ResolutionDecision(
                    candidate_ref=candidate_ref,
                    decision_type=decision_type,
                    target_entity_id=target_id,
                    reasons=[action.reason] if action.reason else [],
                    decided_at=datetime.now(UTC),
                    metadata={
                        "tool_name": str(action.tool_name),
                        "evidence_refs": list(action.evidence_refs),
                    },
                ),
            )

        return ResolutionResult(
            decisions=decisions,
            clarifications=clarifications,
            metadata={
                "policy": "llm_selected_action_backend_validated",
                "validated_tool_actions": [action.model_dump(mode="json", exclude_none=True) for action in validated],
            },
        )

    def validate_actions(
        self,
        actions: Iterable[ResolutionToolAction],
        *,
        supplied_candidate_refs: Iterable[str],
        packets: Iterable[EntityLookupContextPacket] = (),
    ) -> list[ResolutionToolAction]:
        packets_list = list(packets)
        candidate_refs = set(supplied_candidate_refs)
        return [
            self.validator.validate(
                action,
                supplied_candidate_refs=candidate_refs,
                packets=packets_list,
            )
            for action in actions
        ]

    def merge_step_actions(
        self,
        result: ResolutionResult,
        actions: Iterable[ResolutionToolAction],
        *,
        step: ResolutionStep,
        supplied_candidate_refs: Iterable[str],
        packets: Iterable[EntityLookupContextPacket] = (),
    ) -> ResolutionResult:
        candidate_refs = set(supplied_candidate_refs)
        validated = self.validate_actions(
            actions,
            supplied_candidate_refs=candidate_refs,
            packets=packets,
        )
        step_actions = [action for action in validated if action.step == step]
        self._require_actions_for_refs(step_actions, candidate_refs, step.value)
        clarifications = [
            self._clarification(action, step)
            for action in step_actions
            if action.tool_name == ResolutionToolName.ASK_CLARIFICATION
        ]
        existing_actions = list(result.metadata.get("validated_tool_actions") or [])
        return result.model_copy(
            update={
                "clarifications": [*result.clarifications, *clarifications],
                "metadata": {
                    **result.metadata,
                    "validated_tool_actions": [
                        *existing_actions,
                        *[action.model_dump(mode="json", exclude_none=True) for action in validated],
                    ],
                },
            },
            deep=True,
        )

    @staticmethod
    def _require_actions_for_refs(
        actions: list[ResolutionToolAction],
        candidate_refs: set[str],
        step_name: str,
    ) -> None:
        action_refs = [action.candidate_ref for action in actions]
        by_ref: dict[str, list[ResolutionToolAction]] = {}
        for action in actions:
            by_ref.setdefault(action.candidate_ref, []).append(action)
        duplicates = sorted(
            ref
            for ref, ref_actions in by_ref.items()
            if len(ref_actions) > 1
            and any(action.tool_name != ResolutionToolName.ASK_CLARIFICATION for action in ref_actions)
        )
        missing = sorted(candidate_refs - set(action_refs))
        if duplicates or missing:
            errors = []
            if duplicates:
                errors.append(
                    f"Multiple {step_name} actions were supplied for: {', '.join(duplicates)}."
                )
            if missing:
                errors.append(
                    f"No {step_name} action was supplied for: {', '.join(missing)}."
                )
            raise ResolutionProposalValidationError(errors)

    def build_entity_map(
        self,
        candidate_graph: CandidateMemoryGraph,
        result: ResolutionResult,
    ) -> ResolvedEntityMap:
        decision_by_ref = {decision.candidate_ref: decision for decision in result.decisions}
        entries: list[ResolvedEntityMapEntry] = []
        for entity in candidate_graph.candidate_entities:
            decision = decision_by_ref.get(entity.local_ref)
            if decision is None:
                raise ResolutionProposalValidationError(
                    [f"No compiled resolution decision exists for {entity.local_ref}."]
                )
            if decision.decision_type == ResolutionDecisionType.CREATE:
                status = ResolvedEntityStatus.STAGED_CREATE
                graph_alias = entity.local_ref
            elif decision.decision_type == ResolutionDecisionType.MATCH_EXISTING:
                status = ResolvedEntityStatus.MATCHED_EXISTING
                graph_alias = self.validator.registry.alias_for_internal(decision.target_entity_id or "")
            elif decision.decision_type == ResolutionDecisionType.KEEP_PENDING:
                status = ResolvedEntityStatus.PENDING_DUPLICATE_REVIEW
                graph_alias = None
            else:
                status = ResolvedEntityStatus.REJECTED
                graph_alias = None
            entries.append(
                ResolvedEntityMapEntry(
                    local_ref=entity.local_ref,
                    status=status,
                    display_label=entity.display_name or entity.description,
                    entity_type=entity.entity_type,
                    graph_alias=graph_alias,
                    resolution_reason=(decision.reasons[0] if decision.reasons else None),
                ),
            )
        return ResolvedEntityMap(entries=entries, notes=["Compiled from validated LLM actions."])

    def result_from_entity_map(self, entity_map: ResolvedEntityMap) -> ResolutionResult:
        """Rehydrate backend decisions without repeating semantic lookup."""

        decisions: list[ResolutionDecision] = []
        for entry in entity_map.entries:
            if entry.status == ResolvedEntityStatus.STAGED_CREATE:
                decision_type = ResolutionDecisionType.CREATE
                target_id = None
            elif entry.status in {
                ResolvedEntityStatus.MATCHED_EXISTING,
                ResolvedEntityStatus.STAGED_UPDATE,
            }:
                decision_type = ResolutionDecisionType.MATCH_EXISTING
                target_id = self.validator.registry.resolve(
                    entry.graph_alias or "",
                    expected_kind=ReferenceObjectKind.NODE,
                )
            elif entry.status == ResolvedEntityStatus.PENDING_DUPLICATE_REVIEW:
                decision_type = ResolutionDecisionType.KEEP_PENDING
                target_id = None
            else:
                decision_type = ResolutionDecisionType.REJECT
                target_id = None
            decisions.append(
                ResolutionDecision(
                    candidate_ref=entry.local_ref,
                    decision_type=decision_type,
                    target_entity_id=target_id,
                    reasons=[entry.resolution_reason] if entry.resolution_reason else [],
                    decided_at=datetime.now(UTC),
                    metadata={"source": "compiled_entity_map"},
                ),
            )
        return ResolutionResult(
            decisions=decisions,
            metadata={"policy": "llm_selected_action_backend_validated"},
        )

    def _clarification(
        self,
        action: ResolutionToolAction,
        step: ResolutionStep,
    ) -> ClarificationRequest:
        return ClarificationRequest(
            doubt=action.question or "Which supplied candidate did you mean?",
            reason=action.reason or "The supplied context did not support one safe identity choice.",
            target_refs=[action.candidate_ref, *([action.target_ref] if action.target_ref else [])],
            options="; ".join(action.options) or None,
            blocking=True,
            metadata={
                "source": "ask_clarification",
                "resolution_step": step.value,
                "evidence_refs": list(action.evidence_refs),
            },
        )


def _contains_protected_person_fields(payload: object) -> bool:
    if isinstance(payload, list):
        return any(_contains_protected_person_fields(item) for item in payload)
    if not isinstance(payload, dict):
        return False
    protected = {
        "is_owner",
        "personality",
        "personality_traits",
        "stable_traits",
        "profile_key",
        "assertion_mode",
        "backend_id",
        "graph_id",
        "node_id",
        "target_entity_id",
        "owner_id",
    }
    for key, value in payload.items():
        if str(key).casefold() in protected:
            return True
        if isinstance(value, str) and value.casefold().startswith("person:"):
            return True
        if _contains_protected_person_fields(value):
            return True
    return False
