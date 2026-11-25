"""Metamorphic and property tests for the documented v1 semantics.

Every property below follows from a documented rule in
``docs/policy-semantics.md`` (rule references inline). No new assumptions
are introduced: expectations are computed by a local transcription of the
documented decision formula, never by calling the reference engine as the
source of truth.

Hypothesis settings are fixed to a deterministic-ish profile; failures
print a reproduction seed. The reference engine itself is deterministic,
so any counterexample is meaningful.
"""

from __future__ import annotations

import json
import random

import pytest
from hypothesis import given, settings, strategies as st

from authres.core.errors import PolicyValidationError
from authres.core.models import (
    AccessRequest,
    Decision,
    DecisionReason,
    Effect,
    Policy,
)
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine

REQUEST = AccessRequest("alice", "report", "read")

settings.register_profile(
    "authres", max_examples=75, deadline=None, print_blob=True
)
settings.load_profile("authres")


def documented_decision(effects: list[Effect]) -> tuple[Decision, DecisionReason]:
    """Transcription of docs/policy-semantics.md section 8 (evaluete pseudo-code).

    Independent of ``authres.core.reference_engine``: any bug shared between
    the two must be a misreading of the document, visible as a test failure.
    """
    if not effects:
        return Decision.DENY, DecisionReason.DEFAULT_DENY
    has_allow = Effect.ALLOW in effects
    has_deny = Effect.DENY in effects
    if has_deny and has_allow:
        return Decision.DENY, DecisionReason.DENY_OVERRIDE
    if has_deny:
        return Decision.DENY, DecisionReason.MATCHED_DENY
    return Decision.ALLOW, DecisionReason.MATCHED_ALLOW


# --- strategies -----------------------------------------------------------

effects = st.lists(st.sampled_from([Effect.ALLOW, Effect.DENY]), max_size=8)
nonmatching_policies = st.lists(
    st.tuples(
        st.sampled_from(["bob", "carol", "dave"]),
        st.sampled_from(["memo", "calendar"]),
        st.sampled_from(["write", "delete"]),
        st.sampled_from([Effect.ALLOW, Effect.DENY]),
    ),
    max_size=3,
).map(
    lambda tuples: [
        Policy(subject=s, resource=r, action=a, effect=e, policy_id=f"nm-{i}")
        for i, (s, r, a, e) in enumerate(tuples)
    ]
)


def matching_policies(effect_list: list[Effect], with_ids: bool = True) -> list[Policy]:
    return [
        Policy(
            subject="alice",
            resource="report",
            action="read",
            effect=effect,
            policy_id=f"p{index}" if with_ids else None,
        )
        for index, effect in enumerate(effect_list)
    ]


def evaluate(policies: list[Policy]) -> "object":
    return ReferenceEngine().evaluate(
        PolicySet(policies=tuple(policies)), REQUEST
    )


# --- documented decision formula (semantics doc section 8) ----------------


@given(effects)
def test_engine_matches_documented_decision_formula(effect_list) -> None:
    result = evaluate(matching_policies(effect_list))
    want_decision, want_reason = documented_decision(effect_list)

    assert result.decision is want_decision
    assert result.reason is want_reason
    assert result.matched_policy_ids == tuple(
        f"p{i}" for i in range(len(effect_list))
    )


# --- P1: policy order independence (semantics doc assumption 6, section 4) --


@given(effects, st.data())
def test_policy_order_does_not_change_decision(effect_list, data) -> None:
    policies = matching_policies(effect_list)
    shuffled = list(policies)
    rng = random.Random(data.draw(st.integers(0, 2**32 - 1)))
    rng.shuffle(shuffled)

    baseline = evaluate(policies)
    reordered = evaluate(shuffled)

    assert reordered.decision is baseline.decision
    assert reordered.reason is baseline.reason
    # The trace preserves policy-set order (documented), so the reordered
    # run must contain exactly the same matched ids, in the new order.
    assert sorted(
        pid for pid in reordered.matched_policy_ids if pid is not None
    ) == sorted(
        pid for pid in baseline.matched_policy_ids if pid is not None
    )
    assert len(reordered.matched_policy_ids) == len(policies)


