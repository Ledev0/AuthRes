"""Evaluate one access request with the AuthRes reference engine.

This command is a reproducibility and inspection aid, not an experimental
comparison tool. It loads one policy document, validates one request, and
prints the reference decision and its matched-policy trace as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from authres.core.errors import PolicyValidationError, RequestValidationError
from authres.core.models import AccessRequest
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one access request using the AuthRes reference "
            "authorization engine."
        )
    )
    parser.add_argument(
        "--policies",
        type=Path,
        required=True,
        metavar="PATH",
        help="path to a version 1 JSON policy document",
    )
    parser.add_argument(
        "--request",
        required=True,
        metavar="JSON",
        help=(
            'request JSON, for example '
            '\'{"subject":"alice","resource":"report","action":"read"}\''
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        policy_set = PolicySet.from_file(args.policies)
    except PolicyValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        request = AccessRequest.from_json(args.request)
    except RequestValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = ReferenceEngine().evaluate(policy_set, request)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
