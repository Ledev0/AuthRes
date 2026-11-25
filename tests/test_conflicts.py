"""Tests for the descriptive ALLOW/DENY conflict classifier."""

from __future__ import annotations

from authres.compare.conflicts import has_conflict
from authres.core.models import AccessRequest, Effect, Policy
from authres.core.policy import PolicySet

REQUEST = AccessRequest("alice", "report", "read")


def make_set(*effects: Effect) -> PolicySet:
    return PolicySet(
        policies=tuple(
            Policy(
                "alice",
                "report",
                "read",
                effect,
                policy_id=f"p{index}",
            )
            for index, effect in enumerate(effects)
        )
    )


class TestConflictClassification:
    def test_allow_and_deny_matching_is_a_conflict(self) -> None:
        assert has_conflict(make_set(Effect.ALLOW, Effect.DENY), REQUEST)

    def test_order_does_not_matter(self) -> None:
        assert has_conflict(make_set(Effect.DENY, Effect.ALLOW), REQUEST)

    def test_allow_only_is_not_a_conflict(self) -> None:
        assert not has_conflict(make_set(Effect.ALLOW, Effect.ALLOW), REQUEST)

    def test_deny_only_is_not_a_conflict(self) -> None:
        assert not has_conflict(make_set(Effect.DENY, Effect.DENY), REQUEST)

    def test_empty_set_is_not_a_conflict(self) -> None:
        assert not has_conflict(PolicySet(), REQUEST)

    def test_nonmatching_deny_does_not_create_conflict(self) -> None:
        policy_set = PolicySet(
            policies=(
                Policy("alice", "report", "read", Effect.ALLOW, "a"),
                Policy("bob", "report", "read", Effect.DENY, "d"),
            )
        )

        assert not has_conflict(policy_set, REQUEST)

    def test_exact_matching_is_required(self) -> None:
        policy_set = PolicySet(
            policies=(
                Policy("alice", "report", "read", Effect.ALLOW, "a"),
                Policy("alice", "report", "write", Effect.DENY, "d"),
            )
        )

        assert not has_conflict(policy_set, REQUEST)