@given(effects)
def test_policy_trace_follows_policy_set_order(effect_list) -> None:
    policies = matching_policies(effect_list)
    reversed_policies = list(reversed(policies))

    forward = evaluate(policies)
    backward = evaluate(reversed_policies)

    assert forward.matched_policy_ids == tuple(p.policy_id for p in policies)
    assert backward.matched_policy_ids == tuple(p.policy_id for p in reversed_policies)
    assert forward.decision is backward.decision
    assert forward.reason is backward.reason


# --- P2: non-matching policies are decision-neutral (section 4 matching rule) --


@given(effects, nonmatching_policies)
def test_adding_nonmatching_policies_changes_nothing(effect_list, extras) -> None:
    baseline = evaluate(matching_policies(effect_list))
    extended = evaluate(matching_policies(effect_list) + extras)

    assert extended.decision is baseline.decision
    assert extended.reason is baseline.reason
    assert extended.matched_policy_ids == baseline.matched_policy_ids
    assert len(extended.matched_policies) == len(baseline.matched_policies)


# --- P3: duplicate policy ids are rejected (section 2 validation rules) -----


@given(effects, nonmatching_policies)
def test_duplicate_policy_ids_remain_rejected(effect_list, extras) -> None:
    from dataclasses import replace

    policies = matching_policies(effect_list) + extras
    if len(policies) < 2:
        policies = matching_policies(["ALLOW", "DENY"])

    forced_id = "forced-duplicate-id"
    policies[0] = replace(policies[0], policy_id=forced_id)
    policies[1] = replace(policies[1], policy_id=forced_id)

    with pytest.raises(PolicyValidationError, match="duplicate policy id"):
        PolicySet(policies=tuple(policies))


# --- P4: JSON formatting equivalence (strict JSON semantics) ---------------


identifier_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",)  # exclude lone surrogates from JSON text
    ),
    min_size=1,
    max_size=12,
).filter(lambda text: text.strip())


@given(
    subject=identifier_text,
    resource=identifier_text,
    action=identifier_text,
    effect=st.sampled_from(["ALLOW", "DENY"]),
    with_id=st.booleans(),
    indent=st.sampled_from([None, 2, 4]),
    reverse_keys=st.booleans(),
)
def test_equivalent_json_formatting_yields_identical_semantics(
    subject, resource, action, effect, with_id, indent, reverse_keys
) -> None:
    policy = {
        "subject": subject,
        "resource": resource,
        "action": action,
        "effect": effect,
    }
    if with_id:
        policy["id"] = f"id-for-{action}"
    document = {"version": 1, "policies": [policy]}
    if reverse_keys:
        document = {"policies": document["policies"], "version": document["version"]}

    compact = json.dumps(document, separators=(",", ":"))
    pretty = json.dumps(document, indent=indent)
    from authres.core.policy import PolicySet

    from_compact = PolicySet.from_json(compact)
    from_pretty = PolicySet.from_json(pretty)

    assert from_compact == from_pretty
    assert from_compact.to_dict() == document


@given(effects, st.booleans())
def test_semantics_survive_reserialization(effect_list, reverse) -> None:
    policies = matching_policies(effect_list)
    document = {
        "version": 1,
        "policies": [policy.to_dict() for policy in policies],
    }
    if reverse:
        document["policies"] = list(reversed(document["policies"]))
        policies = list(reversed(policies))

    from authres.core.policy import PolicySet

    parsed = PolicySet.from_json(json.dumps(document))
    reparsed = PolicySet.from_json(parsed.to_json())

    assert reparsed == parsed
    assert reparsed.to_dict() == parsed.to_dict()

    result_first = ReferenceEngine().evaluate(parsed, REQUEST)
    result_second = ReferenceEngine().evaluate(reparsed, REQUEST)
    assert result_first.to_dict() == result_second.to_dict()


# --- P5: empty policy sets always deny (section 4) --------------------------


@given(identifier_text, identifier_text, identifier_text)
def test_empty_policy_set_denies_every_valid_request(subject, resource, action) -> None:
    request = AccessRequest(subject, resource, action)
    result = ReferenceEngine().evaluate(PolicySet(), request)

    assert result.decision is Decision.DENY
    assert result.reason is DecisionReason.DEFAULT_DENY
    assert result.matched_policies == ()
