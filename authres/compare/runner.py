"""Corpus-level comparison runner and aggregate statistics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from authres.compare.comparator import (
    ComparisonResult,
    EngineUnderTest,
    run_comparison,
)
from authres.compare.conflicts import has_conflict
from authres.compare.generator import GeneratedCase
from authres.engines.contract import EngineStatus


@dataclass(frozen=True, slots=True)
class CaseComparison:
    """One case plus the neutral outcomes of every engine on it."""

    case: GeneratedCase
    conflicting: bool
    result: ComparisonResult

    @property
    def has_engine_error(self) -> bool:
        return any(
            run.status in (EngineStatus.ERROR, EngineStatus.TIMEOUT)
            for run in self.result.runs
        )

    @property
    def has_non_decided(self) -> bool:
        return any(
            run.status in (EngineStatus.NOT_APPLICABLE, EngineStatus.INDETERMINATE)
            for run in self.result.runs
        )

    def to_dict(self) -> dict[str, Any]:
        """Disagreement-record form. Decisions and statuses are explicit."""
        return {
            "case_index": self.case.case_index,
            "conflicting": self.conflicting,
            "policy_set": self.case.policy_set.to_dict(),
            "request": self.case.request.to_dict(),
            "comparison": self.result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    """Aggregate result of comparing all engines over a synthetic corpus."""

    cases: tuple[CaseComparison, ...]

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def agreements(self) -> int:
        return sum(1 for case in self.cases if case.result.agreement is True)

    @property
    def disagreements(self) -> tuple[CaseComparison, ...]:
        return tuple(
            case for case in self.cases if case.result.agreement is False
        )

    @property
    def error_cases(self) -> tuple[CaseComparison, ...]:
        return tuple(case for case in self.cases if case.has_engine_error)

    @property
    def timeout_cases(self) -> tuple[CaseComparison, ...]:
        return tuple(
            case
            for case in self.cases
            if any(
                run.status is EngineStatus.TIMEOUT
                for run in case.result.runs
            )
        )

    @property
    def non_decided_cases(self) -> tuple[CaseComparison, ...]:
        """Cases with INDETERMINATE/NOT_APPLICABLE and no error/timeout."""
        return tuple(
            case
            for case in self.cases
            if not case.has_engine_error and case.has_non_decided
        )

    @property
    def conflicting_cases(self) -> tuple[CaseComparison, ...]:
        return tuple(case for case in self.cases if case.conflicting)


def compare_corpus(
    cases: Sequence[GeneratedCase],
    engines: Sequence[EngineUnderTest],
    *,
    timeout_seconds: float | None = None,
) -> ComparisonRun:
    """Compare every engine on every generated case."""
    results: list[CaseComparison] = []
    for case in cases:
        result = run_comparison(
            engines,
            case.policy_set,
            case.request,
            timeout_seconds=timeout_seconds,
        )
        results.append(
            CaseComparison(
                case=case,
                conflicting=has_conflict(case.policy_set, case.request),
                result=result,
            )
        )
    return ComparisonRun(cases=tuple(results))
