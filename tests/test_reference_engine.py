"""Tests for the deterministic reference authorization engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from authres.core.models import (
    AccessRequest,
    Decision,
    DecisionReason,
    Effect,
    Policy,
)
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "policies" / "examples"


def make_policy(
    *,
    subject: str = "alice",
    resource: str = "report",
    action: str = "read",
    effect: Effect = Effect.ALLOW,
    policy_id: str | None = None,
) -> Policy:
    return Policy(
        subject=subject,
        resource=resource,
        action=action,
        effect=effect,
        policy_id=policy_id,
    )


def make_request(
    *,
    subject: str = "alice",
    resource: str = "report",
    action: str = "read",
) -> AccessRequest:
    return AccessRequest(
        subject=subject,
        resource=resource,
        action=action,
    )


def test_matching_allow_policy_allows() -> None:
    policy = make_policy(effect=Effect.ALLOW, policy_id="allow-read")

    result = ReferenceEngine().evaluate(
        PolicySet(policies=(policy,)), make_request()
    )

    assert result.decision is Decision.ALLOW
    assert result.reason is DecisionReason.MATCHED_ALLOW
    assert result.matched_policies == (policy,)
    assert result.matched_policy_ids == ("allow-read",)


def test_matching_deny_policy_denies() -> None:
    policy = make_policy(effect=Effect.DENY, policy_id="deny-read")

    result = ReferenceEngine().evaluate(
        PolicySet(policies=(policy,)), make_request()
    )

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.MATCHED_DENY
    assert result.matched_policies == (policy,)


def test_unmatched_request_defaults_to_deny() -> None:
    policy = make_policy(subject="bob")

    result = ReferenceEngine().evaluate(
        PolicySet(policies=(policy,)), make_request()
    )

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DEFAULT_DENY
    assert result.matched_policies == ()


@pytest.mark.parametrize(
    "effects",
    [
        (Effect.ALLOW, Effect.DENY),
        (Effect.DENY, Effect.ALLOW),
    ],
)
def test_deny_overrides_allow_regardless_of_policy_order(
    effects: tuple[Effect, Effect],
) -> None:
    policies = tuple(
        make_policy(effect=effect, policy_id=f"p{index}")
        for index, effect in enumerate(effects)
    )

    result = ReferenceEngine().evaluate(
        PolicySet(policies=policies), make_request()
    )

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DENY_OVERRIDE
    assert result.matched_policy_ids == ("p0", "p1")


def test_multiple_matching_allow_policies_allow() -> None:
    policies = (
        make_policy(effect=Effect.ALLOW, policy_id="a1"),
        make_policy(effect=Effect.ALLOW, policy_id="a2"),
        make_policy(subject="bob", effect=Effect.DENY, policy_id="unmatched"),
    )

    result = ReferenceEngine().evaluate(
        PolicySet(policies=policies), make_request()
    )

    assert result.decision is Decision.ALLOW
    assert result.reason is DecisionReason.MATCHED_ALLOW
    assert result.matched_policy_ids == ("a1", "a2")


def test_multiple_matching_deny_policies_deny() -> None:
    policies = (
        make_policy(effect=Effect.DENY, policy_id="d1"),
        make_policy(effect=Effect.DENY, policy_id="d2"),
        make_policy(effect=Effect.ALLOW, policy_id="unmatched", action="write"),
    )

    result = ReferenceEngine().evaluate(
        PolicySet(policies=policies), make_request()
    )

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.MATCHED_DENY
    assert result.matched_policy_ids == ("d1", "d2")


def test_multiple_matching_mixed_policies_deny_and_trace_all_matches() -> None:
    policies = (
        make_policy(effect=Effect.ALLOW, policy_id="a1"),
        make_policy(effect=Effect.DENY, policy_id="d1"),
        make_policy(effect=Effect.ALLOW, policy_id="a2"),
        make_policy(effect=Effect.DENY, policy_id="d2"),
    )

    result = ReferenceEngine().evaluate(
        PolicySet(policies=policies), make_request()
    )

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DENY_OVERRIDE
    assert result.matched_policy_ids == ("a1", "d1", "a2", "d2")


def test_empty_policy_collection_defaults_to_deny() -> None:
    result = ReferenceEngine().evaluate(PolicySet(), make_request())

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DEFAULT_DENY
    assert result.matched_policies == ()


@pytest.mark.parametrize(
    ("subject", "resource", "action"),
    [
        ("Alice", "report", "read"),
        ("alice ", "report", "read"),
        ("alice", "Report", "read"),
        ("alice", "report", "READ"),
        ("alice", "report", "delete"),
        ("*", "report", "read"),
    ],
)
def test_matching_is_exact_and_case_sensitive(
    subject: str, resource: str, action: str
) -> None:
    policy = make_policy(
        subject="alice", resource="report", action="read", effect=Effect.ALLOW
    )
    request = AccessRequest(subject=subject, resource=resource, action=action)

    result = ReferenceEngine().evaluate(
        PolicySet(policies=(policy,)), request
    )

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DEFAULT_DENY


def test_policy_order_does_not_change_single_effect_decision() -> None:
    allow_a = make_policy(effect=Effect.ALLOW, policy_id="a")
    allow_b = make_policy(effect=Effect.ALLOW, policy_id="b")
    engine = ReferenceEngine()

    forward = engine.evaluate(PolicySet(policies=(allow_a, allow_b)), make_request())
    reverse = engine.evaluate(PolicySet(policies=(allow_b, allow_a)), make_request())

    assert forward.decision is reverse.decision is Decision.ALLOW
    assert forward.reason is reverse.reason is DecisionReason.MATCHED_ALLOW


def test_evaluation_is_repeatable_and_does_not_mutate_inputs() -> None:
    policy = make_policy(effect=Effect.ALLOW, policy_id="p1")
    policy_set = PolicySet(policies=(policy,))
    request = make_request()
    engine = ReferenceEngine()

    first = engine.evaluate(policy_set, request)
    second = engine.evaluate(policy_set, request)

    assert first == second
    assert policy_set.policies == (policy,)
    assert request == make_request()


def test_engine_requires_validated_model_objects() -> None:
    engine = ReferenceEngine()
    request = make_request()

    with pytest.raises(TypeError, match="PolicySet"):
        engine.evaluate([], request)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="AccessRequest"):
        engine.evaluate(PolicySet(), request.to_dict())  # type: ignore[arg-type]


def test_example_basic_allow_policy_set() -> None:
    policy_set = PolicySet.from_file(EXAMPLES_DIR / "basic_allow.json")
    engine = ReferenceEngine()

    allowed = engine.evaluate(policy_set, make_request())
    denied = engine.evaluate(
        policy_set, make_request(action="write")
    )

    assert allowed.decision is Decision.ALLOW
    assert denied.decision is Decision.DENY
    assert denied.reason is DecisionReason.DEFAULT_DENY


def test_example_conflict_policy_set() -> None:
    policy_set = PolicySet.from_file(EXAMPLES_DIR / "conflict.json")

    result = ReferenceEngine().evaluate(policy_set, make_request())

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DENY_OVERRIDE
    assert result.matched_policy_ids == (
        "allow-alice-read-report",
        "deny-alice-read-report",
    )


def test_example_default_deny_policy_set() -> None:
    policy_set = PolicySet.from_file(EXAMPLES_DIR / "default_deny.json")

    result = ReferenceEngine().evaluate(policy_set, make_request())

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DEFAULT_DENY
