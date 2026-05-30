from __future__ import annotations

from my_digital_brain.core.enums import LifecycleState, PrivacyLevel, TrustLevel


def test_trust_level_values_match_docs() -> None:
    assert {item.value for item in TrustLevel} == {
        "user_confirmed",
        "source_stated",
        "llm_inferred",
        "system_derived",
        "externally_enriched",
        "contradicted",
        "stale",
    }


def test_privacy_level_values_match_docs() -> None:
    assert {item.value for item in PrivacyLevel} == {
        "normal",
        "private",
        "sensitive",
        "local_only",
        "hidden",
    }


def test_lifecycle_state_values_match_docs() -> None:
    assert {item.value for item in LifecycleState} == {
        "candidate",
        "active",
        "confirmed",
        "inferred",
        "disputed",
        "stale",
        "expired",
        "archived",
        "deleted",
    }
