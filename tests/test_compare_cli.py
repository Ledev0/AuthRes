"""CLI tests for ``python -m authres.compare``.

These execute the real module in a subprocess and inspect its stdout and
written artifacts. All cases are synthetic.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from authres.core.canonical import canonical_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, output: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "authres.compare",
            *args,
            "--output",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def parse_count(stdout: str, label: str) -> int:
    match = re.search(rf"^{re.escape(label)}: (\d+)$", stdout, re.MULTILINE)
    assert match is not None, f"missing {label!r} in output:\n{stdout}"
    return int(match.group(1))


class TestCompareCli:
    def test_seeded_synthetic_run_writes_artifacts(self, tmp_path) -> None:
        result = run_cli(
            "--seed",
            "3",
            "--cases",
            "25",
            "--policies",
            "4",
            "--vocabulary",
            "3",
            "--conflict-rate",
            "0.5",
            output=tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        assert "AuthRes synthetic engine comparison" in result.stdout
        assert "engine: authres-reference-engine" in result.stdout
        assert "engine: authres-index-engine" in result.stdout

        total = parse_count(result.stdout, "total cases")
        agreements = parse_count(result.stdout, "agreements")
        disagreements = parse_count(result.stdout, "disagreements")
        errors = parse_count(result.stdout, "engine errors")
        non_decided = parse_count(result.stdout, "non-decided cases")
        conflicts = parse_count(result.stdout, "conflicting ALLOW/DENY cases")

        assert total == 25
        assert total == agreements + disagreements + errors + non_decided
        assert 0 <= conflicts <= total

        disagreement_path = (
            tmp_path / "comparison-seed-3-cases-25.disagreements.jsonl"
        )
        manifest_path = (
            tmp_path / "comparison-seed-3-cases-25.manifest.json"
        )
        assert disagreement_path.exists()
        assert manifest_path.exists()
        assert str(disagreement_path) in result.stdout
        assert str(manifest_path) in result.stdout

        lines = [
            line
            for line in disagreement_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert len(lines) == disagreements
        for line in lines:
            record = json.loads(line)
            assert "policy_set" in record
            assert "request" in record
            assert "comparison" in record
            assert record["comparison"]["agreement"] is False

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["case_count"] == 25
        assert manifest["random_seed"] == 3
        assert manifest["generator_config"] == {
            "seed": 3,
            "policies": 4,
            "vocabulary_size": 3,
            "conflict_rate": 0.5,
        }
        assert manifest["engines"] == {
            "authres-reference-engine": "0.1.0",
            "authres-index-engine": "1.0.0",
        }
        assert manifest["semantics_version"] == "authres-policy-v1"
        assert len(manifest["corpus_hash"]) == 64
        assert int(manifest["corpus_hash"], 16) >= 0

        payload = {
            key: value
            for key, value in manifest.items()
            if key not in ("manifest_hash", "manifest_hash_algorithm")
        }
        assert manifest["manifest_hash_algorithm"] == "sha256"
        assert manifest["manifest_hash"] == canonical_sha256(payload)
        assert "decision" not in manifest_path.read_text(encoding="utf-8")

    def test_same_seed_reproduces_identical_artifacts(self, tmp_path) -> None:
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"

        first = run_cli(
            "--seed", "9", "--cases", "30", "--policies", "5",
            output=first_dir,
        )
        second = run_cli(
            "--seed", "9", "--cases", "30", "--policies", "5",
            output=second_dir,
        )

        assert first.returncode == second.returncode == 0
        assert first.stdout.replace(str(first_dir), "<OUT>") == second.stdout.replace(
            str(second_dir), "<OUT>"
        )

        for suffix in (".disagreements.jsonl", ".manifest.json"):
            name = f"comparison-seed-9-cases-30{suffix}"
            assert (first_dir / name).read_bytes() == (
                second_dir / name
            ).read_bytes()

    @pytest.mark.parametrize(
        "extra",
        [
            ["--conflict-rate", "2"],
            ["--policies", "-1"],
            ["--vocabulary", "0"],
            ["--cases", "-1"],
        ],
    )
    def test_invalid_arguments_fail_cleanly(self, tmp_path, extra) -> None:
        result = run_cli(
            "--seed", "1", "--cases", "1", *extra, output=tmp_path
        )

        assert result.returncode == 2
        assert result.stderr
        assert "Traceback" not in result.stderr

    def test_zero_cases_is_allowed(self, tmp_path) -> None:
        result = run_cli(
            "--seed", "1", "--cases", "0", output=tmp_path
        )

        assert result.returncode == 0, result.stderr
        assert parse_count(result.stdout, "total cases") == 0
        assert parse_count(result.stdout, "agreements") == 0
        assert parse_count(result.stdout, "disagreements") == 0
        assert (
            tmp_path / "comparison-seed-1-cases-0.disagreements.jsonl"
        ).read_text(encoding="utf-8") == ""
