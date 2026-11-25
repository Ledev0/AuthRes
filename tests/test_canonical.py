"""Tests for every documented canonical-encoding rule.

Each test maps to a rule row in docs/canonical-encoding.md.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from authres.core.canonical import canonical_bytes, canonical_json, canonical_sha256
from authres.core.models import AccessRequest, Effect, Policy
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine

IDENTIFIER_SCHEMA_RULE = "non-empty, not whitespace-only, never normalized"


class TestCanonicalFormRules:
    def test_keys_sorted_by_code_point(self) -> None:
        value = {"resource": "r", "action": "a", "subject": "s"}

        assert canonical_json(value) == '{"action":"a","resource":"r","subject":"s"}'

    def test_no_insignificant_whitespace(self) -> None:
        value = {"version": 1, "policies": [{"subject": "s"}]}

        text = canonical_json(value)

        assert " " not in text
        assert "\n" not in text
        assert text == (
            '{"policies":[{"subject":"s"}],"version":1}'
        )

    def test_canonical_form_is_ascii_only(self) -> None:
        value = {"subject": "alice", "note": "café — Ω"}

        text = canonical_json(value)

        assert text.isascii()
        assert "\\u" in text

    def test_control_characters_escaped_not_raw(self) -> None:
        value = {"subject": "a\u0000b", "other": "x\ty"}

        raw = canonical_bytes(value)

        assert b"\x00" not in raw
        assert b"\\u0000" in raw
        assert b"\\t" in raw  # JSON short escape for tab
        assert canonical_bytes({"subject": "x\u0007"}).endswith(b"\\u0007\"}")

    def test_version_one_numbers_canonical(self) -> None:
        assert canonical_json({"version": 1}) == '{"version":1}'
        assert canonical_json({"version": 1.0}) == '{"version":1.0}'  # documented: 1.0 is not the integer 1; parser rejects it before canonicalization

    def test_canonical_bytes_are_utf8_ascii(self) -> None:
        raw = canonical_bytes({"subject": "\u00e9"})

        assert raw == b'{"subject":"\\u00e9"}'
        assert raw.decode("utf-8") == canonical_json({"subject": "\u00e9"})

    def test_canonical_rejects_non_finite_numbers(self) -> None:
        with pytest.raises(ValueError):
            canonical_json({"x": float("nan")})
        with pytest.raises(ValueError):
            canonical_json({"x": float("inf")})

    def test_canonical_rejects_non_json_compatible_values(self) -> None:
        with pytest.raises(TypeError):
            canonical_json({"x": object()})


class TestHashRecipe:
    def test_hash_is_sha256_of_canonical_bytes(self) -> None:
        value = {"subject": "alice", "resource": "report", "action": "read"}

        expected = hashlib.sha256(canonical_bytes(value)).hexdigest()

        assert canonical_sha256(value) == expected
        assert canonical_sha256(value) == canonical_sha256(value)

    def test_formatting_differences_do_not_change_hash(self) -> None:
        doc = {"version": 1, "policies": [{"subject": "alice", "action": "read", "resource": "report", "effect": "ALLOW"}]}
        spaced = json.dumps(doc, indent=4)
        compact = json.dumps(doc, separators=(",", ":"))
        reordered = json.dumps(
            {"policies": [{"effect": "ALLOW", "resource": "report", "action": "read", "subject": "alice"}], "version": 1}
        )

        hashes = {
            canonical_sha256(json.loads(text))
            for text in (spaced, compact, reordered)
        }

        assert len(hashes) == 1


class TestUnicodeRules:
    def test_nfc_and_nfd_identifiers_are_distinct(self) -> None:
        nfc = "caf\u00e9"          # single code point U+00E9
        nfd = "cafe\u0301"         # e + combining acute U+0301
        assert nfc != nfd

        request = AccessRequest(nfc, "report", "read")
        policy_nfc = Policy(nfc, "report", "read", Effect.ALLOW)
        policy_nfd = Policy(nfd, "report", "read", Effect.ALLOW)

        result_nfc = ReferenceEngine().evaluate(
            PolicySet(policies=(policy_nfc,)), request
        )
        result_nfd = ReferenceEngine().evaluate(
            PolicySet(policies=(policy_nfd,)), request
        )

        assert result_nfc.reason.value == "MATCHED_ALLOW"
        assert result_nfd.reason.value == "DEFAULT_DENY"

    def test_no_normalization_in_canonical_form(self) -> None:
        nfc = {"subject": "caf\u00e9"}
        nfd = {"subject": "cafe\u0301"}

        assert canonical_sha256(nfc) != canonical_sha256(nfd)

    def test_case_differences_never_match(self) -> None:
        request = AccessRequest("alice", "report", "read")
        upper = Policy("ALICE", "report", "read", Effect.ALLOW)

        result = ReferenceEngine().evaluate(
            PolicySet(policies=(upper,)), request
        )

        assert result.reason.value == "DEFAULT_DENY"

    def test_whitespace_inside_identifiers_is_significant(self) -> None:
        request = AccessRequest(" alice", "report", "read")
        plain = Policy("alice", "report", "read", Effect.ALLOW)
        spaced = Policy(" alice", "report", "read", Effect.ALLOW)

        plain_result = ReferenceEngine().evaluate(
            PolicySet(policies=(plain,)), request
        )
        spaced_result = ReferenceEngine().evaluate(
            PolicySet(policies=(spaced,)), request
        )

        assert plain_result.reason.value == "DEFAULT_DENY"
        assert spaced_result.reason.value == "MATCHED_ALLOW"


class TestNulCharacters:
    def test_nul_is_permitted_identifier_content(self) -> None:
        request = AccessRequest("a\u0000b", "report", "read")
        policy = Policy("a\u0000b", "report", "read", Effect.ALLOW)

        result = ReferenceEngine().evaluate(
            PolicySet(policies=(policy,)), request
        )

        assert result.reason.value == "MATCHED_ALLOW"

    def test_nul_is_significant_in_matching(self) -> None:
        request = AccessRequest("a\u0000b", "report", "read")
        without_nul = Policy("ab", "report", "read", Effect.ALLOW)

        result = ReferenceEngine().evaluate(
            PolicySet(policies=(without_nul,)), request
        )

        assert result.reason.value == "DEFAULT_DENY"

    def test_nul_survives_canonical_round_trip(self) -> None:
        value = {"subject": "a\u0000b"}

        raw = canonical_bytes(value)
        reparsed = json.loads(raw.decode("utf-8"))

        assert reparsed == value
        assert canonical_sha256(reparsed) == canonical_sha256(value)


class TestLoneSurrogates:
    def test_lone_surrogate_is_canonical_and_stable(self) -> None:
        value = {"subject": "\ud800"}

        first = canonical_sha256(value)
        second = canonical_sha256(json.loads(canonical_json(value)))

        assert first == second
        assert "\\ud800" in canonical_json(value)

    def test_lone_surrogate_identifiers_match_exactly(self) -> None:
        request = AccessRequest("a\ud800b", "report", "read")
        policy = Policy("a\ud800b", "report", "read", Effect.ALLOW)

        result = ReferenceEngine().evaluate(
            PolicySet(policies=(policy,)), request
        )

        assert result.reason.value == "MATCHED_ALLOW"


class TestEndToEndCanonicalUsage:
    def test_policy_set_hash_matches_document_hash(self) -> None:
        document = {
            "version": 1,
            "policies": [
                {
                    "id": "p1",
                    "subject": "alice",
                    "resource": "report",
                    "action": "read",
                    "effect": "ALLOW",
                }
            ],
        }
        policy_set = PolicySet.from_json(json.dumps(document))

        assert canonical_sha256(policy_set.to_dict()) == canonical_sha256(document)

    def test_request_hash_stable_across_serializations(self) -> None:
        request = AccessRequest.from_json(
            '{"subject":"alice","resource":"report","action":"read"}'
        )

        assert canonical_sha256(request.to_dict()) == canonical_sha256(
            {"subject": "alice", "resource": "report", "action": "read"}
        )
