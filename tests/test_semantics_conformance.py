"""Hand-authored conformance cases for the documented version 1 semantics.

The expectations in ``fixtures/semantics_v1.json`` are written from
``docs/policy-semantics.md``. They are not calculated by the reference engine.
This suite reduces implementation coupling; it is not an independently
validated oracle. See ``docs/semantic-validation.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from authres.core.models import AccessRequest
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "semantics_v1.json"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _cases() -> list[dict[str, object]]:
    data = _load_fixture()
    cases = data["cases"]
    assert isinstance(cases, list)
    return cases


CASES = _cases()


def test_conformance_fixture_metadata() -> None:
    data = _load_fixture()

    assert data["fixture_version"] == 1
    assert data["semantics_version"] == "authres-policy-v1"


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[str(case["name"]) for case in CASES],
)
def test_documented_semantics_conformance(case: dict[str, object]) -> None:
    policy_document = case["policy_document"]
    request_data = case["request"]
    expected = case["expected"]
    assert isinstance(policy_document, dict)
    assert isinstance(request_data, dict)
    assert isinstance(expected, dict)

    policy_set = PolicySet.from_json(
        json.dumps(policy_document, ensure_ascii=False)
    )
    request = AccessRequest.from_dict(request_data)
    result = ReferenceEngine().evaluate(policy_set, request)

    assert result.decision.value == expected["decision"]
    assert result.reason.value == expected["reason"]
    assert list(result.matched_policy_ids) == expected["matched_policy_ids"]
