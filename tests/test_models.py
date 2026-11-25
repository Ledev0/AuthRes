"""Tests for policy and request data models and their validation."""

from __future__ import annotations

import pytest

from authres.core.errors import PolicyValidationError, RequestValidationError
from authres.core.models import (
    AccessRequest,
    Decision,
    DecisionReason,
    Effect,
    EvaluationResult,
    Policy,
)


def make_policy(**overrides: object) -> Policy:
    values: dict[str, object] = {
        "subject": "alice",
        "resource": "report",
        "action": "read",
        "effect": Effect.ALLOW,
    }
    values.update(overrides)
    return Policy(**values)  # type: ignore[arg-type]


def test_policy_accepts_valid_fields() -> None:
    policy = make_policy(policy_id="allow-alice-read-report")

    assert policy.subject == "alice"
    assert policy.resource == "report"
    assert policy.action == "read"
    assert policy.effect is Effect.ALLOW
    assert policy.policy_id == "allow-alice-read-report"


def test_policy_accepts_uppercase_effect_string_for_direct_construction() -> None:
    policy = make_policy(effect="DENY")

    assert policy.effect is Effect.DENY


@pytest.mark.parametrize("effect", ["allow", "Deny", "permit", "", 1, None])
def test_policy_rejects_invalid_effect(effect: object) -> None:
    with pytest.raises(PolicyValidationError, match="effect"):
        make_policy(effect=effect)


@pytest.mark.parametrize("field", ["subject", "resource", "action"])
@pytest.mark.parametrize("value", ["", "   ", None, 42, True])
def test_policy_rejects_invalid_identifiers(field: str, value: object) -> None:
    with pytest.raises(PolicyValidationError, match=field):
        make_policy(**{field: value})


@pytest.mark.parametrize("value", ["", "  ", 42])
def test_policy_rejects_invalid_policy_id(value: object) -> None:
    with pytest.raises(PolicyValidationError, match="policy_id"):
        make_policy(policy_id=value)


def test_policy_with_none_id_has_no_policy_id() -> None:
    policy = make_policy(policy_id=None)

    assert policy.policy_id is None


def test_policy_preserves_identifier_text_without_normalization() -> None:
    policy = make_policy(subject=" Alice ", action="READ")

    assert policy.subject == " Alice "
    assert policy.action == "READ"


def test_policy_from_dict_without_id() -> None:
    policy = Policy.from_dict(
        {
            "subject": "alice",
            "resource": "report",
            "action": "read",
            "effect": "ALLOW",
        }
    )

    assert policy == make_policy()


def test_policy_from_dict_with_id() -> None:
    policy = Policy.from_dict(
        {
            "id": "p1",
            "subject": "alice",
            "resource": "report",
            "action": "read",
            "effect": "ALLOW",
        }
    )

    assert policy.policy_id == "p1"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"subject": "alice", "resource": "report", "action": "read"},
        {
            "subject": "alice",
            "resource": "report",
            "action": "read",
            "effect": "ALLOW",
            "condition": "time < 12:00",
        },
        {
            "id": None,
            "subject": "alice",
            "resource": "report",
            "action": "read",
            "effect": "ALLOW",
        },
    ],
)
def test_policy_from_dict_rejects_invalid_data(data: dict[str, object]) -> None:
    with pytest.raises(PolicyValidationError):
        Policy.from_dict(data)


def test_policy_from_dict_rejects_non_object() -> None:
    with pytest.raises(PolicyValidationError, match="must be a JSON object"):
        Policy.from_dict([])  # type: ignore[arg-type]


def test_policy_dict_round_trip() -> None:
    policy = make_policy(effect=Effect.DENY, policy_id="deny-alice-read-report")

    assert Policy.from_dict(policy.to_dict()) == policy


def test_access_request_accepts_valid_fields() -> None:
    request = AccessRequest(subject="alice", resource="report", action="read")

    assert request.to_dict() == {
        "subject": "alice",
        "resource": "report",
        "action": "read",
    }


@pytest.mark.parametrize("missing", ["subject", "resource", "action"])
def test_access_request_from_dict_reports_missing_attributes(missing: str) -> None:
    data = {"subject": "alice", "resource": "report", "action": "read"}
    del data[missing]

    with pytest.raises(RequestValidationError, match="missing required attribute"):
        AccessRequest.from_dict(data)


def test_access_request_from_dict_reports_all_missing_attributes() -> None:
    with pytest.raises(
        RequestValidationError,
        match=r"missing required attribute\(s\): 'action', 'resource', 'subject'",
    ):
        AccessRequest.from_dict({})


def test_access_request_from_dict_rejects_unknown_attribute() -> None:
    with pytest.raises(RequestValidationError, match="unsupported attribute"):
        AccessRequest.from_dict(
            {
                "subject": "alice",
                "resource": "report",
                "action": "read",
                "tenant": "example",
            }
        )


def test_access_request_from_dict_rejects_non_object() -> None:
    with pytest.raises(RequestValidationError, match="must be a JSON object"):
        AccessRequest.from_dict(["alice"])  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["subject", "resource", "action"])
