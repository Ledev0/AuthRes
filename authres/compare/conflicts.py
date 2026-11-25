"""Conflict classification for comparison cases.

A conflict is defined by ``docs/policy-semantics.md`` section 6.1: the request
matches at least one ALLOW policy and at least one DENY policy. This is
descriptive metadata for experiment statistics, not an authorization
decision and not a vulnerability claim.
"""

from __future__ import annotations

from authres.core.models import AccessRequest, Effect
from authres.core.policy import PolicySet


def has_conflict(policy_set: PolicySet, request: AccessRequest) -> bool:
    """True when the request matches both an ALLOW and a DENY policy."""
    matched_allow = False
    matched_deny = False

    for policy in policy_set.policies:
        if (
            policy.subject != request.subject
            or policy.resource != request.resource
            or policy.action != request.action
        ):
            continue
        if policy.effect is Effect.ALLOW:
            matched_allow = True
        elif policy.effect is Effect.DENY:
            matched_deny = True
        if matched_allow and matched_deny:
            return True

    return False
