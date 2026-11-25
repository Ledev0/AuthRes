"""Seeded synthetic case generator for engine comparisons.

The vocabulary is intentionally small so that exact-match collisions and
ALLOW/DENY conflicts occur frequently. All data is synthetic; generated cases
are not measurements of any real deployment.

Determinism contract: identical ``GeneratorConfig`` and case count produce
byte-identical ``to_dict`` output on the same Python implementation. The
generator uses a private ``random.Random`` instance and no global state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from authres.core.models import AccessRequest, Effect, Policy
from authres.core.policy import PolicySet


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    """Parameters for one synthetic corpus.

    ``conflict_rate`` is the probability that a case with at least two
    policies is *constructed* to contain a request-matching ALLOW and DENY
    pair. Unforced cases can still contain conflicts, so the observed
    conflict rate may be higher. Values outside 0..1 are rejected.
    """

    seed: int
    policies: int = 5
    vocabulary_size: int = 4
    conflict_rate: float = 0.25

    def __post_init__(self) -> None:
        if type(self.seed) is not int:
            raise TypeError("seed must be an integer")
        if type(self.policies) is not int or self.policies < 0:
            raise ValueError("policies must be a non-negative integer")
        if type(self.vocabulary_size) is not int or self.vocabulary_size < 1:
            raise ValueError("vocabulary_size must be a positive integer")
        if not isinstance(self.conflict_rate, (int, float)) or isinstance(
            self.conflict_rate, bool
        ):
            raise TypeError("conflict_rate must be a number")
        if not 0.0 <= float(self.conflict_rate) <= 1.0:
            raise ValueError("conflict_rate must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "policies": self.policies,
            "vocabulary_size": self.vocabulary_size,
            "conflict_rate": float(self.conflict_rate),
        }


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    """One validated synthetic policy-set/request pair."""

    case_index: int
    policy_set: PolicySet
    request: AccessRequest

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_index": self.case_index,
            "policy_set": self.policy_set.to_dict(),
            "request": self.request.to_dict(),
        }


def _vocabulary(prefix: str, size: int) -> tuple[str, ...]:
    return tuple(f"{prefix}{index}" for index in range(size))


def _generate_case(
    rng: random.Random, config: GeneratorConfig, case_index: int
) -> GeneratedCase:
    subjects = _vocabulary("s", config.vocabulary_size)
    resources = _vocabulary("r", config.vocabulary_size)
    actions = _vocabulary("a", config.vocabulary_size)

    request = AccessRequest(
        subject=rng.choice(subjects),
        resource=rng.choice(resources),
        action=rng.choice(actions),
    )

    force_conflict = (
        config.policies >= 2 and rng.random() < float(config.conflict_rate)
    )
    rules: list[tuple[str, str, str, Effect]] = []

    if force_conflict:
        rules.append(
            (request.subject, request.resource, request.action, Effect.ALLOW)
        )
        rules.append(
            (request.subject, request.resource, request.action, Effect.DENY)
        )

    while len(rules) < config.policies:
        rules.append(
            (
                rng.choice(subjects),
                rng.choice(resources),
                rng.choice(actions),
                rng.choice((Effect.ALLOW, Effect.DENY)),
            )
        )

    # Policy order must not influence decisions; shuffling also avoids making
    # the forced conflict pair deterministically first or last.
    rng.shuffle(rules)

    policies = tuple(
        Policy(
            subject=subject,
            resource=resource,
            action=action,
            effect=effect,
            policy_id=f"p{index}",
        )
        for index, (subject, resource, action, effect) in enumerate(rules)
    )
    return GeneratedCase(
        case_index=case_index,
        policy_set=PolicySet(policies=policies),
        request=request,
    )


def generate_cases(
    config: GeneratorConfig,
    count: int,
) -> list[GeneratedCase]:
    """Generate ``count`` validated cases deterministically from ``config``."""
    if type(count) is not int or count < 0:
        raise ValueError("count must be a non-negative integer")

    rng = random.Random(config.seed)
    return [
        _generate_case(rng, config, case_index) for case_index in range(count)
    ]
