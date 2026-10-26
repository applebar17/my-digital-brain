"""Canonical model-facing rendering for run-scoped reference entries."""

import json
from collections.abc import Iterable

from product.application.references.models import OwnerContextDTO, ReferenceEntryDTO


class ReferenceContextRenderer:
    """Render one reference inventory consistently at verbosity levels zero to two."""

    def render(self, entries: Iterable[ReferenceEntryDTO], *, level: int = 1) -> str:
        """Render selected model-safe entries without exposing private bindings."""
        if level not in {0, 1, 2}:
            raise ValueError("Reference rendering level must be 0, 1, or 2.")
        selected = list(entries)
        if level == 0:
            return json.dumps(
                [self._compact_entry(entry) for entry in selected],
                ensure_ascii=False,
                indent=2,
            )
        if not selected:
            return "No model-facing references are available."
        return "\n".join(self._natural_entry(entry, level=level) for entry in selected)

    def render_owner(self, owner: OwnerContextDTO) -> str:
        """Render the safe owner projection as a named context section."""
        display_name = " ".join(value for value in (owner.name, owner.surname) if value)
        target = display_name or "the current owner"
        return f"Current owner:\n- `{owner.id}` refers to {target}."

    @staticmethod
    def _compact_entry(entry: ReferenceEntryDTO) -> dict[str, str | None]:
        return {
            "ref": entry.ref,
            "object_kind": entry.object_kind.value,
            "label": entry.label,
            "display_name": entry.display_name,
            "summary": entry.summary,
        }

    @staticmethod
    def _natural_entry(entry: ReferenceEntryDTO, *, level: int) -> str:
        object_label = entry.label or entry.object_kind.value.replace("_", " ")
        readable = entry.display_name or entry.summary
        descriptor = f'the {object_label} "{readable}"' if readable else f"a {object_label}"
        line = f"- `{entry.ref}` refers to {descriptor}."
        if level == 1:
            return line

        details = [f"Status: {entry.resolution_status.value}."]
        if entry.aliases:
            details.append(f"Known aliases: {', '.join(entry.aliases)}.")
        details.append(f"Use `{entry.ref}` exactly when referring to this object.")
        return f"{line} {' '.join(details)}"
