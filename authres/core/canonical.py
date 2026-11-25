"""Canonical serialization and identity hashing for AuthRes JSON data.

The canonical form is a total function over JSON-compatible values (as
produced by the existing ``to_dict`` methods): every input has exactly one
output byte string, so equal semantics always produce equal hashes and
unequal identifiers never collide through normalization.

Rules (see ``docs/canonical-encoding.md`` for the normative statement):

- Object keys are sorted by code point.
- No insignificant whitespace; ``,`/``:`` separators only.
- Output is pure ASCII: non-ASCII characters are emitted as ``\\uXXXX``
  escapes (this keeps the form total even for lone surrogates and makes the
  byte encoding trivially UTF-8).
- Control characters, including NUL, are escaped (``\\u0000``), never
  emitted raw and never stripped.
- ``NaN``/``Infinity`` cannot occur in parsed documents (rejected at the
  input boundary) and ``allow_nan=False`` makes them an error here too.
- No normalization of any kind is applied to identifiers.

This module performs no validation of its own: it serializes the JSON
compatible representation that the core models already validated.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CANONICAL_HASH_ALGORITHM = "sha256"


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text for a JSON-compatible value.

    Raises ``ValueError`` on non-finite numbers (``NaN``, ``Infinity``) and
    ``TypeError`` on values that are not JSON-compatible.
    """
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
        indent=None,
    )


def canonical_bytes(value: Any) -> bytes:
    """Canonical JSON text encoded as UTF-8 (identical to ASCII bytes)."""
    return canonical_json(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Lowercase hex SHA-256 digest of the canonical encoding of ``value``."""
    digest = hashlib.sha256(canonical_bytes(value))
    return digest.hexdigest()