@pytest.mark.parametrize("value", ["", "  ", 7, None])
def test_access_request_rejects_invalid_identifiers(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "subject": "alice",
        "resource": "report",
        "action": "read",
    }
    values[field] = value

    with pytest.raises(RequestValidationError, match=field):
        AccessRequest(**values)  # type: ignore[arg-type]


def test_access_request_dict_round_trip() -> None:
    request = AccessRequest(subject="alice", resource="report", action="read")

    assert AccessRequest.from_dict(request.to_dict()) == request


def test_access_request_from_json_parses_strict_document() -> None:
    request = AccessRequest.from_json(
        '{"subject":"alice","resource":"report","action":"read"}'
    )

    assert request == AccessRequest("alice", "report", "read")


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ("not json", "invalid JSON"),
        (
            '{"subject":"alice","subject":"bob","resource":"report","action":"read"}',
            "duplicate key",
        ),
        (
            '{"subject":NaN,"resource":"report","action":"read"}',
            "invalid JSON constant",
        ),
        ("[]", "must be a JSON object"),
        (
            '{"subject":"alice","resource":"report"}',
            "missing required attribute",
        ),
    ],
)
def test_access_request_from_json_rejects_invalid_documents(
    document: str, match: str
) -> None:
    with pytest.raises(RequestValidationError, match=match):
        AccessRequest.from_json(document)


def test_access_request_from_json_reports_non_string_input() -> None:
    with pytest.raises(RequestValidationError, match="must be a JSON string"):
        AccessRequest.from_json(b'{"subject":"alice"}')  # type: ignore[arg-type]


def test_evaluation_result_exposes_policy_ids_and_trace() -> None:
    policy = make_policy(policy_id="p1")
    result = EvaluationResult(
        decision=Decision.ALLOW,
        reason=DecisionReason.MATCHED_ALLOW,
        matched_policies=(policy,),
    )

    assert result.matched_policy_ids == ("p1",)
    assert result.to_dict() == {
        "decision": "ALLOW",
        "reason": "MATCHED_ALLOW",
        "matched_policy_ids": ["p1"],
        "matched_policies": [policy.to_dict()],
    }


def test_evaluation_result_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="decision"):
        EvaluationResult(
            decision="ALLOW",  # type: ignore[arg-type]
            reason=DecisionReason.MATCHED_ALLOW,
        )

    with pytest.raises(TypeError, match="matched_policies"):
        EvaluationResult(
            decision=Decision.ALLOW,
            reason=DecisionReason.MATCHED_ALLOW,
            matched_policies=("not-a-policy",),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("decision", "reason", "effects", "message"),
    [
        (
            Decision.ALLOW,
            DecisionReason.DEFAULT_DENY,
            (),
            "DEFAULT_DENY",
        ),
        (
            Decision.DENY,
            DecisionReason.DEFAULT_DENY,
            (Effect.ALLOW,),
            "DEFAULT_DENY",
        ),
        (
            Decision.DENY,
            DecisionReason.MATCHED_ALLOW,
            (),
            "MATCHED_ALLOW",
        ),
        (
            Decision.DENY,
            DecisionReason.MATCHED_ALLOW,
            (Effect.ALLOW,),
            "MATCHED_ALLOW",
        ),
        (
            Decision.ALLOW,
            DecisionReason.MATCHED_DENY,
            (Effect.DENY,),
            "MATCHED_DENY",
        ),
        (
            Decision.ALLOW,
            DecisionReason.DENY_OVERRIDE,
            (Effect.ALLOW, Effect.DENY),
            "DENY_OVERRIDE",
        ),
        (
            Decision.DENY,
            DecisionReason.DENY_OVERRIDE,
            (Effect.ALLOW,),
            "DENY_OVERRIDE",
        ),
    ],
)
def test_evaluation_result_rejects_inconsistent_semantic_state(
    decision: Decision,
    reason: DecisionReason,
    effects: tuple[Effect, ...],
    message: str,
) -> None:
    policies = tuple(
        make_policy(effect=effect, policy_id=f"p{index}")
        for index, effect in enumerate(effects)
    )

    with pytest.raises(ValueError, match=message):
        EvaluationResult(
            decision=decision,
            reason=reason,
            matched_policies=policies,
        )


@pytest.mark.parametrize(
    ("decision", "reason", "effects"),
    [
        (Decision.DENY, DecisionReason.DEFAULT_DENY, ()),
        (Decision.ALLOW, DecisionReason.MATCHED_ALLOW, (Effect.ALLOW,)),
        (Decision.DENY, DecisionReason.MATCHED_DENY, (Effect.DENY,)),
        (
            Decision.DENY,
            DecisionReason.DENY_OVERRIDE,
            (Effect.ALLOW, Effect.DENY),
        ),
    ],
)
def test_evaluation_result_accepts_consistent_semantic_state(
    decision: Decision,
    reason: DecisionReason,
    effects: tuple[Effect, ...],
) -> None:
    policies = tuple(
        make_policy(effect=effect, policy_id=f"p{index}")
        for index, effect in enumerate(effects)
    )

    result = EvaluationResult(
        decision=decision,
        reason=reason,
        matched_policies=policies,
    )

    assert result.decision is decision
    assert result.reason is reason
    assert result.matched_policies == policies
