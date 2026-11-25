"""Core immutable data models for the Phase 1 authorization semantics.

The models validate all values at construction time. Policy and request
identifiers are opaque strings: they are compared exactly and are never
normalized (for example, no case folding, trimming, or wildcard handling).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from authres.core.errors import (
    AuthResError,
    PolicyValidationError,
    RequestValidationError,
)
from authres.core.jsonio import loads_strict_json


class Effect(str, Enum):
    """The only two policy effects defined in policy format version 1."""

    ALLOW = "ALLOW"
    DENY = "DENY"

    @classmethod
    def parse(cls, value: object, *, field: str = "effect") -> "Effect":
        """Parse a JSON effect value strictly.

        Only the exact uppercase strings ``ALLOW`` and ``DENY`` are accepted.
        Lowercase or mixed-case values are rejected rather than normalized.
        """
        if not isinstance(value, str):
            raise PolicyValidationError(
                f"{field} must be the string 'ALLOW' or 'DENY', "
                f"got {type(value).__name__}"
            )
        if value not in (cls.ALLOW.value, cls.DENY.value):
            raise PolicyValidationError(
                f"{field} must be 'ALLOW' or 'DENY', got {value!r}"
            )
        return cls(value)


class Decision(str, Enum):
    """An authorization decision produced by an authorization engine."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class DecisionReason(str, Enum):
    """Why the reference engine produced a decision.

    Reason codes make the default-deny case distinguishable from an explicit
    matching DENY, even though both yield ``Decision.DENY``.
    """

    DEFAULT_DENY = "DEFAULT_DENY"
    MATCHED_ALLOW = "MATCHED_ALLOW"
    MATCHED_DENY = "MATCHED_DENY"
    DENY_OVERRIDE = "DENY_OVERRIDE"


def _require_identifier(
    value: object,
    field: str,
    error_type: type[AuthResError],
) -> str:
    """Validate an opaque, non-empty string identifier without normalizing it."""
    if not isinstance(value, str):
        raise error_type(
            f"{field} must be a string, got {type(value).__name__}"
        )
    if not value.strip():
        raise error_type(f"{field} must not be empty or whitespace-only")
    return value


