from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from my_digital_brain.core.ids import IdAliasMapper
from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.ingestion.contracts.identity_resolution import (
    ReferenceObjectKind,
    ReferenceRegistryEntry,
    ReferenceStatus,
)


_ALIAS_RE = re.compile(
    r"^(?:OWNER|(?:NODE|REL|MEMORY|CONTEXT|MEDIA|SOURCE|CLAIM)_[0-9]{6})$",
)
_PREFIX_BY_KIND = {
    ReferenceObjectKind.NODE: "NODE",
    ReferenceObjectKind.MEMORY: "MEMORY",
    ReferenceObjectKind.EDGE: "REL",
    ReferenceObjectKind.CONTEXT: "CONTEXT",
    ReferenceObjectKind.MEDIA: "MEDIA",
    ReferenceObjectKind.SOURCE: "SOURCE",
    ReferenceObjectKind.CLAIM: "CLAIM",
}


class RunReferenceRegistry:
    """Backend-owned aliases for one graph-scoped ingestion run."""

    def __init__(self, *, graph_scope: str, run_scope: str) -> None:
        self.graph_scope = _required_scope(graph_scope, "graph_scope")
        self.run_scope = _required_scope(run_scope, "run_scope")
        self._mapper = IdAliasMapper()
        self._entries: dict[str, ReferenceRegistryEntry] = {}
        self._internal_to_ref: dict[str, str] = {}
        self._proposal_bindings: dict[str, str] = {}

    def register_owner(
        self,
        internal_id: str,
        *,
        display_label: str | None = None,
        aliases: list[str] | None = None,
    ) -> str:
        """Register the owner through the trusted owner bootstrap boundary."""

        normalized_id = _internal_id(internal_id)
        existing_ref = self._internal_to_ref.get(normalized_id)
        if existing_ref not in (None, OWNER_ALIAS):
            raise ValueError("The owner internal id is already registered as another reference.")
        existing_owner = self._entries.get(OWNER_ALIAS)
        if existing_owner is not None and existing_owner.backend_id != normalized_id:
            raise ValueError("A run registry cannot contain two owner identities.")
        if existing_owner is not None:
            return OWNER_ALIAS
        entry = ReferenceRegistryEntry(
            ref=OWNER_ALIAS,
            object_kind=ReferenceObjectKind.NODE,
            status=ReferenceStatus.EXISTING,
            label="Person",
            backend_id=normalized_id,
            graph_scope=self.graph_scope,
            session_scope=self.run_scope,
            display_label=display_label,
            aliases=list(aliases or []),
            is_owner=True,
        )
        self._store_entry(entry)
        self._mapper.register_alias(OWNER_ALIAS, normalized_id)
        return OWNER_ALIAS

    def register_existing(
        self,
        internal_id: str,
        *,
        object_kind: ReferenceObjectKind,
        label: str,
        display_label: str | None = None,
        aliases: list[str] | None = None,
    ) -> str:
        normalized_id = _internal_id(internal_id)
        kind = _kind(object_kind)
        if normalized_id == OWNER_ALIAS:
            raise ValueError("OWNER is a model reference, not an internal graph id.")
        existing_ref = self._internal_to_ref.get(normalized_id)
        if existing_ref is not None:
            existing = self._entries[existing_ref]
            if _kind(existing.object_kind) != kind:
                raise ValueError("An internal id cannot be registered as multiple object kinds.")
            return existing.ref

        alias = self._mapper.alias_for(normalized_id, _prefix_for(kind))
        entry = ReferenceRegistryEntry(
            ref=alias,
            object_kind=kind,
            status=ReferenceStatus.EXISTING,
            label=label,
            backend_id=normalized_id,
            graph_scope=self.graph_scope,
            session_scope=self.run_scope,
            display_label=display_label,
            aliases=list(aliases or []),
        )
        self._store_entry(entry)
        return alias

    def register_proposal(
        self,
        proposal_ref: str,
        *,
        object_kind: ReferenceObjectKind = ReferenceObjectKind.NODE,
        label: str,
        display_label: str | None = None,
        aliases: list[str] | None = None,
    ) -> str:
        if not proposal_ref.startswith("CANDIDATE_"):
            raise ValueError("Proposals must use a CANDIDATE_* reference.")
        kind = _kind(object_kind)
        current = self._entries.get(proposal_ref)
        if current is not None:
            if current.status != ReferenceStatus.PROPOSED:
                raise ValueError("An existing reference cannot be reused as a proposal.")
            if _kind(current.object_kind) != kind or current.label != label:
                raise ValueError("A proposal reference cannot change kind or label.")
            return proposal_ref
        entry = ReferenceRegistryEntry(
            ref=proposal_ref,
            object_kind=kind,
            status=ReferenceStatus.PROPOSED,
            label=label,
            graph_scope=self.graph_scope,
            session_scope=self.run_scope,
            display_label=display_label,
            aliases=list(aliases or []),
        )
        self._store_entry(entry)
        return proposal_ref

    def register_local(
        self,
        *,
        object_kind: ReferenceObjectKind,
        label: str,
        display_label: str | None = None,
    ) -> str:
        """Allocate a registry alias for a context object without a graph ID."""

        kind = _kind(object_kind)
        prefix = _prefix_for(kind)
        number = max(
            [
                int(ref.rsplit("_", 1)[1])
                for ref in self._entries
                if ref.startswith(f"{prefix}_") and ref.rsplit("_", 1)[1].isdigit()
            ],
            default=0,
        ) + 1
        ref = f"{prefix}_{number:06d}"
        self._store_entry(
            ReferenceRegistryEntry(
                ref=ref,
                object_kind=kind,
                status=ReferenceStatus.PROPOSED,
                label=label,
                graph_scope=self.graph_scope,
                session_scope=self.run_scope,
                display_label=display_label,
            ),
        )
        return ref

    def bind_proposal(
        self,
        proposal_ref: str,
        internal_id: str,
        *,
        label: str | None = None,
    ) -> str:
        proposal = self._entries.get(proposal_ref)
        if proposal is None or proposal.status != ReferenceStatus.PROPOSED:
            raise ValueError("Only registered proposals can be bound.")
        normalized_id = _internal_id(internal_id)
        previous = self._proposal_bindings.get(proposal_ref)
        if previous is not None and previous != normalized_id:
            raise ValueError("A proposal cannot be rebound to another internal id.")
        existing_alias = self.register_existing(
            normalized_id,
            object_kind=_kind(proposal.object_kind),
            label=label or proposal.label,
            display_label=proposal.display_label,
            aliases=proposal.aliases,
        )
        self._proposal_bindings[proposal_ref] = normalized_id
        return existing_alias

    def resolve(self, ref: str, *, expected_kind: ReferenceObjectKind | None = None) -> str:
        if ref in self._proposal_bindings:
            internal_id = self._proposal_bindings[ref]
            entry = self._entries[ref]
        else:
            entry = self._entries.get(ref)
            if entry is None:
                raise ValueError(f"Unknown or unbound model reference: {ref}")
            if entry.status != ReferenceStatus.EXISTING:
                raise ValueError(f"Model reference is not bound: {ref}")
            internal_id = entry.backend_id
        if internal_id is None:
            raise ValueError(f"Model reference is not bound: {ref}")
        if expected_kind is not None and _kind(entry.object_kind) != _kind(expected_kind):
            raise ValueError(f"Reference has an unexpected object kind: {ref}")
        return internal_id

    def alias_for_internal(self, internal_id: str) -> str:
        normalized_id = _internal_id(internal_id)
        try:
            return self._internal_to_ref[normalized_id]
        except KeyError as exc:
            raise ValueError(f"Internal id is not registered in this run: {internal_id}") from exc

    def entry_for(self, ref: str) -> ReferenceRegistryEntry:
        try:
            return self._entries[ref]
        except KeyError as exc:
            raise ValueError(f"Unknown model reference: {ref}") from exc

    def backend_alias_map(self) -> dict[str, str]:
        result = {
            ref: entry.backend_id
            for ref, entry in self._entries.items()
            if entry.status == ReferenceStatus.EXISTING and entry.backend_id is not None
        }
        result.update(self._proposal_bindings)
        return result

    def model_facing_entries(self) -> list[dict[str, Any]]:
        return [
            entry.model_facing_payload()
            for entry in sorted(self._entries.values(), key=lambda item: item.ref)
        ]

    def snapshot(self) -> dict[str, Any]:
        return {
            "graph_scope": self.graph_scope,
            "run_scope": self.run_scope,
            "entries": [
                entry.model_dump(mode="json")
                for entry in sorted(self._entries.values(), key=lambda item: item.ref)
            ],
            "proposal_bindings": dict(self._proposal_bindings),
        }

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, Any],
        *,
        graph_scope: str | None = None,
        run_scope: str | None = None,
    ) -> "RunReferenceRegistry":
        snapshot_graph_scope = _required_scope(snapshot.get("graph_scope"), "graph_scope")
        snapshot_run_scope = _required_scope(snapshot.get("run_scope"), "run_scope")
        if graph_scope is not None and graph_scope != snapshot_graph_scope:
            raise ValueError("Reference registry graph scope does not match the caller.")
        if run_scope is not None and run_scope != snapshot_run_scope:
            raise ValueError("Reference registry run scope does not match the caller.")
        registry = cls(graph_scope=snapshot_graph_scope, run_scope=snapshot_run_scope)
        for raw_entry in list(snapshot.get("entries") or []):
            registry._store_entry(ReferenceRegistryEntry.model_validate(raw_entry))
        bindings = dict(snapshot.get("proposal_bindings") or {})
        for proposal_ref, internal_id in bindings.items():
            proposal = registry._entries.get(proposal_ref)
            if proposal is None:
                raise ValueError("Registry snapshot contains a binding for an unknown proposal.")
            if proposal.status != ReferenceStatus.PROPOSED:
                raise ValueError("Registry snapshot binds a non-proposed reference.")
            registry.bind_proposal(proposal_ref, _internal_id(internal_id))
        return registry

    def _store_entry(self, entry: ReferenceRegistryEntry) -> None:
        if entry.graph_scope != self.graph_scope or entry.session_scope != self.run_scope:
            raise ValueError("Registry entry scope does not match the registry.")
        if not _ALIAS_RE.fullmatch(entry.ref) and not entry.ref.startswith("CANDIDATE_"):
            raise ValueError(f"Invalid model-facing reference: {entry.ref}")
        current = self._entries.get(entry.ref)
        if current is not None and current != entry:
            raise ValueError(f"Model reference is already registered: {entry.ref}")
        if entry.backend_id is not None:
            normalized_id = _internal_id(entry.backend_id)
            existing_ref = self._internal_to_ref.get(normalized_id)
            if existing_ref not in (None, entry.ref):
                raise ValueError("An internal id is already registered under another reference.")
            self._internal_to_ref[normalized_id] = entry.ref
            self._mapper.register_alias(entry.ref, normalized_id)
        self._entries[entry.ref] = entry


def _kind(value: ReferenceObjectKind | str) -> ReferenceObjectKind:
    return ReferenceObjectKind(value)


def _prefix_for(kind: ReferenceObjectKind) -> str:
    try:
        return _PREFIX_BY_KIND[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported registry object kind: {kind}") from exc


def _internal_id(value: Any) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("Internal ids must not be empty.")
    if normalized == OWNER_ALIAS or _ALIAS_RE.fullmatch(normalized):
        raise ValueError("Internal ids cannot be model-facing aliases.")
    return normalized


def _required_scope(value: Any, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty.")
    return normalized
