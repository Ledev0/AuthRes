"""Tests for the plain-text demonstration script.

The demo is executed as a subprocess so the test observes exactly what a user
sees. No production behavior is changed by these tests.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "demo" / "run_demo.py"
FINAL_LINE = (
    "Synthetic data only. Engine B and the mutant are not external engines."
)


@pytest.fixture(scope="module")
def demo_output() -> str:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            str(DEMO_PATH),
            "--seed",
            "1",
            "--cases",
            "1000",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    return completed.stdout


def _section(output: str, start: str, end: str | None = None) -> str:
    begin = output.index(start)
    if end is None:
        return output[begin:]
    return output[begin : output.index(end, begin)]


def _count(text: str, label: str) -> int:
    match = re.search(rf"^{re.escape(label)}: (\d+)$", text, re.MULTILINE)
    assert match is not None, f"missing {label!r} in output:\n{text}"
    return int(match.group(1))


def test_section_1_agrees(demo_output: str) -> None:
    section = _section(
        demo_output, "1. SINGLE CASE", "2. SYNTHETIC RUN"
    )
    assert "decision: DENY" in section
    assert "matched policy IDs: allow-alice-read-report" in section
    assert "deny-alice-read-report" in section
    assert "reason: DENY_OVERRIDE" in section
    assert "Result: AGREE" in section


def test_section_2_has_no_disagreements_for_seed_1(demo_output: str) -> None:
    section = _section(
        demo_output, "2. SYNTHETIC RUN", "3. FAULT DETECTION"
    )
    assert _count(section, "total cases") == 1000
    assert _count(section, "agreements") == 1000
    assert _count(section, "disagreements") == 0
    assert _count(section, "engine errors") == 0
    assert _count(section, "timeouts") == 0


def test_section_3_detects_injected_fault(demo_output: str) -> None:
    section = _section(demo_output, "3. FAULT DETECTION")
    assert "INJECTED FAULT - FOR DEMONSTRATION ONLY" in section
    assert _count(section, "mutant disagreements") > 0
    assert "Minimal case:" in section
    assert "deciding rule: docs/policy-semantics.md" in section
    assert "rule 2 (DENY overrides ALLOW)" in section


def test_output_is_plain_text_within_width(demo_output: str) -> None:
    lines = demo_output.rstrip("\n").splitlines()
    assert lines[-1] == FINAL_LINE
    assert all(len(line) <= 100 for line in lines)
    assert demo_output.isascii()