@dataclass(frozen=True, slots=True)
class Policy:
    """A single condition-free authorization policy rule.

    A policy matches only when subject, resource, and action all equal the
    corresponding request attributes. ``policy_id`` is optional metadata used
    for reporting; it does not affect matching or the decision.
    """

    subject: str
    resource: str
    action: str
    effect: Effect
    policy_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.subject, "Policy.subject", PolicyValidationError)
        _require_identifier(self.resource, "Policy.resource", PolicyValidationError)
        _require_identifier(self.action, "Policy.action", PolicyValidationError)

        if self.policy_id is not None:
            _require_identifier(
                self.policy_id, "Policy.policy_id", PolicyValidationError
            )

        if isinstance(self.effect, Effect):
            return
        if isinstance(self.effect, str):
            # Convenient for direct Python construction; JSON loading already
            # performs strict parsing before reaching here.
            object.__setattr__(
                self,
                "effect",
                Effect.parse(self.effect, field="Policy.effect"),
            )
            return
        raise PolicyValidationError(
            "Policy.effect must be an Effect or the string 'ALLOW' or 'DENY', "
            f"got {type(self.effect).__name__}"
        )

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, object],
        *,
        context: str = "policy",
    ) -> "Policy":
        """Build a policy from its JSON-compatible mapping representation.

        Unknown fields are rejected so that unsupported semantics (such as a
        future ``condition`` field) cannot be silently ignored.
        """
        if not isinstance(data, Mapping):
            raise PolicyValidationError(
                f"{context} must be a JSON object, got {type(data).__name__}"
            )

        required = {"subject", "resource", "action", "effect"}
        optional = {"id"}
        keys = set(data)
        problems: list[str] = []

        missing = sorted(required - keys)
        if missing:
            problems.append(
                "missing required field(s): " + ", ".join(repr(name) for name in missing)
            )
        unknown = sorted(keys - required - optional, key=repr)
        if unknown:
            problems.append(
                "unsupported field(s): " + ", ".join(repr(name) for name in unknown)
            )
        if problems:
            raise PolicyValidationError(f"{context}: " + "; ".join(problems))

        effect = Effect.parse(data["effect"], field=f"{context}.effect")

        policy_id: str | None = None
        if "id" in data:
            raw_id = data["id"]
            if not isinstance(raw_id, str):
                raise PolicyValidationError(
                    f"{context}.id must be a non-empty string when present, "
                    f"got {type(raw_id).__name__}"
                )
            policy_id = raw_id

        try:
            return cls(
                subject=data["subject"],  # type: ignore[arg-type]
                resource=data["resource"],  # type: ignore[arg-type]
                action=data["action"],  # type: ignore[arg-type]
                effect=effect,
                policy_id=policy_id,
            )
        except PolicyValidationError as exc:
            raise PolicyValidationError(f"{context}: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Return the policy in its JSON-compatible representation."""
        result: dict[str, Any] = {}
        if self.policy_id is not None:
            result["id"] = self.policy_id
        result["subject"] = self.subject
        result["resource"] = self.resource
        result["action"] = self.action
        result["effect"] = self.effect.value
        return result


@dataclass(frozen=True, slots=True)
class AccessRequest:
    """A single access request with the three required attributes."""

    subject: str
    resource: str
    action: str

    def __post_init__(self) -> None:
        _require_identifier(
            self.subject, "AccessRequest.subject", RequestValidationError
        )
        _require_identifier(
            self.resource, "AccessRequest.resource", RequestValidationError
        )
        _require_identifier(
            self.action, "AccessRequest.action", RequestValidationError
        )

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, object],
        *,
        context: str = "request",
    ) -> "AccessRequest":
        """Build a request from a JSON-compatible mapping.

        Missing and unknown fields are reported explicitly. The reference
        engine itself accepts only an ``AccessRequest`` instance, so malformed
        mappings cannot reach evaluation.
        """
        if not isinstance(data, Mapping):
            raise RequestValidationError(
                f"{context} must be a JSON object, got {type(data).__name__}"
            )

        required = {"subject", "resource", "action"}
        keys = set(data)
        problems: list[str] = []

        missing = sorted(required - keys)
        if missing:
            problems.append(
                "missing required attribute(s): "
                + ", ".join(repr(name) for name in missing)
            )
        unknown = sorted(keys - required, key=repr)
        if unknown:
            problems.append(
                "unsupported attribute(s): "
                + ", ".join(repr(name) for name in unknown)
            )
        if problems:
            raise RequestValidationError(f"{context}: " + "; ".join(problems))

        try:
            return cls(
                subject=data["subject"],  # type: ignore[arg-type]
                resource=data["resource"],  # type: ignore[arg-type]
                action=data["action"],  # type: ignore[arg-type]
            )
        except RequestValidationError as exc:
            raise RequestValidationError(f"{context}: {exc}") from exc

    @classmethod
    def from_json(cls, text: str, *, context: str = "request") -> "AccessRequest":
        """Parse a strict JSON request document.

        Uses the same duplicate-key and non-standard-constant rejection as
        policy loading.
        """
        data = loads_strict_json(
            text,
            error_type=RequestValidationError,
            document_name=f"{context} JSON",
        )
        return cls.from_dict(data, context=context)

    def to_dict(self) -> dict[str, str]:
        """Return the request in its JSON-compatible representation."""
        return {
            "subject": self.subject,
            "resource": self.resource,
            "action": self.action,
        }


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Reference-engine result with an auditable matched-policy trace.

    ``matched_policies`` follows the policy-set order. That order is for audit
    output only; it has no effect on the decision.
    """

    decision: Decision
    reason: DecisionReason
    matched_policies: tuple[Policy, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.decision, Decision):
            raise TypeError("EvaluationResult.decision must be a Decision")
        if not isinstance(self.reason, DecisionReason):
            raise TypeError("EvaluationResult.reason must be a DecisionReason")

        try:
            matched = tuple(self.matched_policies)
        except TypeError as exc:
            raise TypeError(
                "EvaluationResult.matched_policies must be an iterable of Policy"
            ) from exc
        for policy in matched:
            if not isinstance(policy, Policy):
                raise TypeError(
                    "EvaluationResult.matched_policies must contain only Policy objects"
                )

        has_allow = any(policy.effect is Effect.ALLOW for policy in matched)
        has_deny = any(policy.effect is Effect.DENY for policy in matched)

        if self.reason is DecisionReason.DEFAULT_DENY:
            if self.decision is not Decision.DENY or matched:
                raise ValueError(
                    "EvaluationResult: DEFAULT_DENY requires decision DENY "
                    "and no matched policies"
                )
        elif self.reason is DecisionReason.MATCHED_ALLOW:
            if (
                self.decision is not Decision.ALLOW
                or not matched
                or has_deny
            ):
                raise ValueError(
                    "EvaluationResult: MATCHED_ALLOW requires decision ALLOW "
                    "and at least one ALLOW-only match"
                )
        elif self.reason is DecisionReason.MATCHED_DENY:
            if (
                self.decision is not Decision.DENY
                or not matched
                or has_allow
            ):
                raise ValueError(
                    "EvaluationResult: MATCHED_DENY requires decision DENY "
                    "and at least one DENY-only match"
                )
        elif self.reason is DecisionReason.DENY_OVERRIDE:
            if self.decision is not Decision.DENY or not has_allow or not has_deny:
                raise ValueError(
                    "EvaluationResult: DENY_OVERRIDE requires decision DENY "
                    "and matches containing both ALLOW and DENY"
                )

        object.__setattr__(self, "matched_policies", matched)

    @property
    def matched_policy_ids(self) -> tuple[str | None, ...]:
        """Policy IDs of matches, in policy-set order (``None`` if absent)."""
        return tuple(policy.policy_id for policy in self.matched_policies)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible result for reproducible trace output."""
        return {
            "decision": self.decision.value,
            "reason": self.reason.value,
            "matched_policy_ids": list(self.matched_policy_ids),
            "matched_policies": [
                policy.to_dict() for policy in self.matched_policies
            ],
        }
