from __future__ import annotations

from typing import Any

from my_digital_brain.graph.exceptions import GraphError
from my_digital_brain.ingestion.contracts import (
    CandidateMetadataPatch,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    IngestionResult,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import GraphWritePlanStatus, IngestionStatus
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.validation import IngestionValidator


class GraphWritePlanExecutor:
    """Execute validated write plans through the graph service facade."""

    def __init__(
        self,
        graph_service: Any,
        *,
        validator: IngestionValidator | None = None,
    ) -> None:
        self.graph_service = graph_service
        self.validator = validator or IngestionValidator()

    def execute(self, write_plan: GraphWritePlan) -> IngestionResult:
        try:
            self._validate_status(write_plan)
            validation = self.validator.validate_write_plan(write_plan)
            if not validation.is_valid:
                return IngestionResult(
                    source_id=write_plan.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    write_plan=write_plan,
                    validation_errors=validation.issues,
                )
            if not _write_plan_has_mutations(write_plan):
                return IngestionResult(
                    source_id=write_plan.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    write_plan=write_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="write_plan",
                            message=(
                                "The write plan contains no graph mutations. "
                                "Execution was skipped because an empty write plan "
                                "cannot be considered stored memory."
                            ),
                            code="empty_write_plan",
                        )
                    ],
                )

            ref_map = self._initial_ref_map(write_plan)
            created_nodes = self._execute_node_creates(write_plan.nodes_to_create, ref_map)
            updated_nodes = self._execute_node_updates(write_plan.nodes_to_update, ref_map)
            created_claims = self._execute_node_creates(write_plan.claims_to_create, ref_map)
            created_perceptions = self._execute_node_creates(
                write_plan.perceptions_to_create,
                ref_map,
            )
            created_contexts = self._execute_node_creates(
                write_plan.relationship_contexts_to_create,
                ref_map,
            )
            patched_nodes = self._execute_metadata_patches(write_plan.metadata_patches, ref_map)
            relationships = self._execute_relationship_writes(
                [
                    *write_plan.relationships_to_create,
                    *write_plan.relationships_to_update,
                ],
                ref_map,
            )

            write_plan.status = GraphWritePlanStatus.EXECUTED
            return IngestionResult(
                source_id=write_plan.source_id,
                status=IngestionStatus.WRITTEN,
                write_plan=write_plan,
                metadata={
                    "created_nodes": len(created_nodes),
                    "updated_nodes": len(updated_nodes),
                    "created_claims": len(created_claims),
                    "created_perceptions": len(created_perceptions),
                    "created_relationship_contexts": len(created_contexts),
                    "metadata_patches": len(patched_nodes),
                    "relationships": len(relationships),
                    "ref_map": ref_map,
                },
            )
        except (GraphError, IngestionValidationError, ValueError) as exc:
            return IngestionResult(
                source_id=write_plan.source_id,
                status=IngestionStatus.FAILED,
                write_plan=write_plan,
                validation_errors=[
                    ValidationIssue(
                        field_path="write_plan",
                        message=str(exc),
                        code="write_plan_execution_failed",
                    ),
                ],
            )

    def _validate_status(self, write_plan: GraphWritePlan) -> None:
        status = GraphWritePlanStatus(write_plan.status)
        if status == GraphWritePlanStatus.EXECUTED:
            raise IngestionValidationError("Write plan has already been executed.")
        if status == GraphWritePlanStatus.FAILED:
            raise IngestionValidationError("Failed write plans must be rebuilt before execution.")

    def _initial_ref_map(self, write_plan: GraphWritePlan) -> dict[str, str]:
        metadata = write_plan.metadata or {}
        ref_map = dict(metadata.get("alias_map", {}))
        ref_map.update(metadata.get("local_ref_resolution", {}))
        return ref_map

    def _execute_node_creates(
        self,
        writes: list[GraphNodeWrite],
        ref_map: dict[str, str],
    ) -> list[Any]:
        results: list[Any] = []
        for write in writes:
            result = self.graph_service.upsert_node(write.label, write.properties)
            node_id = result.properties["id"]
            ref_map[write.local_ref] = node_id
            results.append(result)
        return results

    def _execute_node_updates(
        self,
        writes: list[GraphNodeWrite],
        ref_map: dict[str, str],
    ) -> list[Any]:
        results: list[Any] = []
        for write in writes:
            target_id = self._resolve_node_write_target(write, ref_map)
            patch = {key: value for key, value in write.properties.items() if key != "id"}
            result = self.graph_service.patch_node(target_id, patch)
            ref_map[write.local_ref] = result.properties["id"]
            results.append(result)
        return results

    def _execute_relationship_writes(
        self,
        writes: list[GraphRelationshipWrite],
        ref_map: dict[str, str],
    ) -> list[Any]:
        results: list[Any] = []
        for write in writes:
            from_id = self._resolve_ref(write.from_ref, ref_map)
            to_id = self._resolve_ref(write.to_ref, ref_map)
            result = self.graph_service.upsert_relationship(
                write.relationship_type,
                from_id,
                to_id,
                write.properties,
            )
            ref_map[write.local_ref] = result.properties["id"]
            results.append(result)
        return results

    def _execute_metadata_patches(
        self,
        patches: list[CandidateMetadataPatch],
        ref_map: dict[str, str],
    ) -> list[Any]:
        results: list[Any] = []
        for patch in patches:
            if "." in patch.path:
                raise IngestionValidationError(
                    "Nested metadata patch paths are not supported in Wave 3."
                )
            target_id = self._resolve_ref(patch.target_ref, ref_map)
            patch_properties = self._metadata_patch_properties(patch, target_id)
            results.append(self.graph_service.patch_node(target_id, patch_properties))
        return results

    def _metadata_patch_properties(
        self,
        patch: CandidateMetadataPatch,
        target_id: str,
    ) -> dict[str, Any]:
        if patch.operation == "set":
            return {patch.path: patch.value}
        node = self.graph_service.get_node(target_id)
        current = node.properties.get(patch.path)
        if patch.operation == "append":
            if isinstance(current, list):
                values = list(current)
            elif current is None:
                values = []
            else:
                values = [current]
            if patch.value not in values:
                values.append(patch.value)
            return {patch.path: values}
        if patch.operation == "remove":
            if isinstance(current, list):
                return {patch.path: [value for value in current if value != patch.value]}
            return {patch.path: None}
        raise IngestionValidationError(f"Unsupported metadata patch operation: {patch.operation}")

    def _resolve_node_write_target(
        self,
        write: GraphNodeWrite,
        ref_map: dict[str, str],
    ) -> str:
        if write.target_ref:
            return self._resolve_ref(write.target_ref, ref_map)
        if write.local_ref in ref_map:
            return ref_map[write.local_ref]
        node_id = write.properties.get("id")
        if isinstance(node_id, str) and node_id:
            return node_id
        raise IngestionValidationError(f"Node write {write.local_ref} has no target ref.")

    def _resolve_ref(self, ref: str, ref_map: dict[str, str]) -> str:
        if ref in ref_map:
            return ref_map[ref]
        if ref.startswith("CANDIDATE_"):
            raise IngestionValidationError(f"Unresolved candidate reference: {ref}")
        return ref


def _write_plan_has_mutations(write_plan: GraphWritePlan) -> bool:
    return any(
        (
            write_plan.nodes_to_create,
            write_plan.nodes_to_update,
            write_plan.relationships_to_create,
            write_plan.relationships_to_update,
            write_plan.claims_to_create,
            write_plan.perceptions_to_create,
            write_plan.relationship_contexts_to_create,
            write_plan.metadata_patches,
        )
    )
