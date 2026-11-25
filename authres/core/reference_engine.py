"""Deterministic reference authorization engine for policy format version 1.

The engine is the reference model ("oracle") for the first phase. It has no
randomness, clock access, external I/O, or hidden state. Evaluation depends
only on the validated ``PolicySet`` and ``AccessRequest`` arguments.
"""

from __future__ import annotations

from authres.core.models import (
    AccessRequest,
    Decision,
    DecisionReason,
    Effect,
    EvaluationResult,
    Policy,
)
from authres.core.policy import PolicySet


def _matches(policy: Policy, request: AccessRequest) -> bool:
    """Return true only when all three request attributes match exactly."""
    return (
        policy.subject == request.subject
        and policy.resource == request.resource
        and policy.action == request.action
    )


class ReferenceEngine:
    """Evaluate requests under the documented version 1 semantics.

    Matching is exact and case-sensitive. DENY overrides ALLOW whenever both
    effects appear among matching policies. If no policy matches, the result
    is DENY.
    """

    def evaluate(
        self,
        policy_set: PolicySet,
        request: AccessRequest,
    ) -> EvaluationResult:
        """Evaluate one request against one policy set.

        Raises:
            TypeError: If either argument is not the validated model type.
        """
        if not isinstance(policy_set, PolicySet):
            raise TypeError(
                "policy_set must be a PolicySet, "
                f"got {type(policy_set).__name__}"
            )
        if not isinstance(request, AccessRequest):
            raise TypeError(
                "request must be an AccessRequest, "
                f"got {type(request).__name__}"
            )

        matched = tuple(
            policy
            for policy in policy_set.policies
            if _matches(policy, request)
        )

        if not matched:
            return EvaluationResult(
                decision=Decision.DENY,
                reason=DecisionReason.DEFAULT_DENY,
                matched_policies=(),
            )

        has_allow = any(policy.effect is Effect.ALLOW for policy in matched)
        has_deny = any(policy.effect is Effect.DENY for policy in matched)

        if has_deny:
            reason = (
                DecisionReason.DENY_OVERRIDE
                if has_allow
                else DecisionReason.MATCHED_DENY
            )
            return EvaluationResult(
                decision=Decision.DENY,
                reason=reason,
                matched_policies=matched,
            )

        return EvaluationResult(
            decision=Decision.ALLOW,
            reason=DecisionReason.MATCHED_ALLOW,
            matched_policies=matched,
        )
