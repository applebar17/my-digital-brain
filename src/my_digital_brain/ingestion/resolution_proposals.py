"""Validation and compilation of LLM resolution tool requests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    EntityLookupContextPacket,
    ReferenceObjectKind,
    ResolutionDecision,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
    ResolvedEntityMap,
    ResolvedEntityMapEntry,
    ResolvedEntityStatus,
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
        if (
            action.candidate_ref not in candidate_refs
            and action.candidate_ref not in packet_by_candidate
        ):
            errors.append(
                f"candidate_ref '{action.candidate_ref}' was not supplied for this step. "
                f"Assigned candidate IDs: {', '.join(sorted(candidate_refs))}. "
                "Use one of the supplied IDs."
            )

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
            if (
                entry.graph_scope != self.registry.graph_scope
                or entry.session_scope != self.registry.run_scope
            ):
                errors.append(f"{field_name} '{ref}' is outside the active graph/session scope.")

        if (
            action.tool_name
            in {
                ResolutionToolName.UPDATE_NODE,
                ResolutionToolName.UPDATE_MEMORY,
                ResolutionToolName.UPDATE_RELATIONSHIP,
            }
            and action.target_ref
        ):
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
        required_candidate_refs: Iterable[str] | None = None,
        action_candidate_refs: Iterable[str] | None = None,
    ) -> ResolutionResult:
        if supplied_candidate_refs is None:
            candidate_refs = {entity.local_ref for entity in candidate_graph.candidate_entities}
        else:
            candidate_refs = set(supplied_candidate_refs)
        required_refs = set(required_candidate_refs or [])
        if not required_refs:
            required_refs = {entity.local_ref for entity in candidate_graph.candidate_entities}
        packets_list = list(packets)
        validated = self.validate_actions(
            actions,
            supplied_candidate_refs=candidate_refs,
            packets=packets_list,
        )

        node_actions = [action for action in validated if action.step == ResolutionStep.NODE]
        self._reject_actions_outside_refs(
            node_actions,
            set(action_candidate_refs or required_refs),
            "node",
        )
        entity_refs = {
            entity.local_ref
            for entity in candidate_graph.candidate_entities
            if entity.local_ref in required_refs
        }
        self._require_actions_for_refs(node_actions, entity_refs, "node")

        decisions: list[ResolutionDecision] = []
        actions_by_ref: dict[str, list[ResolutionToolAction]] = {}
        for action in node_actions:
            actions_by_ref.setdefault(action.candidate_ref, []).append(action)
        for candidate_ref, candidate_actions in actions_by_ref.items():
            action = candidate_actions[0]
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
            metadata={
                "policy": "llm_selected_action_backend_validated",
                "validated_tool_actions": [
                    action.model_dump(mode="json", exclude_none=True) for action in validated
                ],
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
        action_candidate_refs: Iterable[str] | None = None,
        packets: Iterable[EntityLookupContextPacket] = (),
    ) -> ResolutionResult:
        candidate_refs = set(supplied_candidate_refs)
        validated = self.validate_actions(
            actions,
            supplied_candidate_refs=candidate_refs,
            packets=packets,
        )
        step_actions = [action for action in validated if action.step == step]
        action_refs = set(action_candidate_refs or candidate_refs)
        self._reject_actions_outside_refs(step_actions, action_refs, step.value)
        self._require_actions_for_refs(
            step_actions,
            action_refs,
            step.value,
        )
        existing_actions = list(result.metadata.get("validated_tool_actions") or [])
        return result.model_copy(
            update={
                "metadata": {
                    **result.metadata,
                    "validated_tool_actions": [
                        *existing_actions,
                        *[
                            action.model_dump(mode="json", exclude_none=True)
                            for action in validated
                        ],
                    ],
                },
            },
            deep=True,
        )

    @staticmethod
    def require_complete_actions(
        actions: Iterable[ResolutionToolAction],
        candidate_refs: Iterable[str],
        step_name: str,
    ) -> None:
        """Require one terminal action for exactly the supplied batch refs."""

        ResolutionProposalCompiler._require_actions_for_refs(
            list(actions), set(candidate_refs), step_name
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
        duplicates = sorted(ref for ref, ref_actions in by_ref.items() if len(ref_actions) > 1)
        missing = sorted(candidate_refs - set(action_refs))
        if duplicates or missing:
            errors = []
            if duplicates:
                errors.append(
                    f"Multiple {step_name} actions were supplied for: {', '.join(duplicates)}."
                )
            if missing:
                errors.append(
                    f"No {step_name} action was supplied for: {', '.join(missing)}. "
                    f"Assigned candidate IDs: {', '.join(sorted(candidate_refs))}. "
                    "The resolution step returned no action tool call for these IDs. "
                    "Provide exactly one terminal action for every supplied ID."
                )
            raise ResolutionProposalValidationError(errors)

    @staticmethod
    def _reject_actions_outside_refs(
        actions: list[ResolutionToolAction],
        candidate_refs: set[str],
        step_name: str,
    ) -> None:
        outside_refs = sorted({action.candidate_ref for action in actions} - candidate_refs)
        if outside_refs:
            raise ResolutionProposalValidationError(
                [
                    f"{step_name} actions were supplied for candidates outside the "
                    f"current batch: {', '.join(outside_refs)}. "
                    "Use those references only as evidence or relationship endpoints; "
                    "submit terminal actions only for the current batch candidates."
                ]
            )

    def build_entity_map(
        self,
        candidate_graph: CandidateMemoryGraph,
        result: ResolutionResult,
        *,
        candidate_refs: Iterable[str] | None = None,
    ) -> ResolvedEntityMap:
        decision_by_ref = {decision.candidate_ref: decision for decision in result.decisions}
        selected_refs = set(candidate_refs or [])
        entries: list[ResolvedEntityMapEntry] = []
        for entity in candidate_graph.candidate_entities:
            if selected_refs and entity.local_ref not in selected_refs:
                continue
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
                graph_alias = self.validator.registry.alias_for_internal(
                    decision.target_entity_id or ""
                )
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
