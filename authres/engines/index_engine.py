"""Engine B: an index-and-lookup implementation of policy semantics v1.

This engine was written from ``docs/policy-semantics.md`` alone. It is not a
copy of, and does not import, ``authres.core.reference_engine``. The evaluation
strategy is deliberately different from the reference engine:

1. ``compile`` builds a dictionary keyed by ``(subject, resource, action)``
   whose value is the set of effects declared for that exact triple.
2. ``execute`` performs one dictionary lookup for the request.
3. ``normalize`` applies the documented combination rule: absent key means
   default DENY; any matching DENY means DENY; otherwise matching ALLOWs mean
   ALLOW.

Independence caveat: this engine was authored by an AI coding agent from the
same specification and in the same project as the reference engine. It is an
*independent implementation attempt*, not independent human validation and not
an external authorization engine. Agreement between it and the reference
engine is not proof that the specification is correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from authres.core.models import AccessRequest, Decision, Effect
from authres.core.policy import PolicySet
from authres.engines.contract import EngineOutcome, EngineStatus

ENGINE_ID = "authres-index-engine"
ENGINE_VERSION = "1.0.0"

PolicyKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class CompiledIndex:
    """Engine-native artifact: exact-match index of declared effects."""

    index: Mapping[PolicyKey, frozenset[Effect]]
    rule_count: int


@dataclass(frozen=True, slots=True)
class LookupResult:
    """Raw engine output for one request: the effects found by lookup.

    An empty set means no policy rule matched. The set records effects, not
    policy instances; this engine deliberately makes no matched-policy trace.
    """

    effects: frozenset[Effect]


class IndexEngine:
    """Dictionary-index implementation of AuthRes policy semantics version 1."""

    @property
    def engine_id(self) -> str:
        return ENGINE_ID

    @property
    def engine_version(self) -> str:
        return ENGINE_VERSION

    def compile(self, policy_set: PolicySet) -> CompiledIndex:
        """Build the exact-match effect index for a validated policy set."""
        mutable: dict[PolicyKey, set[Effect]] = {}
        for policy in policy_set.policies:
            key = (policy.subject, policy.resource, policy.action)
            mutable.setdefault(key, set()).add(policy.effect)

        frozen = {
            key: frozenset(effects) for key, effects in mutable.items()
        }
        return CompiledIndex(
            index=MappingProxyType(frozen),
            rule_count=len(policy_set.policies),
        )

    def execute(
        self,
        compiled_policy: CompiledIndex,
        request: AccessRequest,
    ) -> LookupResult:
        """Look up one request in the compiled index (no decision yet)."""
        key = (request.subject, request.resource, request.action)
        return LookupResult(
            effects=compiled_policy.index.get(key, frozenset())
        )

    def normalize(self, raw_result: LookupResult) -> EngineOutcome:
        """Apply the documented default and DENY-overrides-ALLOW rule."""
        if not raw_result.effects:
            decision = Decision.DENY  # default deny: no matching rule
        elif Effect.DENY in raw_result.effects:
            decision = Decision.DENY  # any matching DENY overrides ALLOW
        else:
            decision = Decision.ALLOW

        return EngineOutcome(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            status=EngineStatus.DECIDED,
            decision=decision,
            detail=None,
        )

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        """Convenience composition of the three adapter stages."""
        return self.normalize(self.execute(self.compile(policy_set), request))
