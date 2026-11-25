"""Engine comparison package.

This package compares the project's reference engine with a second in-project
implementation written from the same specification. It does not integrate any
external authorization engine, and agreement here is not external validation.
"""

from authres.compare.comparator import (
    ComparisonResult,
    EngineRun,
    EngineUnderTest,
    run_comparison,
)
from authres.compare.conflicts import has_conflict
from authres.compare.generator import (
    GeneratedCase,
    GeneratorConfig,
    generate_cases,
)
from authres.compare.runner import CaseComparison, ComparisonRun, compare_corpus

__all__ = [
    "CaseComparison",
    "ComparisonResult",
    "ComparisonRun",
    "EngineRun",
    "EngineUnderTest",
    "GeneratedCase",
    "GeneratorConfig",
    "compare_corpus",
    "generate_cases",
    "has_conflict",
    "run_comparison",
]
