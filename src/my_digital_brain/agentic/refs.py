from __future__ import annotations

import re
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.agentic.base import AgenticModel
from my_digital_brain.agentic.enums import (
    PacketDetailProfile,
    RefObjectKind,
    RefResolutionStatus,
)

_REF_RE = re.compile(
    r"^(node|memory|edge|context|media)(?:_new)?_[0-9]{4}$",
)
_KIND_PREFIX = {
    RefObjectKind.NODE: "node",
    RefObjectKind.MEMORY: "memory",
    RefObjectKind.EDGE: "edge",
    RefObjectKind.CONTEXT: "context",
    RefObjectKind.MEDIA: "media",
}
_CONTEXT_LABELS = {
    "Claim",
    "Perception",
    "RelationshipContext",
    "RelationshipState",
    "ProfileMemory",
}
_BACKEND_NOISE_KEYS = {
    "id",
    "metadata",
    "metadata_json",
    "backend_id",
    "vector_id",
    "collection",
    "prompt",
    "prompt_trace",
    "trace",
    "audit",
    "audit_fields",
    "raw_payload",
    "source_payload",
    "provider_raw_metadata",
}


class RefEntry(AgenticModel):
    ref: str
    object_kind: RefObjectKind
    label: str | None = None
    type: str | None = None
    name: str | None = None
    summary: str | None = None
    aliases: list[str] = Field(default_factory=list)
    backend_id: str | None = None
    source: str | None = None
    resolution_status: RefResolutionStatus = RefResolutionStatus.EXISTING
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_ref(self) -> "RefEntry":
        _validate_ref_for_kind(self.ref, self.object_kind)
        return self

    def model_facing_packet(
        self,
        profile: PacketDetailProfile = PacketDetailProfile.MEDIUM,
    ) -> dict[str, Any]:
        profile = PacketDetailProfile(profile)
        packet: dict[str, Any] = {
            "ref": self.ref,
            "kind": RefObjectKind(self.object_kind).value,
        }
        if self.label:
            packet["label"] = self.label
        if self.type:
            packet["type"] = self.type
        title = self.name or self.summary
        if title:
            packet["name" if self.name else "summary"] = title
        if profile == PacketDetailProfile.SHORT:
            return _drop_empty(packet)
        if self.name and self.summary:
            packet["summary"] = self.summary
        if self.aliases:
            packet["aliases"] = list(self.aliases)
        packet["resolution_status"] = RefResolutionStatus(self.resolution_status).value
        if profile == PacketDetailProfile.LONG and self.diagnostics:
            packet["diagnostics"] = list(self.diagnostics)
        return _drop_empty(packet)


