from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from my_digital_brain.rag.models import SemanticMemoryHit

GraphFocusMode = Literal["broad", "adaptive"]
GraphFocusAlgorithm = Literal["otsu", "knee"]


@dataclass(frozen=True)
class GraphFocusSelection:
    mode: GraphFocusMode
    algorithm: GraphFocusAlgorithm | None
    selected_hits: tuple[SemanticMemoryHit, ...]
    excluded_hits: tuple[SemanticMemoryHit, ...]
    threshold: float | None
    reason: str

    @property
    def selected_target_ids(self) -> list[str]:
        return [_hit_target_id(hit) for hit in self.selected_hits]

    @property
    def excluded_target_ids(self) -> list[str]:
        return [_hit_target_id(hit) for hit in self.excluded_hits]


class SearchGraphFocusSelector:
    """Select retrieval hits that should drive user-facing graph rendering."""

    def __init__(
        self,
        *,
        algorithm: GraphFocusAlgorithm = "otsu",
        fallback_hit_count: int = 5,
        max_focus_hits: int = 8,
    ) -> None:
        self.algorithm = algorithm
        self.fallback_hit_count = fallback_hit_count
        self.max_focus_hits = max_focus_hits

    def select(
        self,
        hits: list[SemanticMemoryHit],
        *,
        mode: GraphFocusMode = "broad",
    ) -> GraphFocusSelection:
        if mode == "broad" or len(hits) <= 1:
            return GraphFocusSelection(
                mode=mode,
                algorithm=None if mode == "broad" else self.algorithm,
                selected_hits=tuple(hits),
                excluded_hits=(),
                threshold=None,
                reason="broad" if mode == "broad" else "single_hit",
            )

        selected_count, threshold, reason = (
            self._select_with_knee(hits)
            if self.algorithm == "knee"
            else self._select_with_otsu(hits)
        )
        selected_count = min(max(selected_count, 1), len(hits), self.max_focus_hits)
        return GraphFocusSelection(
            mode=mode,
            algorithm=self.algorithm,
            selected_hits=tuple(hits[:selected_count]),
            excluded_hits=tuple(hits[selected_count:]),
            threshold=threshold,
            reason=reason,
        )

    def _select_with_otsu(
        self,
        hits: list[SemanticMemoryHit],
    ) -> tuple[int, float | None, str]:
        scores = [hit.score for hit in hits]
        if len(set(scores)) <= 1:
            return min(len(hits), self.fallback_hit_count), None, "no_score_variance"

        best_index = 1
        best_variance = -1.0
        best_threshold: float | None = None
        for index in range(1, len(scores)):
            high = scores[:index]
            low = scores[index:]
            high_mean = sum(high) / len(high)
            low_mean = sum(low) / len(low)
            between_variance = len(high) * len(low) * (high_mean - low_mean) ** 2
            if between_variance > best_variance:
                best_index = index
                best_variance = between_variance
                best_threshold = (scores[index - 1] + scores[index]) / 2

        return best_index, best_threshold, "otsu_between_class_variance"

    def _select_with_knee(
        self,
        hits: list[SemanticMemoryHit],
    ) -> tuple[int, float | None, str]:
        scores = [hit.score for hit in hits]
        if len(set(scores)) <= 1:
            return min(len(hits), self.fallback_hit_count), None, "no_score_variance"

        gaps = [scores[index] - scores[index + 1] for index in range(len(scores) - 1)]
        selected_count = gaps.index(max(gaps)) + 1
        threshold = (scores[selected_count - 1] + scores[selected_count]) / 2
        return selected_count, threshold, "knee_largest_score_gap"


def _hit_target_id(hit: SemanticMemoryHit) -> str:
    return hit.canonical_target_id or hit.primary_target_id
