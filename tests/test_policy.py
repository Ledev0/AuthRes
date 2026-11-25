"""Tests for strict JSON policy-set parsing and serialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from authres.core.errors import PolicyValidationError
from authres.core.models import Effect, Policy
from authres.core.policy import POLICY_FORMAT_VERSION, PolicySet

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "policies" / "examples"


def test_from_json_parses_minimal_document() -> None:
    policy_set = PolicySet.from_json(
        """
        {
          "version": 1,
          "policies": [
            {
              "subject": "alice",
              "resource": "report",
              "action": "read",
              "effect": "ALLOW"
            }
          ]
        }
        """
    )

    assert policy_set.version == POLICY_FORMAT_VERSION
    assert len(policy_set.policies) == 1
    assert policy_set.policies[0].effect is Effect.ALLOW


def test_empty_policy_collection_is_valid() -> None:
    policy_set = PolicySet.from_json('{"version": 1, "policies": []}')

    assert policy_set.policies == ()


def test_policy_set_json_round_trip() -> None:
    policy_set = PolicySet(
        policies=(
            Policy(
                subject="alice",
                resource="report",
                action="read",
                effect=Effect.ALLOW,
                policy_id="p1",
            ),
            Policy(
                subject="alice",
                resource="report",
                action="read",
                effect=Effect.DENY,
                policy_id="p2",
            ),
        )
    )

    parsed = PolicySet.from_json(policy_set.to_json())

    assert parsed == policy_set


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ("not json", "invalid JSON"),
        ("", "invalid JSON"),
        ("[]", "must be a JSON object"),
        ('{"policies": []}', r"missing required field\(s\): 'version'"),
        ('{"version": 1}', r"missing required field\(s\): 'policies'"),
        (
            '{"version": 1, "policies": [], "extra": true}',
            "unsupported field",
        ),
        ('{"version": 2, "policies": []}', "version must be the integer 1"),
        ('{"version": true, "policies": []}', "version must be the integer 1"),
        ('{"version": "1", "policies": []}', "version must be the integer 1"),
        ('{"version": 1, "policies": {}}', "policies must be a JSON array"),
        ('{"version": 1, "policies": [42]}', "must be a JSON object"),
    ],
)
def test_invalid_policy_documents_are_rejected(
    document: str, match: str
) -> None:
    with pytest.raises(PolicyValidationError, match=match):
        PolicySet.from_json(document)


@pytest.mark.parametrize(
    ("policy_document", "match"),
    [
        (
            '{"version": 1, "policies": ['
            '{"subject": "alice", "resource": "report", "action": "read"}]}',
            "missing required field",
        ),
        (
            '{"version": 1, "policies": ['
            '{"subject": "alice", "resource": "report", "action": "read",'
            ' "effect": "allow"}]}',
            "must be 'ALLOW' or 'DENY'",
        ),
        (
            '{"version": 1, "policies": ['
            '{"subject": "alice", "resource": "report", "action": "read",'
            ' "effect": "ALLOW", "condition": "x"}]}',
            "unsupported field",
        ),
    ],
)
def test_invalid_policies_are_rejected(
    policy_document: str, match: str
) -> None:
    with pytest.raises(PolicyValidationError, match=match):
        PolicySet.from_json(policy_document)


def test_duplicate_policy_ids_are_rejected() -> None:
    document = json.dumps(
        {
            "version": 1,
            "policies": [
                {
                    "id": "same-id",
                    "subject": "alice",
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                },
                {
                    "id": "same-id",
                    "subject": "bob",
                    "resource": "report",
                    "action": "read",
                    "effect": "DENY",
                },
            ],
        }
    )

    with pytest.raises(PolicyValidationError, match="duplicate policy id"):
        PolicySet.from_json(document)


def test_missing_policy_ids_do_not_count_as_duplicates() -> None:
    document = {
        "version": 1,
        "policies": [
            {
                "subject": "alice",
                "resource": "report",
                "action": "read",
                "effect": "ALLOW",
            },
            {
                "subject": "bob",
                "resource": "report",
                "action": "read",
                "effect": "ALLOW",
            },
        ],
    }

    policy_set = PolicySet.from_dict(document)

    assert [policy.policy_id for policy in policy_set.policies] == [None, None]


def test_duplicate_json_object_keys_are_rejected() -> None:
    document = '{"version": 1, "policies": [], "version": 1}'

    with pytest.raises(PolicyValidationError, match="duplicate key"):
        PolicySet.from_json(document)


def test_duplicate_keys_inside_policy_are_rejected() -> None:
    document = (
        '{"version": 1, "policies": [{"subject": "alice", "subject": "bob",'
        ' "resource": "report", "action": "read", "effect": "ALLOW"}]}'
    )

    with pytest.raises(PolicyValidationError, match="duplicate key"):
        PolicySet.from_json(document)


def test_nonstandard_json_constants_are_rejected() -> None:
    document = '{"version": 1, "policies": [], "extra": NaN}'

    with pytest.raises(PolicyValidationError, match="invalid JSON constant"):
        PolicySet.from_json(document)


def test_direct_policy_set_rejects_duplicate_ids() -> None:
    with pytest.raises(PolicyValidationError, match="duplicate policy id"):
        PolicySet(
            policies=(
                Policy(
                    subject="alice",
                    resource="report",
                    action="read",
                    effect=Effect.ALLOW,
                    policy_id="duplicate",
                ),
                Policy(
                    subject="bob",
                    resource="report",
                    action="read",
                    effect=Effect.DENY,
                    policy_id="duplicate",
                ),
            )
        )


def test_direct_policy_set_rejects_invalid_members() -> None:
    with pytest.raises(PolicyValidationError, match=r"policies\[0\]"):
        PolicySet(policies=("not-a-policy",))  # type: ignore[arg-type]


def test_policy_set_requires_integer_version() -> None:
    with pytest.raises(PolicyValidationError, match="version"):
        PolicySet(version=True)


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("basic_allow.json", 2),
        ("conflict.json", 2),
        ("default_deny.json", 0),
    ],
)
def test_example_policy_files_are_valid(
    filename: str, expected_count: int
) -> None:
    policy_set = PolicySet.from_file(EXAMPLES_DIR / filename)

    assert len(policy_set.policies) == expected_count


def test_missing_policy_file_has_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(PolicyValidationError, match="cannot read policy file"):
        PolicySet.from_file(missing)