class RefContext(AgenticModel):
    session_id: str | None = None
    entries: dict[str, RefEntry] = Field(default_factory=dict)
    counters: dict[str, int] = Field(default_factory=dict)

    def allocate_ref(self, object_kind: RefObjectKind | str, *, proposed: bool = False) -> str:
        kind = RefObjectKind(object_kind)
        key = f"{kind.value}{'_new' if proposed else ''}"
        next_value = int(self.counters.get(key, 0)) + 1
        self.counters[key] = next_value
        prefix = _KIND_PREFIX[kind]
        middle = "_new" if proposed else ""
        return f"{prefix}{middle}_{next_value:04d}"

    def add_entry(self, entry: RefEntry) -> RefEntry:
        if entry.ref in self.entries:
            raise ValueError(f"Ref already exists in this session: {entry.ref}")
        _validate_ref_for_kind(entry.ref, entry.object_kind)
        self.entries[entry.ref] = entry
        return entry

    def add_hydrated(
        self,
        object_kind: RefObjectKind | str,
        *,
        backend_id: str | None = None,
        label: str | None = None,
        type: str | None = None,
        name: str | None = None,
        summary: str | None = None,
        aliases: list[str] | None = None,
        source: str | None = "hydrated_context",
    ) -> RefEntry:
        ref = self.allocate_ref(object_kind, proposed=False)
        return self.add_entry(
            RefEntry(
                ref=ref,
                object_kind=RefObjectKind(object_kind),
                label=label,
                type=type,
                name=name,
                summary=summary,
                aliases=list(aliases or []),
                backend_id=backend_id,
                source=source,
                resolution_status=RefResolutionStatus.EXISTING,
            ),
        )

    def add_proposed(
        self,
        object_kind: RefObjectKind | str,
        *,
        label: str | None = None,
        type: str | None = None,
        name: str | None = None,
        summary: str | None = None,
        aliases: list[str] | None = None,
        source: str | None = None,
    ) -> RefEntry:
        ref = self.allocate_ref(object_kind, proposed=True)
        return self.add_entry(
            RefEntry(
                ref=ref,
                object_kind=RefObjectKind(object_kind),
                label=label,
                type=type,
                name=name,
                summary=summary,
                aliases=list(aliases or []),
                source=source,
                resolution_status=RefResolutionStatus.PROPOSED,
            ),
        )

    def get_entry(self, ref: str) -> RefEntry:
        try:
            return self.entries[ref]
        except KeyError as exc:
            raise ValueError(f"Unknown ref: {ref}") from exc

    def resolve_backend_id(
        self,
        ref: str,
        backend_id: str,
        *,
        status: RefResolutionStatus | str = RefResolutionStatus.RESOLVED,
    ) -> RefEntry:
        entry = self.get_entry(ref)
        entry.backend_id = backend_id
        entry.resolution_status = RefResolutionStatus(status)
        return entry

    def ref_for_backend_id(self, backend_id: str) -> str | None:
        for entry in self.entries.values():
            if entry.backend_id == backend_id:
                return entry.ref
        return None

    def backend_id_for_ref(self, ref: str) -> str:
        entry = self.get_entry(ref)
        if not entry.backend_id:
            raise ValueError(f"Ref has no backend id: {ref}")
        return entry.backend_id

    def model_facing_packet(
        self,
        profile: PacketDetailProfile | str = PacketDetailProfile.MEDIUM,
    ) -> list[dict[str, Any]]:
        resolved_profile = PacketDetailProfile(profile)
        return [entry.model_facing_packet(resolved_profile) for entry in self.entries.values()]

    def delta_packet(
        self,
        refs: list[str],
        profile: PacketDetailProfile | str = PacketDetailProfile.MEDIUM,
    ) -> dict[str, Any]:
        resolved_profile = PacketDetailProfile(profile)
        return {
            "refs": [self.get_entry(ref).model_facing_packet(resolved_profile) for ref in refs],
        }

    def merge_delta(self, other: "RefContext") -> None:
        for ref, entry in other.entries.items():
            if ref in self.entries and self.entries[ref] != entry:
                raise ValueError(f"Conflicting ref during merge: {ref}")
            self.entries[ref] = entry
        for key, value in other.counters.items():
            self.counters[key] = max(int(self.counters.get(key, 0)), int(value))


