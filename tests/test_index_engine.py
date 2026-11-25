"""Engine B tests: fixture conformance and metamorphic properties.

Engine B is ``authres.engines.index_engine.IndexEngine``. Expectations come
from the hand-authored fixture or from a local transcription of
``docs/policy-semantics.md`` section 8, never from the reference engine.
"""

from __future__ import annotations

import json
import random
from itertools import permutations
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from authres.core.models import AccessRequest, Decision, Effect, Policy
from authres.core.policy import PolicySet
from authres.engines.contract import EngineStatus
from authres.engines.index_engine import IndexEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "semantics_v1.json"

with FIXTURE_PATH.open(encoding="utf-8") as handle:
    FIXTURE = json.load(handle)

CASES = FIXTURE["cases"]

EFFECT_LISTS = st.lists(
    st.sampled_from([Effect.ALLOW, Effect.DENY]), max_size=8
)


def documented_decision(effects: list[Effect]) -> Decision:
    """Transcription of docs/policy-semantics.md sections 6 and 8."""
    if not effects:
        return Decision.DENY
    if Effect.DENY in effects:
        return Decision.DENY
    return Decision.ALLOW


def matching_policies(effects: list[Effect]) -> list[Policy]:
    return [
        Policy(
            subject="alice",
            resource="report",
            action="read",
            effect=effect,
            policy_id=f"p{index}",
        )
        for index, effect in enumerate(effects)
    ]


class TestFixtureConformance:
    @pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
    def test_fixture_decisions(self, case: dict) -> None:
        policy_set = PolicySet.from_dict(case["policy_document"])
        request = AccessRequest.from_dict(case["request"])

        engine = IndexEngine()
        outcome = engine.evaluate(policy_set, request)

        assert outcome.status is EngineStatus.DECIDED
        assert outcome.has_decision is True
        assert outcome.decision.value == case["expected"]["decision"]

    @pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
    def test_compile_once_execute_many(self, case: dict) -> None:
        policy_set = PolicySet.from_dict(case["policy_document"])
        request = AccessRequest.from_dict(case["request"])
        engine = IndexEngine()

        compiled = engine.compile(policy_set)
        raw = engine.execute(compiled, request)
        outcome = engine.normalize(raw)

        assert isinstance(raw.effects, frozenset)
        assert outcome.decision.value == case["expected"]["decision"]


class TestDocumentedFormula:
    @given(EFFECT_LISTS)
    def test_matches_documented_formula(self, effects: list[Effect]) -> None:
        policy_set = PolicySet(policies=tuple(matching_policies(effects)))
        request = AccessRequest("alice", "report", "read")

        outcome = IndexEngine().evaluate(policy_set, request)

        assert outcome.decision is documented_decision(effects)

    @given(EFFECT_LISTS, st.integers(0, 2**32 - 1))
    def test_policy_order_does_not_change_decision(
        self, effects: list[Effect], shuffle_seed: int
    ) -> None:
        policies = matching_policies(effects)
        shuffled = list(policies)
        random.Random(shuffle_seed).shuffle(shuffled)
        request = AccessRequest("alice", "report", "read")
        engine = IndexEngine()

        forward = engine.evaluate(
            PolicySet(policies=tuple(policies)), request
        )
        reordered = engine.evaluate(
            PolicySet(policies=tuple(shuffled)), request
        )

        assert forward.decision is reordered.decision

    def test_all_permutations_of_small_conflict_agree(self) -> None:
        policies = [
            Policy("alice", "report", "read", Effect.ALLOW, "a"),
            Policy("alice", "report", "read", Effect.DENY, "d"),
            Policy("bob", "report", "read", Effect.ALLOW, "other"),
        ]
        request = AccessRequest("alice", "report", "read")
        engine = IndexEngine()

        decisions = {
            engine.evaluate(
                PolicySet(policies=tuple(order)), request
            ).decision
            for order in permutations(policies)
        }

        assert decisions == {Decision.DENY}

    @given(EFFECT_LISTS)
    def test_nonmatching_policies_do_not_change_decision(
        self, effects: list[Effect]
    ) -> None:
        matching = matching_policies(effects)
        extras = [
            Policy("bob", "memo", "write", Effect.DENY, "x1"),
            Policy("carol", "calendar", "delete", Effect.ALLOW, "x2"),
        ]
        request = AccessRequest("alice", "report", "read")
        engine = IndexEngine()

        baseline = engine.evaluate(
            PolicySet(policies=tuple(matching)), request
        )
        extended = engine.evaluate(
            PolicySet(policies=tuple(matching + extras)), request
        )

        assert extended.decision is baseline.decision


class TestDefaultsAndLookup:
    def test_empty_policy_set_defaults_to_deny(self) -> None:
        outcome = IndexEngine().evaluate(
            PolicySet(), AccessRequest("alice", "report", "read")
        )

        assert outcome.decision is Decision.DENY
        assert outcome.status is EngineStatus.DECIDED

    def test_unmatched_request_defaults_to_deny(self) -> None:
        policy = Policy("alice", "report", "read", Effect.ALLOW)
        outcome = IndexEngine().evaluate(
            PolicySet(policies=(policy,)),
            AccessRequest("bob", "report", "read"),
        )

        assert outcome.decision is Decision.DENY

    def test_identifier_equality_is_exact(self) -> None:
        policy = Policy("Alice", "report", "read", Effect.ALLOW)
        request = AccessRequest("alice", "report", "read")

        outcome = IndexEngine().evaluate(
            PolicySet(policies=(policy,)), request
        )

        assert outcome.decision is Decision.DENY

    def test_duplicate_effect_rules_are_not_deduplicated_in_index(self) -> None:
        policies = (
            Policy("alice", "report", "read", Effect.ALLOW, "a1"),
            Policy("alice", "report", "read", Effect.ALLOW, "a2"),
        )
        compiled = IndexEngine().compile(PolicySet(policies=policies))

        assert compiled.rule_count == 2
        assert compiled.index[("alice", "report", "read")] == frozenset(
            {Effect.ALLOW}
        )

    def test_engine_identity(self) -> None:
        engine = IndexEngine()

        assert engine.engine_id == "authres-index-engine"
        assert engine.engine_version
        assert engine.engine_id.strip()
        assert engine.engine_version.strip()


class TestNoReferenceImport:
    def test_index_engine_has_no_reference_engine_import(self) -> None:
        import ast

        path = PROJECT_ROOT / "authres" / "engines" / "index_engine.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        assert not any(
            module.startswith("authres.core.reference_engine")
            for module in imported
        )
