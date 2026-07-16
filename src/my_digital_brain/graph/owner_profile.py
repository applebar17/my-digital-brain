from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from my_digital_brain.core.profile_context import OwnerProfileItem, OwnerProfileSnapshot
from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.graph.exceptions import GraphConflictError, GraphValidationError


class OwnerAliasResolver(Protocol):
    def resolve_owner_alias(self, alias: str) -> str: ...


def is_approved_profile_properties(properties: dict[str, Any]) -> bool:
    metadata = properties.get("metadata") or {}
    return (
        properties.get("lifecycle_state", "active") == "active"
        and properties.get("visibility") == "prompt_allowed"
        and properties.get("stability") in {"stable", "user_confirmed"}
        and metadata.get("requires_confirmation") is not True
    )


class OwnerProfileReader:
    """Read-only, canonical-owner-scoped profile projection."""

    def __init__(self, *, graph_service: Any, owner_manager: OwnerAliasResolver) -> None:
        self.graph_service = graph_service
        self.owner_manager = owner_manager

    def get_approved_profile(self) -> OwnerProfileSnapshot:
        owner_id = self.owner_manager.resolve_owner_alias(OWNER_ALIAS)
        owner = self.graph_service.get_node(owner_id)
        if owner.label != "Person" or owner.properties.get("is_owner") is not True:
            raise GraphConflictError("Configured OWNER is not a validated owner Person node")

        items: list[tuple[str, str, str, OwnerProfileItem]] = []
        for node in self.graph_service.search_nodes(
            label="ProfileMemory", lifecycle_state="active", limit=200
        ):
            properties = node.properties
            if not is_approved_profile_properties(properties):
                continue
            if not _describes_owner(
                self.graph_service.get_node_relationships(node.properties.get("id", "")),
                owner_id,
                str(node.properties.get("id", "")),
            ):
                continue
            value = _text(properties.get("value"))
            key = _text(properties.get("profile_key"))
            if not value or not key:
                continue
            metadata = properties.get("metadata") or {}
            source_ids = properties.get("source_ids") or []
            item = OwnerProfileItem(
                profile_key=key,
                category=_text(properties.get("category")),
                value=value,
                stability=str(properties["stability"]),
                original_user_words=_text(properties.get("original_user_words")),
                assertion_mode=(
                    "inferred" if metadata.get("assertion_mode") == "inferred" else "explicit"
                ),
                source_summary=(
                    f"Source-backed evidence ({len(source_ids)} source reference(s))"
                    if source_ids
                    else None
                ),
            )
            recency = str(properties.get("updated_at") or properties.get("created_at") or "")
            items.append((item.category or "", item.profile_key, recency, item))

        ordered = [item for _, _, _, item in sorted(items, key=lambda value: value[:3])]
        return OwnerProfileSnapshot(
            items=ordered,
            categories=sorted({item.category for item in ordered if item.category}),
            generated_at=datetime.now(UTC),
        )

    def get_approved_profile_for_prompt(self) -> OwnerProfileSnapshot:
        return self.get_approved_profile()


class ProfileMemoryReviewService:
    """Backend-owned approval and rejection operations for profile memories."""

    def __init__(
        self,
        *,
        graph_service: Any,
        owner_manager: OwnerAliasResolver,
        vectorization_service: Any | None = None,
    ) -> None:
        self.graph_service = graph_service
        self.owner_manager = owner_manager
        self.vectorization_service = vectorization_service

    def approve(self, profile_id: str) -> Any:
        node = self._owner_profile(profile_id)
        metadata = dict(node.properties.get("metadata") or {})
        metadata.update({"requires_confirmation": False, "profile_review": {"decision": "approved"}})
        updated = self.graph_service.patch_node(
            profile_id,
            {"stability": "user_confirmed", "visibility": "prompt_allowed", "metadata": metadata},
        )
        self._refresh_vector(profile_id)
        return updated

    def reject(self, profile_id: str, *, reason: str | None = None) -> Any:
        node = self._owner_profile(profile_id)
        metadata = dict(node.properties.get("metadata") or {})
        metadata.update(
            {
                "requires_confirmation": True,
                "profile_review": {"decision": "rejected", "reason": reason},
            }
        )
        updated = self.graph_service.patch_node(profile_id, {"visibility": "hidden", "metadata": metadata})
        self._refresh_vector(profile_id)
        return updated

    def _owner_profile(self, profile_id: str) -> Any:
        owner_id = self.owner_manager.resolve_owner_alias(OWNER_ALIAS)
        node = self.graph_service.get_node(profile_id)
        if node.label != "ProfileMemory":
            raise GraphValidationError("Profile review requires a ProfileMemory node")
        if not _describes_owner(
            self.graph_service.get_node_relationships(profile_id), owner_id, profile_id
        ):
            raise GraphValidationError("Profile review is outside the canonical owner scope")
        return node

    def _refresh_vector(self, profile_id: str) -> None:
        if self.vectorization_service is not None:
            self.vectorization_service.vectorize_targets([profile_id])


def _describes_owner(relationships: Any, owner_id: str, profile_id: str) -> bool:
    for relationship in relationships:
        if (
            getattr(relationship, "type", None) == "DESCRIBES_USER"
            and str(getattr(relationship, "from_id", "")) == profile_id
            and str(getattr(relationship, "to_id", "")) == owner_id
        ):
            return True
    return False


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

