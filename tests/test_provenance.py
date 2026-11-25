"""Tests for run-manifest construction and identity hashing.

Manifest construction is deterministic and tested by repetition within one
process. Cross-environment reproducibility is NOT claimed by these tests.
"""

from __future__ import annotations

import json
import platform

import pytest

from authres import __version__
from authres.core.canonical import canonical_sha256
from authres.core.models import AccessRequest
from authres.core.policy import PolicySet
from authres.core.provenance import (
    MANIFEST_HASH_ALGORITHM,
    MANIFEST_VERSION,
    REFERENCE_ENGINE_ID,
    SEMANTICS_VERSION,
    build_comparison_manifest,
    build_run_manifest,
    dependency_versions,
)

POLICY_DOC = {
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


@pytest.fixture()
def inputs():
    policy_set = PolicySet.from_json(json.dumps(POLICY_DOC))
    request = AccessRequest("alice", "report", "read")
    return policy_set, request


class TestManifestConstruction:
    def test_fixed_identity_fields(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(policy_set, request)

        assert manifest.manifest_version == MANIFEST_VERSION
        assert manifest.semantics_version == SEMANTICS_VERSION
        assert manifest.reference_engine_id == REFERENCE_ENGINE_ID
        assert manifest.reference_engine_version == __version__

    def test_policy_set_hash_uses_canonical_recipe(self, inputs) -> None:
        policy_set, _ = inputs

        manifest = build_run_manifest(policy_set, AccessRequest("x", "y", "z"))

        assert manifest.policy_set_hash == canonical_sha256(POLICY_DOC)

    def test_request_hash_uses_canonical_recipe(self, inputs) -> None:
        _, request = inputs

        manifest = build_run_manifest(PolicySet(), request)

        assert manifest.request_hash == canonical_sha256(request.to_dict())

    def test_repeated_construction_is_identical(self, inputs) -> None:
        policy_set, request = inputs

        first = build_run_manifest(policy_set, request)
        second = build_run_manifest(policy_set, request)

        assert first.to_dict() == second.to_dict()

    def test_formatting_does_not_change_policy_hash(self, inputs) -> None:
        policy_set_spaced = PolicySet.from_json(json.dumps(POLICY_DOC, indent=4))
        policy_set_compact = PolicySet.from_json(
            json.dumps(POLICY_DOC, separators=(",", ":"))
        )
        _, request = inputs

        hash_spaced = build_run_manifest(policy_set_spaced, request).policy_set_hash
        hash_compact = build_run_manifest(
            policy_set_compact, request
        ).policy_set_hash

        assert hash_spaced == hash_compact

    def test_environment_fields_recorded(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(policy_set, request)

        assert manifest.python_version == platform.python_version()
        assert manifest.python_implementation == platform.python_implementation()
        assert set(manifest.dependency_versions) == {
            "pytest",
            "textual",
            "hypothesis",
            "jsonschema",
        }
        assert all(
            value is None or isinstance(value, str)
            for value in manifest.dependency_versions.values()
        )

    def test_random_seed_defaults_to_none(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(policy_set, request)

        assert manifest.random_seed is None
        assert manifest.generator_config == {}

    def test_seed_and_generator_config_round_trip(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(
            policy_set,
            request,
            random_seed=1234,
            generator_config={"case_count": 10, "alphabet": "ascii"},
        )

        assert manifest.random_seed == 1234
        assert manifest.generator_config == {
            "case_count": 10,
            "alphabet": "ascii",
        }


class TestManifestSerialization:
    def test_manifest_hash_describes_payload(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(policy_set, request)
        payload = manifest.payload_dict()

        assert manifest.manifest_hash == canonical_sha256(payload)
        assert manifest.manifest_hash == manifest.manifest_hash.lower()

    def test_to_dict_is_json_compatible_and_hash_covers_content(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(policy_set, request)
        exported = manifest.to_dict()

        assert exported["manifest_hash_algorithm"] == MANIFEST_HASH_ALGORITHM == "sha256"
        rehash = canonical_sha256(
            {key: value for key, value in exported.items() if key not in ("manifest_hash", "manifest_hash_algorithm")}
        )
        assert rehash == exported["manifest_hash"]

        reparsed = json.loads(json.dumps(exported))
        assert reparsed == exported

    def test_manifest_contains_no_authorization_decision(self, inputs) -> None:
        policy_set, request = inputs

        manifest = build_run_manifest(policy_set, request)
        exported = manifest.to_dict()

        forbidden = {"decision", "reason", "matched_policy_ids", "result", "ALLOW", "DENY"}
        assert not forbidden & set(exported)
        assert all(not isinstance(value, dict) or "decision" not in value for value in exported.values())


class TestDependencyVersions:
    def test_reported_for_installed_packages(self) -> None:
        versions = dependency_versions(("pytest",))

        assert versions["pytest"] is not None
        assert versions["pytest"].count(".") >= 1

    def test_missing_package_reports_none(self) -> None:
        versions = dependency_versions(("definitely-not-a-distribution",))

        assert versions["definitely-not-a-distribution"] is None


class TestComparisonManifest:
    CORPUS = [
        {
            "case_index": 0,
            "policy_set": POLICY_DOC,
            "request": {"subject": "alice", "resource": "report", "action": "read"},
        }
    ]
    ENGINES = {
        "authres-reference-engine": "0.1.0",
        "authres-index-engine": "1.0.0",
    }

    def test_identity_fields_and_corpus_hash(self) -> None:
        manifest = build_comparison_manifest(
            self.CORPUS,
            engines=self.ENGINES,
            random_seed=1,
            generator_config={"policies": 5, "vocabulary_size": 4},
        )

        assert manifest.manifest_version == MANIFEST_VERSION
        assert manifest.semantics_version == SEMANTICS_VERSION
        assert manifest.case_count == 1
        assert manifest.corpus_hash == canonical_sha256(self.CORPUS)
        assert manifest.random_seed == 1
        assert manifest.generator_config == {
            "policies": 5,
            "vocabulary_size": 4,
        }
        assert manifest.engines == self.ENGINES

    def test_manifest_hash_covers_payload(self) -> None:
        manifest = build_comparison_manifest(
            self.CORPUS, engines=self.ENGINES, random_seed=None
        )
        exported = manifest.to_dict()

        assert exported["manifest_hash_algorithm"] == MANIFEST_HASH_ALGORITHM
        assert exported["manifest_hash"] == canonical_sha256(
            manifest.payload_dict()
        )

    def test_repeated_construction_is_identical(self) -> None:
        first = build_comparison_manifest(
            self.CORPUS, engines=self.ENGINES, random_seed=1
        )
        second = build_comparison_manifest(
            list(reversed(self.CORPUS)),
            engines=dict(reversed(list(self.ENGINES.items()))),
            random_seed=1,
        )

        # A one-element corpus and mapping order cannot change identity.
        assert first.to_dict() == second.to_dict()

    def test_corpus_key_order_does_not_change_hash(self) -> None:
        reordered = [
            {
                "request": self.CORPUS[0]["request"],
                "policy_set": self.CORPUS[0]["policy_set"],
                "case_index": 0,
            }
        ]

        first = build_comparison_manifest(
            self.CORPUS, engines=self.ENGINES, random_seed=1
        )
        second = build_comparison_manifest(
            reordered, engines=self.ENGINES, random_seed=1
        )

        assert first.corpus_hash == second.corpus_hash

    def test_contains_no_authorization_decision(self) -> None:
        manifest = build_comparison_manifest(
            self.CORPUS, engines=self.ENGINES, random_seed=1
        )
        exported = manifest.to_dict()

        forbidden = {"decision", "reason", "result", "ALLOW", "DENY"}
        assert not forbidden & set(exported)
        assert "decision" not in json.dumps(exported)
        assert "ALLOW" not in json.dumps(exported)
        assert "DENY" not in json.dumps(exported)

    def test_invalid_engine_mapping_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one engine"):
            build_comparison_manifest(
                self.CORPUS, engines={}, random_seed=1
            )

    def test_non_list_corpus_rejected(self) -> None:
        with pytest.raises(TypeError, match="corpus"):
            build_comparison_manifest(
                tuple(self.CORPUS), engines=self.ENGINES, random_seed=1  # type: ignore[arg-type]
            )
