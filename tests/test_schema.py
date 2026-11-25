"""Schema/parser agreement tests for the policy and request JSON Schemas.

The Python parser stays normative; these tests pin the documented agreement
between the schemas (schemas/*.schema.json) and the parser behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
EXAMPLES_DIR = PROJECT_ROOT / "policies" / "examples"

REQUEST = {"subject": "alice", "resource": "report", "action": "read"}


@pytest.fixture(scope="module")
def policy_schema() -> dict:
    schema = json.loads(
        (SCHEMAS_DIR / "policy-v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return schema


@pytest.fixture(scope="module")
def request_schema() -> dict:
    schema = json.loads(
        (SCHEMAS_DIR / "request-v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return schema


def _validate(schema: dict, instance: object) -> None:
    Draft202012Validator(schema).validate(instance)


class TestSchemaFiles:
    def test_policy_schema_is_valid_draft_2020_12(self, policy_schema) -> None:
        assert policy_schema["title"].startswith("AuthRes policy document")

    def test_request_schema_is_valid_draft_2020_12(self, request_schema) -> None:
        assert request_schema["title"].startswith("AuthRes access request")


class TestParserAcceptedInstancesValidate:
    @pytest.mark.parametrize(
        "path",
        sorted(EXAMPLES_DIR.glob("*.json")),
        ids=lambda path: path.name,
    )
    def test_example_policy_files_validate(self, path, policy_schema) -> None:
        document = json.loads(path.read_text(encoding="utf-8"))

        _validate(policy_schema, document)

    def test_minimal_valid_policy_document(self, policy_schema) -> None:
        _validate(
            policy_schema,
            {
                "version": 1,
                "policies": [
                    {
                        "subject": "alice",
                        "resource": "report",
                        "action": "read",
                        "effect": "ALLOW",
                    }
                ],
            },
        )

    def test_policy_with_optional_id_and_empty_set(self, policy_schema) -> None:
        _validate(
            policy_schema,
            {
                "version": 1,
                "policies": [
                    {
                        "id": "p1",
                        "subject": "alice",
                        "resource": "report",
                        "action": "read",
                        "effect": "DENY",
                    }
                ],
            },
        )
        _validate(policy_schema, {"version": 1, "policies": []})

    def test_valid_request(self, request_schema) -> None:
        _validate(request_schema, REQUEST)

    def test_whitespace_inside_identifiers_validates(self, request_schema) -> None:
        _validate(
            request_schema,
            {"subject": " alice ", "resource": "report", "action": "read"},
        )

    def test_nul_inside_identifier_validates(self, request_schema) -> None:
        _validate(
            request_schema,
            {"subject": "a\u0000b", "resource": "report", "action": "read"},
        )


REJECTED_POLICIES = [
    pytest.param({"policies": []}, "missing version", id="missing-version"),
    pytest.param({"version": 1}, "missing policies", id="missing-policies"),
    pytest.param({"version": "1", "policies": []}, "version as string", id="version-string"),
    pytest.param({"version": 2, "policies": []}, "wrong version", id="wrong-version"),
    pytest.param(
        {"version": 1, "policies": [], "extra": True},
        "unknown top-level field",
        id="unknown-top-level",
    ),
    pytest.param({"version": 1, "policies": {}}, "policies not an array", id="policies-not-array"),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "subject": "alice",
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                    "condition": "x",
                }
            ],
        },
        "unknown policy field",
        id="unknown-policy-field",
    ),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "subject": "alice",
                    "resource": "report",
                    "effect": "ALLOW",
                }
            ],
        },
        "missing action",
        id="missing-action",
    ),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "subject": "alice",
                    "resource": "report",
                    "action": "read",
                    "effect": "allow",
                }
            ],
        },
        "lowercase effect",
        id="lowercase-effect",
    ),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "subject": "",
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                }
            ],
        },
        "empty identifier",
        id="empty-identifier",
    ),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "subject": "   ",
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                }
            ],
        },
        "whitespace-only identifier",
        id="whitespace-only-identifier",
    ),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "id": 7,
                    "subject": "alice",
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                }
            ],
        },
        "non-string id",
        id="non-string-id",
    ),
    pytest.param(
        {
            "version": 1,
            "policies": [
                {
                    "subject": 7,
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                }
            ],
        },
        "non-string subject",
        id="non-string-subject",
    ),
]


@pytest.mark.parametrize(("instance", "reason"), REJECTED_POLICIES)
def test_parser_rejected_policies_fail_schema(instance, reason, policy_schema) -> None:
    with pytest.raises(Exception):
        _validate(policy_schema, instance)

    # The parser must reject these too: schema and parser agree.
    with pytest.raises(Exception):
        from authres.core.policy import PolicySet

        PolicySet.from_json(json.dumps(instance))


REJECTED_REQUESTS = [
    pytest.param({}, "empty request", id="empty-request"),
    pytest.param({"subject": "alice", "resource": "report"}, "missing action", id="missing-action"),
    pytest.param(
        {"subject": "alice", "resource": "report", "action": "read", "id": "x"},
        "unknown field",
        id="unknown-field",
    ),
    pytest.param({"subject": "", "resource": "report", "action": "read"}, "empty subject", id="empty-subject"),
    pytest.param(
        {"subject": "   ", "resource": "report", "action": "read"},
        "whitespace-only subject",
        id="whitespace-only-subject",
    ),
    pytest.param({"subject": None, "resource": "report", "action": "read"}, "null subject", id="null-subject"),
    pytest.param([], "not an object", id="not-an-object"),
]


@pytest.mark.parametrize(("instance", "reason"), REJECTED_REQUESTS)
def test_parser_rejected_requests_fail_schema(
    instance, reason, request_schema
) -> None:
    with pytest.raises(Exception):
        _validate(request_schema, instance)

    from authres.core.models import AccessRequest

    with pytest.raises(Exception):
        AccessRequest.from_dict(instance)


class TestSchemaParserAgreement:
    def test_schema_adds_no_undocumented_acceptance(self, policy_schema, request_schema) -> None:
        """Any document the schema accepts must also parse (spot corpus)."""
        accepted_policy = {
            "version": 1,
            "policies": [
                {
                    "id": "weird \u0000 id",
                    "subject": "nfc caf\u00e9",
                    "resource": "repo/rt 1",
                    "action": "READ",
                    "effect": "ALLOW",
                }
            ],
        }
        _validate(policy_schema, accepted_policy)
        from authres.core.policy import PolicySet

        PolicySet.from_json(json.dumps(accepted_policy))

        accepted_request = {
            "subject": "a\u0000b",
            "resource": "\u00e9",
            "action": "-",
        }
        _validate(request_schema, accepted_request)
        from authres.core.models import AccessRequest

        AccessRequest.from_dict(accepted_request)
