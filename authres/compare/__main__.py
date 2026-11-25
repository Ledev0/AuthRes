"""CLI: run the synthetic engine comparison.

Usage:
    python -m authres.compare --seed 1 --cases 1000 --policies 5

This compares the in-project reference engine with the in-project Engine B.
No external engine is executed. All generated cases are synthetic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from authres.compare.generator import GeneratorConfig, generate_cases
from authres.compare.reference_adapter import ReferenceEngineUnderTest
from authres.compare.runner import ComparisonRun, compare_corpus
from authres.core.provenance import build_comparison_manifest
from authres.engines.index_engine import IndexEngine


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m authres.compare",
        description=(
            "Compare AuthRes reference engine with in-project Engine B on a "
            "seeded synthetic corpus. No external engine is involved."
        ),
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--cases", type=int, default=1000)
    parser.add_argument("--policies", type=int, default=5)
    parser.add_argument("--vocabulary", type=int, default=4)
    parser.add_argument("--conflict-rate", type=float, default=0.25)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs"),
        help="directory for disagreement JSONL and run manifest (default: runs)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="optional per-engine wall-clock budget in seconds",
    )
    return parser


def _print_summary(
    run: ComparisonRun,
    *,
    seed: int,
    config: GeneratorConfig,
    engines: list[tuple[str, str]],
    disagreement_path: Path,
    manifest_path: Path,
) -> None:
    print("AuthRes synthetic engine comparison")
    print(
        f"seed={seed} cases={run.total_cases} "
        f"policies={config.policies} vocabulary={config.vocabulary_size} "
        f"conflict_rate={config.to_dict()['conflict_rate']}"
    )
    for engine_id, engine_version in engines:
        print(f"engine: {engine_id} {engine_version}")
    print(f"total cases: {run.total_cases}")
    print(f"agreements: {run.agreements}")
    print(f"disagreements: {len(run.disagreements)}")
    print(f"engine errors: {len(run.error_cases)}")
    print(f"timeouts: {len(run.timeout_cases)}")
    print(f"non-decided cases: {len(run.non_decided_cases)}")
    print(f"conflicting ALLOW/DENY cases: {len(run.conflicting_cases)}")
    print(f"disagreement file: {disagreement_path}")
    print(f"manifest: {manifest_path}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = GeneratorConfig(
            seed=args.seed,
            policies=args.policies,
            vocabulary_size=args.vocabulary,
            conflict_rate=args.conflict_rate,
        )
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))

    if args.cases < 0:
        parser.error("--cases must be non-negative")
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout must be positive when provided")

    cases = generate_cases(config, args.cases)
    engines = [ReferenceEngineUnderTest(), IndexEngine()]
    engine_versions = [
        (engine.engine_id, engine.engine_version) for engine in engines
    ]

    run = compare_corpus(cases, engines, timeout_seconds=args.timeout)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"comparison-seed-{args.seed}-cases-{args.cases}"
    disagreement_path = output_dir / f"{stem}.disagreements.jsonl"
    manifest_path = output_dir / f"{stem}.manifest.json"

    lines = [
        json.dumps(case.to_dict(), ensure_ascii=False, allow_nan=False)
        for case in run.disagreements
    ]
    disagreement_path.write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8"
    )

    manifest = build_comparison_manifest(
        [case.to_dict() for case in cases],
        engines=dict(engine_versions),
        random_seed=args.seed,
        generator_config=config.to_dict(),
    )
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _print_summary(
        run,
        seed=args.seed,
        config=config,
        engines=engine_versions,
        disagreement_path=disagreement_path,
        manifest_path=manifest_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
