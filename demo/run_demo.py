#!/usr/bin/env python3
"""Plain-text AuthRes demonstration.

Run from the project root:

    python demo/run_demo.py [--seed N --cases N]

The demo uses only existing project modules. Section 3 also loads the
test-only mutant ``tests/mutants/allow_overrides_deny.py``. That engine is not
production code, is not an external engine, and exists only to demonstrate
that the comparator detects a known injected fault.

All generated cases and decisions in this demo are synthetic.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# These imports require the project root on sys.path when run as a script.
from authres.compare.comparator import (  # noqa: E402
    ComparisonResult,
    EngineUnderTest,
    run_comparison,
)
from authres.compare.generator import (  # noqa: E402
    GeneratedCase,
    GeneratorConfig,
    generate_cases,
)
from authres.compare.reference_adapter import (  # noqa: E402
    REFERENCE_ENGINE_ID,
    ReferenceEngineUnderTest,
)
from authres.compare.runner import compare_corpus  # noqa: E402
from authres.core.models import (  # noqa: E402
    AccessRequest,
    DecisionReason,
    Effect,
    EvaluationResult,
    Policy,
)
from authres.core.policy import PolicySet  # noqa: E402
from authres.core.reference_engine import ReferenceEngine  # noqa: E402
from authres.engines.index_engine import IndexEngine  # noqa: E402

LINE_WIDTH = 79
CONFLICT_POLICY_PATH = PROJECT_ROOT / "policies" / "examples" / "conflict.json"
MUTANT_PATH = PROJECT_ROOT / "tests" / "mutants" / "allow_overrides_deny.py"
FINAL_LINE = (
    "Synthetic data only. Engine B and the mutant are not external engines."
)


def _section(title: str) -> None:
    print()
    print("=" * LINE_WIDTH)
    print(title)
    print("=" * LINE_WIDTH)


def _policy_line(policy: Policy) -> str:
    policy_id = policy.policy_id if policy.policy_id is not None else "(no id)"
    return (
        f"{policy_id}: {policy.subject} / {policy.resource} / "
        f"{policy.action} -> {policy.effect.value}"
    )


def _matched_policy_ids(result: EvaluationResult) -> str:
    if not result.matched_policies:
        return "(none)"
    return ", ".join(
        policy_id if policy_id is not None else "(no id)"
        for policy_id in result.matched_policy_ids
    )


def _verdict(result: ComparisonResult) -> str:
    if result.agreement is True:
        return "AGREE"
    if result.agreement is False:
        return "DISAGREE"
    return "NO DECISION"


def _run_single_case() -> None:
    _section("1. SINGLE CASE")
    policy_set = PolicySet.from_file(CONFLICT_POLICY_PATH)
    request = AccessRequest("alice", "report", "read")
    engines = [ReferenceEngineUnderTest(), IndexEngine()]
    comparison = run_comparison(engines, policy_set, request)
    # The neutral adapter deliberately drops match traces. Call the reference
    # engine directly only for the display-only trace and reason.
    reference = ReferenceEngine().evaluate(policy_set, request)

    index_engine = engines[1]
    lookup = index_engine.execute(index_engine.compile(policy_set), request)
    effects = ", ".join(
        effect.value
        for effect in sorted(lookup.effects, key=lambda item: item.value)
    )
    if not effects:
        effects = "(none)"

    reference_run = next(
        run for run in comparison.runs if run.engine_id == REFERENCE_ENGINE_ID
    )
    index_run = next(
        run
        for run in comparison.runs
        if run.engine_id == index_engine.engine_id
    )

    print(f"policy file: {CONFLICT_POLICY_PATH.relative_to(PROJECT_ROOT)}")
    print(f"request: {request.subject} / {request.resource} / {request.action}")
    print("policies:")
    for policy in policy_set.policies:
        print(f"  {_policy_line(policy)}")
    print()
    print("reference engine:")
    print(
        "  decision: "
        f"{reference_run.decision.value if reference_run.decision else '(none)'}"
    )
    print(f"  matched policy IDs: {_matched_policy_ids(reference)}")
    print(f"  reason: {reference.reason.value}")
    print()
    print("Engine B:")
    print(
        "  decision: "
        f"{index_run.decision.value if index_run.decision else '(none)'}"
    )
    print("  matched policy IDs: not exposed (index stores effects only)")
    print(f"  effects found: {effects}")
    print(
        "  reason: "
        f"{index_run.outcome.detail or 'not exposed (Engine B returns no reason)'}"
    )
    print()
    print(f"Result: {_verdict(comparison)}")


def _run_synthetic(seed: int, case_count: int) -> list[GeneratedCase]:
    _section("2. SYNTHETIC RUN")
    config = GeneratorConfig(seed=seed, policies=5)
    cases = generate_cases(config, case_count)
    run = compare_corpus(cases, [ReferenceEngineUnderTest(), IndexEngine()])

    print(
        f"seed={seed} cases={run.total_cases} policies={config.policies} "
        f"vocabulary={config.vocabulary_size} "
        f"conflict_rate={float(config.conflict_rate):g}"
    )
    print("engines: authres-reference-engine vs authres-index-engine (Engine B)")
    print(f"total cases: {run.total_cases}")
    print(f"agreements: {run.agreements}")
    print(f"disagreements: {len(run.disagreements)}")
    print(f"engine errors: {len(run.error_cases)}")
    print(f"timeouts: {len(run.timeout_cases)}")
    print(f"non-decided cases: {len(run.non_decided_cases)}")
    print(f"conflicting ALLOW/DENY cases: {len(run.conflicting_cases)}")
    return cases


def _load_mutant() -> EngineUnderTest:
    """Load the test-only known-fault engine; section 3 calls this only."""
    spec = importlib.util.spec_from_file_location(
        "authres_demo_mutant_allow_overrides_deny", MUTANT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test-only mutant: {MUTANT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AllowOverridesDenyEngine()


def _minimal_conflict_policy_set(case: GeneratedCase) -> PolicySet | None:
    """Keep one matching ALLOW and one matching DENY rule, if both exist."""
    request = case.request
    matching = [
        policy
        for policy in case.policy_set.policies
        if policy.subject == request.subject
        and policy.resource == request.resource
        and policy.action == request.action
    ]
    allow = next(
        (policy for policy in matching if policy.effect is Effect.ALLOW), None
    )
    deny = next(
        (policy for policy in matching if policy.effect is Effect.DENY), None
    )
    if allow is None or deny is None:
        return None

    selected = tuple(
        policy
        for policy in case.policy_set.policies
        if policy is allow or policy is deny
    )
    return PolicySet(policies=selected, version=case.policy_set.version)


def _rule_for_reason(reason: DecisionReason) -> str:
    if reason is DecisionReason.DEFAULT_DENY:
        return "section 6, rule 1 (default DENY when no policy matches)"
    if reason is DecisionReason.DENY_OVERRIDE:
        return "section 6, rule 2 (DENY overrides ALLOW)"
    if reason is DecisionReason.MATCHED_DENY:
        return "section 6, rule 2 (a matching DENY decides DENY)"
    return "section 6, rule 3 (all matching policies are ALLOW)"


def _run_fault_detection(cases: list[GeneratedCase]) -> None:
    _section(
        "3. FAULT DETECTION (INJECTED FAULT - FOR DEMONSTRATION ONLY)"
    )
    print(
        'Mutant under test: "ALLOW overrides DENY" '
        "(test-only known-fault engine)."
    )
    print("Source: tests/mutants/allow_overrides_deny.py. NOT production code.")
    print("This section deliberately compares against a wrong engine.")
    print()

    mutant = _load_mutant()
    run = compare_corpus(cases, [ReferenceEngineUnderTest(), mutant])
    disagreements = run.disagreements

    print(f"cases compared: {run.total_cases}")
    print(f"mutant disagreements: {len(disagreements)}")
    if not disagreements:
        print("No disagreement found; no minimal case to show.")
        return

    first = disagreements[0]
    print()
    print(
        f"First disagreement: case {first.case.case_index} "
        f"(original policy count: {len(first.case.policy_set.policies)})"
    )

    policy_set = first.case.policy_set
    comparison = first.result
    reduced = _minimal_conflict_policy_set(first.case)
    if reduced is not None:
        reduced_comparison = run_comparison(
            [ReferenceEngineUnderTest(), mutant], reduced, first.case.request
        )
        if reduced_comparison.agreement is False:
            policy_set = reduced
            comparison = reduced_comparison
            print(
                "Minimal case: non-matching and redundant matching rules "
                "removed;"
            )
            print("the same disagreement reproduces.")
        else:
            print(
                "Minimal reduction did not reproduce; showing the original "
                "case."
            )

    print()
    print("policies:")
    for policy in policy_set.policies:
        print(f"  {_policy_line(policy)}")

    request = first.case.request
    print(f"request: {request.subject} / {request.resource} / {request.action}")
    # Display-only reference trace; comparison still used the neutral adapter.
    reference = ReferenceEngine().evaluate(policy_set, request)
    mutant_run = next(
        item for item in comparison.runs if item.engine_id == mutant.engine_id
    )
    mutant_reason = (
        mutant_run.outcome.detail
        or "not exposed (the mutant returns no reason code)"
    )
    print(
        f"reference: {reference.decision.value} "
        f"(reason {reference.reason.value})"
    )
    print(
        f"mutant: {mutant_run.decision.value if mutant_run.decision else '(none)'} "
        f"(reason: {mutant_reason})"
    )
    print()
    print("deciding rule: docs/policy-semantics.md")
    print(f"  {_rule_for_reason(reference.reason)}")
    if reference.reason in (
        DecisionReason.MATCHED_DENY,
        DecisionReason.DENY_OVERRIDE,
    ):
        print('  "If any policy in M has effect DENY, the decision is DENY,')
        print('   even if other matching policies have effect ALLOW."')
        print("  The reference engine follows this rule; the mutant inverts it.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python demo/run_demo.py",
        description=(
            "Run the AuthRes plain-text demo: one fixed case, one synthetic "
            "comparison run, and one injected-fault detection run."
        ),
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--cases", type=int, default=1000)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cases < 0:
        parser.error("--cases must be non-negative")

    _run_single_case()
    cases = _run_synthetic(args.seed, args.cases)
    _run_fault_detection(cases)
    print()
    print(FINAL_LINE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
