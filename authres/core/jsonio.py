"""Strict JSON decoding shared by policy and request boundaries.

Policy and request documents must obey the same JSON rules. This module
contains no model semantics; it only rejects ambiguous or non-standard JSON
and lets the caller choose the validation error type.
"""

from __future__ import annotations

import json
from typing import Any, NoReturn

from authres.core.errors import AuthResError


def loads_strict_json(
    text: str,
    *,
    error_type: type[AuthResError],
    document_name: str,
) -> Any:
    """Parse JSON while rejecting duplicate keys and non-standard constants.

    ``json.loads`` normally accepts duplicate object keys (last value wins) and
    the non-standard constants ``NaN`` and ``Infinity``. Both are unsafe at a
    research input boundary: they can make the executed input differ from the
    apparent input. Callers provide the error type and a document label so
    policy and request errors remain distinguishable.
    """
    if not isinstance(text, str):
        raise error_type(
            f"{document_name} must be a JSON string, got {type(text).__name__}"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise error_type(
                    f"{document_name}: duplicate key in JSON object: {key!r}"
                )
            result[key] = value
        return result

    def reject_nonstandard_constant(value: str) -> NoReturn:
        raise error_type(
            f"{document_name}: invalid JSON constant {value!r}; "
            "NaN and Infinity are not valid JSON"
        )

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonstandard_constant,
        )
    except AuthResError:
        raise
    except json.JSONDecodeError as exc:
        raise error_type(
            f"{document_name}: invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc
