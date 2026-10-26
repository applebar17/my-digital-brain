"""Backend-owned allocation and resolution of model-facing references."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from product.application.references.models import (
    OwnerContextDTO,
    ReferenceBindingDTO,
    ReferenceContextDeltaDTO,
    ReferenceEntryDTO,
    ReferenceObjectKind,
    ReferenceResolutionStatus,
)

_PREFIX_BY_KIND = {
    ReferenceObjectKind.NODE: "node",
    ReferenceObjectKind.MEMORY_LOG: "memory",
    ReferenceObjectKind.RELATIONSHIP: "edge",
    ReferenceObjectKind.CONTEXT: "context",
    ReferenceObjectKind.MEDIA: "media",
}


class ReferenceContext:
    """Own coherent model references and private backend bindings for one run."""

    def __init__(self) -> None:
        self._entries: dict[str, ReferenceEntryDTO] = {}
        self._backend_by_ref: dict[str, str] = {}
        self._ref_by_backend: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def register_existing(
        self,
        backend_id: str,
        *,
        object_kind: ReferenceObjectKind,
        label: str | None = None,
        display_name: str | None = None,
        summary: str | None = None,
        aliases: Iterable[str] = (),
    ) -> ReferenceEntryDTO:
        """Register a persisted object or reuse its reference from this run.

        Dependencies:
            Callers obtain ``backend_id`` from trusted deterministic storage.
            The identifier remains private to this service and typed deltas.
        """
        normalized_backend_id = self._required_text(backend_id, "backend_id")
        existing_ref = self._ref_by_backend.get(normalized_backend_id)
        if existing_ref is not None:
            existing = self._entries[existing_ref]
            if existing.object_kind != object_kind:
                raise ValueError(
                    "The backend object is already registered as "
                    f"{existing.object_kind.value}, not {object_kind.value}."
                )
            enriched = self._enrich_entry(
                existing,
                label=label,
                display_name=display_name,
                summary=summary,
                aliases=aliases,
            )
            self._entries[existing_ref] = enriched
            return enriched

        entry = ReferenceEntryDTO(
            ref=self._allocate_ref(object_kind, proposed=False, label=label),
            object_kind=object_kind,
            label=self._optional_text(label),
            display_name=self._optional_text(display_name),
            summary=self._optional_text(summary),
            aliases=self._normalize_aliases(aliases),
            resolution_status=ReferenceResolutionStatus.EXISTING,
        )
        self._store(entry, backend_id=normalized_backend_id)
        return entry

    def allocate_proposed(
        self,
        *,
        object_kind: ReferenceObjectKind,
        label: str | None = None,
        display_name: str | None = None,
        summary: str | None = None,
        aliases: Iterable[str] = (),
    ) -> ReferenceEntryDTO:
        """Allocate an unbound reference for an object proposed during this run."""
        entry = ReferenceEntryDTO(
            ref=self._allocate_ref(object_kind, proposed=True, label=label),
            object_kind=object_kind,
            label=self._optional_text(label),
            display_name=self._optional_text(display_name),
            summary=self._optional_text(summary),
            aliases=self._normalize_aliases(aliases),
            resolution_status=ReferenceResolutionStatus.PROPOSED,
        )
        self._store(entry)
        return entry

    def bind_created(self, ref: str, backend_id: str) -> ReferenceEntryDTO:
        """Bind a proposed reference after a successful deterministic write."""
        entry = self.entry_for(ref)
        if entry.resolution_status not in {
            ReferenceResolutionStatus.PROPOSED,
            ReferenceResolutionStatus.CREATED,
        }:
            raise ValueError(
                f"Reference '{ref}' represents an existing object and cannot be rebound."
            )
        normalized_backend_id = self._required_text(backend_id, "backend_id")
        existing_ref = self._ref_by_backend.get(normalized_backend_id)
        if existing_ref not in {None, ref}:
            raise ValueError(
                f"The backend object is already mapped to reference '{existing_ref}'."
            )
        current_backend_id = self._backend_by_ref.get(ref)
        if current_backend_id not in {None, normalized_backend_id}:
            raise ValueError(f"Reference '{ref}' is already bound to another backend object.")

        created = entry.model_copy(
            update={"resolution_status": ReferenceResolutionStatus.CREATED}
        )
        self._entries[ref] = created
        self._bind(ref, normalized_backend_id)
        return created

    def register_owner(
        self,
        backend_id: str,
        *,
        name: str | None = None,
        surname: str | None = None,
    ) -> OwnerContextDTO:
        """Register the active owner using a safe readable model-facing identifier."""
        normalized_name = self._optional_text(name)
        normalized_surname = self._optional_text(surname)
        owner_ref = self._owner_ref(normalized_name, normalized_surname)
        normalized_backend_id = self._required_text(backend_id, "backend_id")

        current = self._entries.get(owner_ref)
        if current is None:
            display_name = " ".join(
                value for value in (normalized_name, normalized_surname) if value
            ) or None
            self._store(
                ReferenceEntryDTO(
                    ref=owner_ref,
                    object_kind=ReferenceObjectKind.NODE,
                    label="Person",
                    display_name=display_name,
                    summary=None,
                    aliases=[],
                    resolution_status=ReferenceResolutionStatus.EXISTING,
                ),
                backend_id=normalized_backend_id,
            )
        elif self._backend_by_ref.get(owner_ref) != normalized_backend_id:
            raise ValueError(
                f"Owner reference '{owner_ref}' is already bound to another backend identity."
            )
        return OwnerContextDTO(id=owner_ref, name=normalized_name, surname=normalized_surname)

    def resolve(
        self,
        ref: str,
        *,
        expected_kind: ReferenceObjectKind | None = None,
    ) -> str:
        """Resolve a supplied active reference before a deterministic service call."""
        entry = self.entry_for(ref)
        if expected_kind is not None and entry.object_kind != expected_kind:
            raise ValueError(
                f"Reference '{ref}' represents {entry.object_kind.value}, but this operation "
                f"requires {expected_kind.value}. Use a supplied {expected_kind.value} reference."
            )
        backend_id = self._backend_by_ref.get(ref)
        if backend_id is None:
            raise ValueError(
                f"Reference '{ref}' is proposed but not yet bound to a persisted object. "
                "Create it successfully before using it in this operation."
            )
        return backend_id

    def entry_for(self, ref: str) -> ReferenceEntryDTO:
        """Return one model-facing entry or explain how a caller can recover."""
        try:
            return self._entries[ref]
        except KeyError as error:
            raise ValueError(
                f"Unknown reference '{ref}'. Use an exact reference supplied in the active "
                "reference context or search for the object first."
            ) from error

    def ref_for_backend_id(self, backend_id: str) -> str | None:
        """Return the active local reference for a trusted backend identifier."""
        return self._ref_by_backend.get(self._required_text(backend_id, "backend_id"))

    def entries(self, refs: Iterable[str] | None = None) -> list[ReferenceEntryDTO]:
        """Return model-facing entries in stable allocation order."""
        if refs is None:
            return list(self._entries.values())
        return [self.entry_for(ref) for ref in refs]

    def export_delta(self, refs: Iterable[str]) -> ReferenceContextDeltaDTO:
        """Export selected entries and their private bindings for a trusted parent."""
        entries = self.entries(refs)
        bindings = [
            ReferenceBindingDTO(ref=entry.ref, backend_id=self._backend_by_ref[entry.ref])
            for entry in entries
            if entry.ref in self._backend_by_ref
        ]
        return ReferenceContextDeltaDTO(entries=entries, bindings=bindings)

    def snapshot(self) -> ReferenceContextDeltaDTO:
        """Return the complete typed state needed to resume this run-scoped mapping."""
        return self.export_delta(self._entries)

    @classmethod
    def from_snapshot(cls, snapshot: ReferenceContextDeltaDTO) -> ReferenceContext:
        """Restore a persisted mapping without exposing its bindings to an LLM."""
        context = cls()
        context.merge_delta(snapshot)
        return context

    def merge_delta(self, delta: ReferenceContextDeltaDTO) -> None:
        """Merge a child result without silently changing any reference identity."""
        binding_by_ref = {binding.ref: binding.backend_id for binding in delta.bindings}
        if len(binding_by_ref) != len(delta.bindings):
            raise ValueError("A reference delta cannot contain duplicate private bindings.")

        entry_refs = {entry.ref for entry in delta.entries}
        unknown_binding_refs = set(binding_by_ref).difference(entry_refs)
        if unknown_binding_refs:
            refs = ", ".join(sorted(unknown_binding_refs))
            raise ValueError(f"Reference delta contains bindings without entries: {refs}.")

        for entry in delta.entries:
            backend_id = binding_by_ref.get(entry.ref)
            current = self._entries.get(entry.ref)
            merged = self._merge_entry(current, entry) if current is not None else entry
            if (
                merged.resolution_status != ReferenceResolutionStatus.PROPOSED
                and backend_id is None
                and entry.ref not in self._backend_by_ref
            ):
                raise ValueError(
                    f"Resolved reference '{entry.ref}' has no private backend binding in "
                    "the child delta."
                )
            if backend_id is not None:
                mapped_ref = self._ref_by_backend.get(backend_id)
                if mapped_ref not in {None, entry.ref}:
                    raise ValueError(
                        f"The backend object is already mapped to reference '{mapped_ref}', "
                        f"not '{entry.ref}'."
                    )
            if current is not None:
                self._entries.pop(entry.ref)
            self._store(merged, backend_id=backend_id)

    def _store(self, entry: ReferenceEntryDTO, *, backend_id: str | None = None) -> None:
        current = self._entries.get(entry.ref)
        if current is not None and current != entry:
            raise ValueError(f"Reference '{entry.ref}' is already registered differently.")
        if backend_id is not None:
            mapped_ref = self._ref_by_backend.get(backend_id)
            if mapped_ref not in {None, entry.ref}:
                raise ValueError(
                    f"The backend object is already mapped to reference '{mapped_ref}'."
                )
        self._entries[entry.ref] = entry
        if backend_id is not None:
            self._bind(entry.ref, backend_id)
        self._observe_counter(entry.ref)

    def _bind(self, ref: str, backend_id: str) -> None:
        self._backend_by_ref[ref] = backend_id
        self._ref_by_backend[backend_id] = ref

    def _allocate_ref(
        self,
        object_kind: ReferenceObjectKind,
        *,
        proposed: bool,
        label: str | None,
    ) -> str:
        if object_kind == ReferenceObjectKind.CANDIDATE:
            base = f"candidate_{self._slug(label) or 'object'}"
        else:
            try:
                base = _PREFIX_BY_KIND[object_kind]
            except KeyError as error:
                raise ValueError(
                    f"No reference family is configured for {object_kind.value}."
                ) from error
            if proposed:
                base = f"{base}_new"
        counter = self._counters.get(base, 0) + 1
        self._counters[base] = counter
        return f"{base}_{counter:04d}"

    def _observe_counter(self, ref: str) -> None:
        match = re.fullmatch(r"(.+)_([0-9]+)", ref)
        if match is None:
            return
        base, raw_counter = match.groups()
        self._counters[base] = max(self._counters.get(base, 0), int(raw_counter))

    @classmethod
    def _enrich_entry(
        cls,
        entry: ReferenceEntryDTO,
        *,
        label: str | None,
        display_name: str | None,
        summary: str | None,
        aliases: Iterable[str],
    ) -> ReferenceEntryDTO:
        updates: dict[str, object] = {}
        for field_name, supplied in (
            ("label", cls._optional_text(label)),
            ("display_name", cls._optional_text(display_name)),
            ("summary", cls._optional_text(summary)),
        ):
            current = getattr(entry, field_name)
            if current is None and supplied is not None:
                updates[field_name] = supplied
        merged_aliases = cls._normalize_aliases([*entry.aliases, *aliases])
        if merged_aliases != entry.aliases:
            updates["aliases"] = merged_aliases
        return entry.model_copy(update=updates) if updates else entry

    @classmethod
    def _merge_entry(
        cls,
        current: ReferenceEntryDTO,
        incoming: ReferenceEntryDTO,
    ) -> ReferenceEntryDTO:
        if current.object_kind != incoming.object_kind:
            raise ValueError(
                f"Reference '{current.ref}' cannot change from {current.object_kind.value} "
                f"to {incoming.object_kind.value}."
            )
        if current.label and incoming.label and current.label != incoming.label:
            raise ValueError(f"Reference '{current.ref}' cannot change its domain label.")

        allowed_statuses = {
            (current.resolution_status, current.resolution_status),
            (
                ReferenceResolutionStatus.PROPOSED,
                ReferenceResolutionStatus.CREATED,
            ),
        }
        status_pair = (current.resolution_status, incoming.resolution_status)
        if status_pair not in allowed_statuses:
            raise ValueError(
                f"Reference '{current.ref}' cannot change status from "
                f"{current.resolution_status.value} to {incoming.resolution_status.value}."
            )

        return current.model_copy(
            update={
                "label": current.label or incoming.label,
                "display_name": current.display_name or incoming.display_name,
                "summary": current.summary or incoming.summary,
                "aliases": cls._normalize_aliases([*current.aliases, *incoming.aliases]),
                "resolution_status": incoming.resolution_status,
            }
        )

    @staticmethod
    def _normalize_aliases(values: Iterable[str]) -> list[str]:
        aliases: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in seen:
                aliases.append(normalized)
                seen.add(normalized)
        return aliases

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def _owner_ref(cls, name: str | None, surname: str | None) -> str:
        if not name or not surname:
            return "owner"
        return f"{cls._slug(name)}_{cls._slug(surname)}"

    @staticmethod
    def _slug(value: str | None) -> str:
        if not value:
            return ""
        ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
