"""Comparator tests, including deliberately wrong engines defined in tests.

No mutant is imported by production code. The known-fault engine lives under
``tests/mutants/`` and is used only to demonstrate fault detection.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

from authres.compare.comparator import ComparisonResult, run_comparison
from authres.compare.reference_adapter import ReferenceEngineUnderTest
from authres.core.models import AccessRequest, Decision, Effect, Policy
from authres.core.policy import PolicySet
from authres.engines.contract import EngineOutcome, EngineStatus
from authres.engines.index_engine import IndexEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "semantics_v1.json"
MUTANT_PATH = PROJECT_ROOT / "tests" / "mutants" / "allow_overrides_deny.py"

with FIXTURE_PATH.open(encoding="utf-8") as handle:
    FIXTURE_CASES = json.load(handle)["cases"]

REQUEST = AccessRequest("alice", "report", "read")


class StubEngine:
    """Test-only engine with configurable decision, status, error, or delay."""

    def __init__(
        self,
        engine_id: str,
        *,
        decision: Decision | None = None,
        status: EngineStatus = EngineStatus.DECIDED,
        detail: str | None = None,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self._engine_id = engine_id
        self._decision = decision
        self._status = status
        self._detail = detail
        self._error = error
        self._delay = delay

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def engine_version(self) -> str:
        return "test-stub-1"

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        if self._delay:
            time.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return EngineOutcome(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            status=self._status,
            decision=self._decision,
            detail=self._detail,
        )


class WrongTypeEngine:
    engine_id = "wrong-type"
    engine_version = "1"

    def evaluate(self, policy_set, request):  # type: ignore[no-untyped-def]
        return {"decision": "ALLOW"}


class IdentityMismatchEngine:
    engine_id = "declared-id"
    engine_version = "1"

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        return EngineOutcome(
            engine_id="other-id",
            engine_version="1",
            status=EngineStatus.DECIDED,
            decision=Decision.ALLOW,
        )


ALLOW_ENGINE = StubEngine("stub-allow", decision=Decision.ALLOW)
DENY_ENGINE = StubEngine("stub-deny", decision=Decision.DENY)


class TestAgreement:
    def test_identical_decisions_agree(self) -> None:
        result = run_comparison(
            [
                StubEngine("a", decision=Decision.ALLOW),
                StubEngine("b", decision=Decision.ALLOW),
            ],
            PolicySet(),
            REQUEST,
        )

        assert isinstance(result, ComparisonResult)
        assert result.agreement is True
        assert result.is_disagreement is False
        assert result.decisions == {"a": "ALLOW", "b": "ALLOW"}
        assert result.reasons == {"a": None, "b": None}

    def test_different_decisions_disagree(self) -> None:
        result = run_comparison(
            [ALLOW_ENGINE, DENY_ENGINE],
            PolicySet(),
            REQUEST,
        )

        assert result.agreement is False
        assert result.is_disagreement is True
        assert result.decisions == {"stub-allow": "ALLOW", "stub-deny": "DENY"}

    def test_single_engine_agrees_with_itself(self) -> None:
        result = run_comparison([ALLOW_ENGINE], PolicySet(), REQUEST)

        assert result.agreement is True

    def test_empty_engine_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one engine"):
            run_comparison([], PolicySet(), REQUEST)

    def test_duplicate_engine_ids_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate engine ids"):
            run_comparison(
                [
                    StubEngine("same", decision=Decision.ALLOW),
                    StubEngine("same", decision=Decision.DENY),
                ],
                PolicySet(),
                REQUEST,
            )


class TestErrorAndNonDecisionSeparation:
    def test_engine_exception_is_an_error_not_a_decision(self) -> None:
        result = run_comparison(
            [
                ALLOW_ENGINE,
                StubEngine("boom", error=RuntimeError("engine crashed")),
            ],
            PolicySet(),
            REQUEST,
        )

        assert result.agreement is None
        assert result.decisions["boom"] is None
        assert len(result.error_runs) == 1
        error = result.error_runs[0]
        assert error.status is EngineStatus.ERROR
        assert "RuntimeError: engine crashed" in (error.outcome.detail or "")

    def test_timeout_is_a_separate_status(self) -> None:
        result = run_comparison(
            [
                ALLOW_ENGINE,
                StubEngine(
                    "slow", decision=Decision.ALLOW, delay=0.3
                ),
            ],
            PolicySet(),
            REQUEST,
            timeout_seconds=0.01,
        )

        assert result.agreement is None
        assert result.decisions["slow"] is None
        assert len(result.timeout_runs) == 1
        assert result.timeout_runs[0].status is EngineStatus.TIMEOUT
        assert result.error_runs[0].status is EngineStatus.TIMEOUT

    def test_indeterminate_is_not_coerced(self) -> None:
        result = run_comparison(
            [
                ALLOW_ENGINE,
                StubEngine(
                    "indeterminate",
                    status=EngineStatus.INDETERMINATE,
                    detail="engine could not decide",
                ),
            ],
            PolicySet(),
            REQUEST,
        )

        assert result.agreement is None
        assert result.decisions["indeterminate"] is None
        assert len(result.non_decided_runs) == 1
        assert result.error_runs == ()

    def test_not_applicable_is_not_coerced(self) -> None:
        result = run_comparison(
            [
                ALLOW_ENGINE,
                StubEngine(
                    "na", status=EngineStatus.NOT_APPLICABLE
                ),
            ],
            PolicySet(),
            REQUEST,
        )

        assert result.agreement is None
        assert result.decisions["na"] is None

    def test_non_engine_outcome_becomes_error(self) -> None:
        result = run_comparison(
            [ALLOW_ENGINE, WrongTypeEngine()],  # type: ignore[list-item]
            PolicySet(),
            REQUEST,
        )

        assert result.agreement is None
        assert result.error_runs[0].status is EngineStatus.ERROR
        assert "non-EngineOutcome" in (
            result.error_runs[0].outcome.detail or ""
        )

    def test_outcome_identity_mismatch_becomes_error(self) -> None:
        result = run_comparison(
            [ALLOW_ENGINE, IdentityMismatchEngine()],  # type: ignore[list-item]
            PolicySet(),
            REQUEST,
        )

        assert result.agreement is None
        assert "identity does not match" in (
            result.error_runs[0].outcome.detail or ""
        )

    def test_non_positive_timeout_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            run_comparison(
                [ALLOW_ENGINE], PolicySet(), REQUEST, timeout_seconds=0
            )


class TestBuiltInEngines:
    @pytest.mark.parametrize(
        "case", FIXTURE_CASES, ids=lambda case: case["name"]
    )
    def test_reference_and_index_agree_on_conformance_fixture(
        self, case: dict
    ) -> None:
        policy_set = PolicySet.from_dict(case["policy_document"])
        request = AccessRequest.from_dict(case["request"])

        result = run_comparison(
            [ReferenceEngineUnderTest(), IndexEngine()],
            policy_set,
            request,
        )

        assert result.agreement is True
        assert result.error_runs == ()
        assert result.decisions == {
            "authres-reference-engine": case["expected"]["decision"],
            "authres-index-engine": case["expected"]["decision"],
        }
        assert result.reasons["authres-reference-engine"] == (
            f"reason={case['expected']['reason']}"
        )
        assert result.reasons["authres-index-engine"] is None

    def test_builtin_engines_agree_on_generated_corpus(self) -> None:
        from authres.compare.generator import GeneratorConfig, generate_cases

        cases = generate_cases(
            GeneratorConfig(
                seed=7,
                policies=6,
                vocabulary_size=3,
                conflict_rate=0.5,
            ),
            count=50,
        )

        mismatches = []
        for case in cases:
            result = run_comparison(
                [ReferenceEngineUnderTest(), IndexEngine()],
                case.policy_set,
                case.request,
            )
            if result.agreement is not True:
                mismatches.append((case.case_index, result.to_dict()))

        assert mismatches == []


def _load_mutant():
    spec = importlib.util.spec_from_file_location(
        "authres_test_mutant_allow_overrides_deny", MUTANT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AllowOverridesDenyEngine()


class TestMutantDetection:
    def test_comparator_detects_known_allow_overrides_deny_fault(self) -> None:
        policies = PolicySet(
            policies=(
                Policy("alice", "report", "read", Effect.ALLOW, "a"),
                Policy("alice", "report", "read", Effect.DENY, "d"),
            )
        )
        mutant = _load_mutant()

        result = run_comparison(
            [ReferenceEngineUnderTest(), IndexEngine(), mutant],
            policies,
            REQUEST,
        )

        assert result.agreement is False
        assert result.decisions == {
            "authres-reference-engine": "DENY",
            "authres-index-engine": "DENY",
            "mutant-allow-overrides-deny": "ALLOW",
        }
        assert result.error_runs == ()

    def test_mutant_lives_outside_production_engines(self) -> None:
        assert MUTANT_PATH.exists()
        assert MUTANT_PATH.parent == PROJECT_ROOT / "tests" / "mutants"
