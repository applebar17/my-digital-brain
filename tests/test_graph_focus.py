from __future__ import annotations

from my_digital_brain.rag.graph_focus import SearchGraphFocusSelector
from my_digital_brain.rag.models import SemanticMemoryHit


def test_otsu_focus_selector_keeps_high_score_cluster_by_default() -> None:
    selector = SearchGraphFocusSelector()

    selection = selector.select(
        [
            _hit("brother", 0.98),
            _hit("roommate-a", 0.60),
            _hit("roommate-b", 0.55),
        ],
        mode="adaptive",
    )

    assert selection.algorithm == "otsu"
    assert selection.selected_target_ids == ["brother"]
    assert selection.excluded_target_ids == ["roommate-a", "roommate-b"]
    assert selection.threshold == 0.79


def test_otsu_focus_selector_keeps_multiple_close_high_score_hits() -> None:
    selector = SearchGraphFocusSelector()

    selection = selector.select(
        [
            _hit("roommate-a", 0.92),
            _hit("roommate-b", 0.90),
            _hit("roommate-c", 0.88),
            _hit("weak-memory", 0.50),
        ],
        mode="adaptive",
    )

    assert selection.selected_target_ids == ["roommate-a", "roommate-b", "roommate-c"]
    assert selection.excluded_target_ids == ["weak-memory"]


def test_knee_focus_selector_is_available_for_later_comparison() -> None:
    selector = SearchGraphFocusSelector(algorithm="knee")

    selection = selector.select(
        [
            _hit("primary", 0.99),
            _hit("nearby", 0.94),
            _hit("weak-a", 0.45),
            _hit("weak-b", 0.40),
        ],
        mode="adaptive",
    )

    assert selection.algorithm == "knee"
    assert selection.selected_target_ids == ["primary", "nearby"]


def _hit(target_id: str, score: float) -> SemanticMemoryHit:
    return SemanticMemoryHit(
        rank=0,
        score=score,
        source="semantic",
        primary_target_id=target_id,
        primary_target_label="Person",
    )
