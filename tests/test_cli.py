"""CLI integration tests for the strict request boundary and stable output."""

from __future__ import annotations

import json
from pathlib import Path

from main import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "policies" / "examples"


def test_cli_evaluates_conflict_and_emits_json(capsys) -> None:
    exit_code = main(
        [
            "--policies",
            str(EXAMPLES_DIR / "conflict.json"),
            "--request",
            '{"subject":"alice","resource":"report","action":"read"}',
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert captured.err == ""
    assert payload["decision"] == "DENY"
    assert payload["reason"] == "DENY_OVERRIDE"
    assert payload["matched_policy_ids"] == [
        "allow-alice-read-report",
        "deny-alice-read-report",
    ]


def test_cli_rejects_duplicate_request_keys(capsys) -> None:
    exit_code = main(
        [
            "--policies",
            str(EXAMPLES_DIR / "basic_allow.json"),
            "--request",
            (
                '{"subject":"alice","subject":"bob",'
                '"resource":"report","action":"read"}'
            ),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "duplicate key" in captured.err


def test_cli_rejects_missing_request_attribute(capsys) -> None:
    exit_code = main(
        [
            "--policies",
            str(EXAMPLES_DIR / "basic_allow.json"),
            "--request",
            '{"subject":"alice","resource":"report"}',
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "missing required attribute" in captured.err


def test_cli_rejects_malformed_request_json(capsys) -> None:
    exit_code = main(
        [
            "--policies",
            str(EXAMPLES_DIR / "basic_allow.json"),
            "--request",
            "not-json",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "invalid JSON" in captured.err
