"""Caller-configurable prompt rendering for model-safe memory-search results."""

import json

from product.application.tools.memory_search.models import (
    MemorySearchRenderLevel,
    MemorySearchToolResultDTO,
)


class MemorySearchResultRenderer:
    """Render one typed search packet at a caller-selected detail level."""

    def render(
        self,
        result: MemorySearchToolResultDTO,
        *,
        level: MemorySearchRenderLevel = MemorySearchRenderLevel.STANDARD,
    ) -> str:
        """Render only model-safe fields already present in the search result."""
        resolved_level = MemorySearchRenderLevel(level)
        if resolved_level == MemorySearchRenderLevel.COMPACT:
            return self._compact(result)
        return self._readable(result, detailed=resolved_level == MemorySearchRenderLevel.DETAILED)

    @staticmethod
    def _compact(result: MemorySearchToolResultDTO) -> str:
        packet = {
            "seed_refs": result.seed_refs,
            "objects": [
                {
                    "ref": item.ref,
                    "kind": item.object_kind.value,
                    "label": item.label,
                    "name": item.display_name,
                }
                for item in result.objects
            ],
            "relationships": [
                {
                    "ref": item.ref,
                    "type": item.label,
                    "from_ref": item.from_ref,
                    "to_ref": item.to_ref,
                }
                for item in result.relationships
            ],
        }
        if result.truncated:
            packet["truncated"] = True
        return json.dumps(packet, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _readable(result: MemorySearchToolResultDTO, *, detailed: bool) -> str:
        if not result.objects and not result.relationships:
            return "No matching memory context was found."

        lines: list[str] = []
        if result.seed_refs:
            lines.append(f"Search seeds: {', '.join(f'`{ref}`' for ref in result.seed_refs)}")
        if result.objects:
            lines.append("Objects:")
            for item in result.objects:
                descriptor = (
                    item.display_name or item.summary or item.label or item.object_kind.value
                )
                line = f"- `{item.ref}`: {descriptor}"
                if item.summary and item.summary != descriptor:
                    line = f"{line}. {item.summary}"
                if detailed:
                    details = [f"status={item.resolution_status.value}"]
                    if item.aliases:
                        details.append(f"aliases={', '.join(item.aliases)}")
                    if item.temporal_summary:
                        details.append(f"time={item.temporal_summary}")
                    line = f"{line} ({'; '.join(details)})"
                lines.append(line)
        if result.relationships:
            lines.append("Relationships:")
            for item in result.relationships:
                relationship_type = item.label or item.display_name or "related to"
                line = (
                    f"- `{item.ref}`: `{item.from_ref}` {relationship_type} `{item.to_ref}`"
                )
                if item.summary:
                    line = f"{line}. {item.summary}"
                if detailed and item.temporal_summary:
                    line = f"{line} (time={item.temporal_summary})"
                lines.append(line)
        if result.truncated:
            lines.append("Additional matching context exists beyond this bounded result.")
        return "\n".join(lines)
