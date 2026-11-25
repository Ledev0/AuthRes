"""Experiment provenance: reproducible run manifests.

A run manifest records the identity of everything that influenced an
evaluation **without recording any authorization decision**. Decisions live
in ``EvaluationResult``; manifests live beside them.

Two manifest forms exist:

- ``RunManifest`` identifies one policy-set/request pair.
- ``ComparisonRunManifest`` identifies a multi-case comparison corpus and the
  set of engines that ran on it.

Identity rules:

- The policy-set identity is the SHA-256 (``canonical_sha256``) of the
  policy set's ``to_dict`` representation. Equal semantics produce equal
  hashes; formatting differences do not affect the hash.
- The request identity is the same recipe over ``AccessRequest.to_dict``.
- Engine identity is a stable id plus the package version string.

Reproducibility status: manifest *construction* is deterministic and tested
by repetition within one process/interpreter. Cross-machine reproducibility
has **not** been verified yet; do not claim it. See
``docs/semantic-validation.md`` for the evidence ladder.

The ``random_seed`` and ``generator_config`` fields record the Phase 2
synthetic corpus generator configuration. The reference engine itself uses no
randomness; ``random_seed=None`` means "no generator ran".
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from importlib.metadata import version as distribution_version
from typing import Any, Mapping

from authres import __version__
from authres.core.canonical import canonical_sha256
from authres.core.models import AccessRequest
from authres.core.policy import PolicySet

MANIFEST_VERSION = 1

SEMANTICS_VERSION = "authres-policy-v1"
REFERENCE_ENGINE_ID = "authres-reference-engine"
REFERENCE_ENGINE_VERSION = __version__

MANIFEST_HASH_ALGORITHM = "sha256"

DEFAULT_DEPENDENCY_NAMES: tuple[str, ...] = (
    "pytest",
    "textual",
    "hypothesis",
    "jsonschema",
)


def dependency_versions(
    names: tuple[str, ...] = DEFAULT_DEPENDENCY_NAMES,
) -> dict[str, str | None]:
    """Installed version of each named distribution, or None if absent."""
    result: dict[str, str | None] = {}
    for name in names:
        try:
            result[name] = distribution_version(name)
        except Exception:
            result[name] = None
    return result


@dataclass(frozen=True)
class RunManifest:
    """Identity metadata for one evaluation run. Contains no decisions."""

    manifest_version: int
    semantics_version: str
    reference_engine_id: str
    reference_engine_version: str
    policy_set_hash: str
    request_hash: str
    python_version: str
    python_implementation: str
    dependency_versions: Mapping[str, str | None]
    random_seed: int | None
    generator_config: Mapping[str, Any] = field(default_factory=dict)
    manifest_hash: str = ""

    def payload_dict(self) -> dict[str, Any]:
        """The hashed manifest content (everything except the hash itself)."""
        return {
            "manifest_version": self.manifest_version,
            "semantics_version": self.semantics_version,
            "reference_engine_id": self.reference_engine_id,
            "reference_engine_version": self.reference_engine_version,
            "policy_set_hash": self.policy_set_hash,
            "request_hash": self.request_hash,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "dependency_versions": dict(self.dependency_versions),
            "random_seed": self.random_seed,
            "generator_config": dict(self.generator_config),
        }

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible manifest including its self-describing hash."""
        result = self.payload_dict()
        result["manifest_hash_algorithm"] = MANIFEST_HASH_ALGORITHM
        result["manifest_hash"] = self.manifest_hash
        return result


def _policy_set_hash(policy_set: PolicySet) -> str:
    return canonical_sha256(policy_set.to_dict())


def _request_hash(request: AccessRequest) -> str:
    return canonical_sha256(request.to_dict())