class RefPacketBuilder:
    def build_packet(
        self,
        value: Any,
        *,
        ref_context: RefContext | None = None,
        profile: PacketDetailProfile | str = PacketDetailProfile.MEDIUM,
        ref: str | None = None,
        object_kind: RefObjectKind | str | None = None,
        state_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del state_overrides
        resolved_profile = PacketDetailProfile(profile)
        normalized = _normalize_object(value)
        kind = RefObjectKind(object_kind) if object_kind else _infer_kind(normalized)
        label = normalized.get("label")
        type_value = normalized.get("type")
        backend_id = _backend_id(normalized)
        resolved_ref = ref or (ref_context.ref_for_backend_id(backend_id) if ref_context and backend_id else None)
        if not resolved_ref and ref_context is not None:
            entry = ref_context.add_hydrated(
                kind,
                backend_id=backend_id,
                label=label,
                type=type_value,
                name=_display_name(normalized),
                summary=_summary(normalized),
                aliases=_aliases(normalized),
            )
            resolved_ref = entry.ref
        if not resolved_ref:
            raise ValueError("A ref or RefContext with backend id mapping is required.")
        packet = RefEntry(
            ref=resolved_ref,
            object_kind=kind,
            label=label,
            type=type_value,
            name=_display_name(normalized),
            summary=_summary(normalized),
            aliases=_aliases(normalized),
            resolution_status=RefResolutionStatus.EXISTING,
        ).model_facing_packet(resolved_profile)
        if kind == RefObjectKind.EDGE:
            from_ref = _endpoint_ref(normalized.get("from_id"), ref_context)
            to_ref = _endpoint_ref(normalized.get("to_id"), ref_context)
            if from_ref:
                packet["from_ref"] = from_ref
            if to_ref:
                packet["to_ref"] = to_ref
        if resolved_profile != PacketDetailProfile.SHORT:
            _add_hints(packet, normalized, kind)
        return _drop_empty(packet)


def build_ref_packet(
    value: Any,
    *,
    ref_context: RefContext | None = None,
    profile: PacketDetailProfile | str = PacketDetailProfile.MEDIUM,
    ref: str | None = None,
    object_kind: RefObjectKind | str | None = None,
    state_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return RefPacketBuilder().build_packet(
        value,
        ref_context=ref_context,
        profile=profile,
        ref=ref,
        object_kind=object_kind,
        state_overrides=state_overrides,
    )


def _validate_ref_for_kind(ref: str, object_kind: RefObjectKind | str) -> None:
    kind = RefObjectKind(object_kind)
    if not _REF_RE.match(ref):
        raise ValueError(f"Malformed ref: {ref}")
    expected = _KIND_PREFIX[kind]
    if not (ref.startswith(f"{expected}_") or ref.startswith(f"{expected}_new_")):
        raise ValueError(f"Ref '{ref}' does not match object kind '{kind.value}'.")


def _normalize_object(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="json", exclude_none=True)
    elif isinstance(value, dict):
        data = dict(value)
    else:
        data = {
            key: getattr(value, key)
            for key in ("label", "labels", "properties", "type", "from_id", "to_id")
            if hasattr(value, key)
        }
    if "properties" in data and isinstance(data["properties"], dict):
        props = dict(data["properties"])
        merged = {**props, **{key: item for key, item in data.items() if key != "properties"}}
        if "label" not in merged and data.get("label"):
            merged["label"] = data["label"]
        return merged
    return data


def _infer_kind(data: dict[str, Any]) -> RefObjectKind:
    label = str(data.get("label") or "")
    if data.get("from_id") and data.get("to_id"):
        return RefObjectKind.EDGE
    if label == "MemoryLog":
        return RefObjectKind.MEMORY
    if label == "MediaAsset":
        return RefObjectKind.MEDIA
    if label in _CONTEXT_LABELS:
        return RefObjectKind.CONTEXT
    return RefObjectKind.NODE


def _backend_id(data: dict[str, Any]) -> str | None:
    value = data.get("id") or data.get("backend_id")
    return str(value) if value else None


def _display_name(data: dict[str, Any]) -> str | None:
    for key in (
        "display_name",
        "name",
        "title",
        "label_text",
        "profile_key",
        "relationship_type",
        "type",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _summary(data: dict[str, Any]) -> str | None:
    for key in (
        "summary",
        "description",
        "log_text",
        "text",
        "value",
        "relationship_detail",
        "caption",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _aliases(data: dict[str, Any]) -> list[str]:
    aliases = data.get("aliases")
    if isinstance(aliases, list):
        return [str(alias) for alias in aliases if str(alias).strip()]
    return []


def _endpoint_ref(value: Any, ref_context: RefContext | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if ref_context is None:
        return text if _REF_RE.match(text) else None
    if text in ref_context.entries:
        return text
    return ref_context.ref_for_backend_id(text)


def _add_hints(packet: dict[str, Any], data: dict[str, Any], kind: RefObjectKind) -> None:
    for source_key, target_key in (
        ("happened_at", "time_hint"),
        ("started_at", "time_hint"),
        ("source_kind", "source_hint"),
        ("city", "place_hint"),
    ):
        value = data.get(source_key)
        if value and target_key not in packet:
            packet[target_key] = value
    if kind == RefObjectKind.MEMORY:
        for key in (
            "primary_host_ref",
            "primary_host_target_ref",
            "primary_host_target_id",
            "involved_refs",
            "involved_target_refs",
            "relationship_context_refs",
        ):
            value = data.get(key)
            if value:
                packet[key] = value


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in _BACKEND_NOISE_KEYS and item not in (None, "", [], {})
    }