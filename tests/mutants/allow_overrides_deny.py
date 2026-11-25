"""TEST-ADEQUACY MUTANT ONLY. NOT AN AUTHORS ENGINE.

This is a copy of the index-and-lookup strategy with one deliberately injected
fault: ALLOW overrides DENY instead of DENY overriding ALLOW. It exists only to
prove that the comparator detects a known wrong decision. It must never be
imported by any code under ``authres/`` and must never be used to make claims
about correctness.

Generated from docs/policy-semantics.md section 6, with rule 2 inverted.
"""

from __future__ import annotations

from authres.core.models import AccessRequest, Decision, Effect
from authres.core.policy import PolicySet
from authres.engines.contract import EngineOutcome, EngineStatus

ENGINE_ID = "mutant-allow-overrides-deny"
ENGINE_VERSION = "0.0.0-test-mutant"


class AllowOverridesDenyEngine:
    """Known-fault engine used only by comparator tests."""

    @property
    def engine_id(self) -> str:
        return ENGINE_ID

    @property
    def engine_version(self) -> str:
        return ENGINE_VERSION

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        index: dict[tuple[str, str, str], set[Effect]] = {}
        for policy in policy_set.policies:
            key = (policy.subject, policy.resource, policy.action)
            index.setdefault(key, set()).add(policy.effect)
        effects = frozenset(
            index.get((request.subject, request.resource, request.action), ())
        )

        if not effects:
            decision = Decision.DENY
        elif Effect.ALLOW in effects:
            decision = Decision.ALLOW  # INJECTED FAULT: ALLOW wins
        else:
            decision = Decision.DENY

        return EngineOutcome(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            status=EngineStatus.DECIDED,
            decision=decision,
            detail=None,
        )
