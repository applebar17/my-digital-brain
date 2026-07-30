"""Model-facing projection of read-only graph clarification context."""

from __future__ import annotations

from typing import Any

from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult


def project_entity_detail(
    detail: Any,
    registry: Any,
    *,
    graph_service: Any | None,
    include_relationships: bool,
    include_evidence: bool,
    limit: int,
) -> dict[str, Any]:
    target = getattr(detail, "target", None)
    if target is None:
        raise ValueError("Graph context did not contain a target node.")
    target_ref = register_node(target, registry)
    result = {"ref": target_ref, "node": project_node(target, registry)}
    if include_relationships:
        result["relationships"] = [
            projected
            for projected in [
                project_relationship(item, registry, graph_service=graph_service)
                for item in list(getattr(detail, "relationships", []))[:limit]
            ]
            if projected
        ]
    if include_evidence:
        evidence = [
            *list(getattr(detail, "perceptions", [])),
            *list(getattr(detail, "sources", [])),
            *list(getattr(detail, "changes", [])),
        ][:limit]
        result["evidence"] = [project_node(item, registry) for item in evidence]
    return result


def project_node(node: Any, registry: Any | None = None) -> dict[str, Any]:
    model = NodeSearchResult.model_validate(node)
    properties = {
        key: value
        for key, value in model.properties.items()
        if key not in {"id", "node_id", "graph_id"}
        and not key.endswith("_id")
        and not key.endswith("_ids")
    }
    return {
        "label": model.label,
        "labels": list(model.labels),
        "properties": redact_values(properties, registry),
    }


def register_node(node: Any, registry: Any) -> str:
    model = NodeSearchResult.model_validate(node)
    node_id = model.properties.get("id")
    if not node_id:
        raise ValueError("Graph context node has no internal id.")
    try:
        return registry.alias_for_internal(str(node_id))
    except ValueError:
        return registry.register_existing(
            str(node_id),
            object_kind=_node_kind(),
            label=model.label,
            display_label=display_name(model),
            aliases=aliases(model),
        )


def project_relationship(
    relationship: Any,
    registry: Any,
    *,
    graph_service: Any | None = None,
) -> dict[str, Any]:
    model = (
        relationship
        if isinstance(relationship, RelationshipResult)
        else RelationshipResult.model_validate(relationship)
    )
    if graph_service is not None:
        for endpoint in (model.from_id, model.to_id):
            try:
                safe_ref(endpoint, registry)
            except ValueError:
                register_node(graph_service.get_node(endpoint), registry)
    return {
        "type": model.type,
        "from_ref": safe_ref(model.from_id, registry),
        "to_ref": safe_ref(model.to_id, registry),
        "properties": redact_values(
            {
                key: value
                for key, value in model.properties.items()
                if key not in {"id", "from_id", "to_id"}
                and not key.endswith("_id")
                and not key.endswith("_ids")
            },
            registry,
        ),
    }


def relationship_matches(relationship: Any, from_id: str, to_id: str) -> bool:
    model = (
        relationship
        if isinstance(relationship, RelationshipResult)
        else RelationshipResult.model_validate(relationship)
    )
    return {str(model.from_id), str(model.to_id)} == {str(from_id), str(to_id)}


def redact_values(value: Any, registry: Any | None) -> Any:
    if registry is None:
        return value
    if isinstance(value, str):
        try:
            return registry.alias_for_internal(value)
        except ValueError:
            return value
    if isinstance(value, list):
        return [redact_values(item, registry) for item in value]
    if isinstance(value, dict):
        return {key: redact_values(item, registry) for key, item in value.items()}
    return value


def safe_ref(internal_id: str, registry: Any) -> str:
    try:
        return registry.alias_for_internal(str(internal_id))
    except ValueError as exc:
        raise ValueError(
            f"Relationship endpoint is not registered in this run: {internal_id}"
        ) from exc


def display_name(node: NodeSearchResult) -> str | None:
    for field in ("display_name", "name", "title", "description"):
        value = node.properties.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def aliases(node: NodeSearchResult) -> list[str]:
    value = node.properties.get("aliases")
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _node_kind() -> Any:
    from my_digital_brain.ingestion.contracts import ReferenceObjectKind

    return ReferenceObjectKind.NODE
