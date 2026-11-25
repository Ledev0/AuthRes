"""Corpus runner and disagreement-record tests."""

from __future__ import annotations

import json

from authres.compare.generator import GeneratedCase
from authres.compare.runner import compare_corpus
from authres.core.models import AccessRequest, Decision, Effect, Policy
from authres.core.policy import PolicySet
from authres.engines.contract import EngineOutcome, EngineStatus
from authres.engines.index_engine import IndexEngine


class AlwaysAllowEngine:
    engine_id = "stub-always-allow"
    engine_version = "1"

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        return EngineOutcome(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            status=EngineStatus.DECIDED,
            decision=Decision.ALLOW,
        )


class AlwaysErrorEngine:
    engine_id = "stub-always-error"
    engine_version = "1"

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        raise RuntimeError("intentional test failure")


CONFLICT_CASE = GeneratedCase(
    case_index=0,
    policy_set=PolicySet(
        policies=(
            Policy("alice", "report", "read", Effect.ALLOW, "a"),
            Policy("alice", "report", "read", Effect.DENY, "d"),
        )
    ),
    request=AccessRequest("alice", "report", "read"),
)

ALLOW_ONLY_CASE = GeneratedCase(
    case_index=1,
    policy_set=PolicySet(
        policies=(Policy("bob", "memo", "read", Effect.ALLOW, "a"),)
    ),
    request=AccessRequest("bob", "memo", "read"),
)


class TestComparisonRun:
    def test_disagreements_and_conflicts_are_counted(self) -> None:
        run = compare_corpus(
            [CONFLICT_CASE, ALLOW_ONLY_CASE],
            [IndexEngine(), AlwaysAllowEngine()],
        )

        assert run.total_cases == 2
        assert run.agreements == 1
        assert len(run.disagreements) == 1
        assert len(run.error_cases) == 0
        assert len(run.non_decided_cases) == 0
        assert len(run.conflicting_cases) == 1
        assert run.conflicting_cases[0].case.case_index == 0

    def test_error_cases_are_not_agreements_or_disagreements(self) -> None:
        run = compare_corpus(
            [CONFLICT_CASE],
            [IndexEngine(), AlwaysErrorEngine()],
        )

        assert run.agreements == 0
        assert run.disagreements == ()
        assert len(run.error_cases) == 1
        assert run.error_cases[0].result.agreement is None
        assert run.error_cases[0].result.decisions["stub-always-error"] is None

    def test_disagreement_record_is_json_compatible(self) -> None:
        run = compare_corpus(
            [CONFLICT_CASE],
            [IndexEngine(), AlwaysAllowEngine()],
        )
        record = run.disagreements[0].to_dict()

        assert json.loads(json.dumps(record)) == record
        assert record["case_index"] == 0
        assert record["conflicting"] is True
        assert record["policy_set"]["version"] == 1
        assert record["request"] == {
            "subject": "alice",
            "resource": "report",
            "action": "read",
        }
        assert record["comparison"]["agreement"] is False
        engine_records = {
            entry["engine_id"]: entry
            for entry in record["comparison"]["engines"]
        }
        assert engine_records["authres-index-engine"]["status"] == "DECIDED"
        assert engine_records["authres-index-engine"]["decision"] == "DENY"
        assert engine_records["stub-always-allow"]["decision"] == "ALLOW"

    def test_empty_corpus(self) -> None:
        run = compare_corpus([], [IndexEngine(), AlwaysAllowEngine()])

        assert run.total_cases == 0
        assert run.agreements == 0
        assert run.disagreements == ()
        assert run.conflicting_cases == ()