def build_run_manifest(
    policy_set: PolicySet,
    request: AccessRequest,
    *,
    random_seed: int | None = None,
    generator_config: Mapping[str, Any] | None = None,
    dependency_names: tuple[str, ...] = DEFAULT_DEPENDENCY_NAMES,
) -> RunManifest:
    """Build a manifest for one policy-set/request pair."""
    manifest = RunManifest(
        manifest_version=MANIFEST_VERSION,
        semantics_version=SEMANTICS_VERSION,
        reference_engine_id=REFERENCE_ENGINE_ID,
        reference_engine_version=REFERENCE_ENGINE_VERSION,
        policy_set_hash=_policy_set_hash(policy_set),
        request_hash=_request_hash(request),
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        dependency_versions=dependency_versions(dependency_names),
        random_seed=random_seed,
        generator_config=dict(generator_config or {}),
    )
    object.__setattr__(
        manifest, "manifest_hash", canonical_sha256(manifest.payload_dict())
    )
    return manifest


@dataclass(frozen=True)
class ComparisonRunManifest:
    """Identity metadata for a multi-case engine comparison run.

    Contains no authorization decisions and no per-case outcomes. Those are
    separate artifacts; this manifest identifies the corpus and environment.
    """

    manifest_version: int
    semantics_version: str
    comparison_tool_id: str
    comparison_tool_version: str
    engines: Mapping[str, str]
    corpus_hash: str
    case_count: int
    python_version: str
    python_implementation: str
    dependency_versions: Mapping[str, str | None]
    random_seed: int | None
    generator_config: Mapping[str, Any] = field(default_factory=dict)
    manifest_hash: str = ""

    def payload_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "semantics_version": self.semantics_version,
            "comparison_tool_id": self.comparison_tool_id,
            "comparison_tool_version": self.comparison_tool_version,
            "engines": dict(self.engines),
            "corpus_hash": self.corpus_hash,
            "case_count": self.case_count,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "dependency_versions": dict(self.dependency_versions),
            "random_seed": self.random_seed,
            "generator_config": dict(self.generator_config),
        }

    def to_dict(self) -> dict[str, Any]:
        result = self.payload_dict()
        result["manifest_hash_algorithm"] = MANIFEST_HASH_ALGORITHM
        result["manifest_hash"] = self.manifest_hash
        return result


def build_comparison_manifest(
    corpus: list[Mapping[str, Any]],
    *,
    engines: Mapping[str, str],
    random_seed: int | None,
    generator_config: Mapping[str, Any] | None = None,
    dependency_names: tuple[str, ...] = DEFAULT_DEPENDENCY_NAMES,
) -> ComparisonRunManifest:
    """Build a run manifest over a JSON-compatible comparison corpus.

    ``engines`` maps engine id to engine version. The corpus hash is the
    canonical SHA-256 of the corpus list, so formatting of the input case
    records does not affect identity.
    """
    if not isinstance(corpus, list):
        raise TypeError("corpus must be a list of JSON-compatible case records")
    if not engines:
        raise ValueError("engines must contain at least one engine")
    for engine_id, engine_version in engines.items():
        if not isinstance(engine_id, str) or not engine_id.strip():
            raise ValueError(f"invalid engine id: {engine_id!r}")
        if not isinstance(engine_version, str) or not engine_version.strip():
            raise ValueError(
                f"invalid engine version for {engine_id!r}: {engine_version!r}"
            )

    manifest = ComparisonRunManifest(
        manifest_version=MANIFEST_VERSION,
        semantics_version=SEMANTICS_VERSION,
        comparison_tool_id="authres-compare",
        comparison_tool_version=REFERENCE_ENGINE_VERSION,
        engines=dict(engines),
        corpus_hash=canonical_sha256(corpus),
        case_count=len(corpus),
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        dependency_versions=dependency_versions(dependency_names),
        random_seed=random_seed,
        generator_config=dict(generator_config or {}),
    )
    object.__setattr__(
        manifest, "manifest_hash", canonical_sha256(manifest.payload_dict())
    )
    return manifest
