"""Strict JSON representation and loading for authorization policy sets.

Policy format version 1 is an object with exactly two fields: ``version`` and
``policies``. The parser rejects unknown fields, duplicate JSON keys, and
malformed values. Rejection is intentional: silently ignoring unsupported
fields would make the reference model disagree with an intended specification
without any signal.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from authres.core.errors import PolicyValidationError
from authres.core.jsonio import loads_strict_json
from authres.core.models import Policy

POLICY_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class PolicySet:
    """An immutable, validated collection of policies.

    The collection may be empty. An empty policy set is valid and produces the
    default DENY decision for every request.
    """

    policies: tuple[Policy, ...] = ()
    version: int = POLICY_FORMAT_VERSION

    def __post_init__(self) -> None:
        try:
            policies = tuple(self.policies)
        except TypeError as exc:
            raise PolicyValidationError(
                "policies must be an iterable of Policy objects"
            ) from exc

        if type(self.version) is not int or self.version != POLICY_FORMAT_VERSION:
            raise PolicyValidationError(
                f"version must be the integer {POLICY_FORMAT_VERSION}, "
                f"got {self.version!r}"
            )

        for index, policy in enumerate(policies):
            if not isinstance(policy, Policy):
                raise PolicyValidationError(
                    f"policies[{index}] must be a Policy, "
                    f"got {type(policy).__name__}"
                )

        seen_ids: dict[str, int] = {}
        for index, policy in enumerate(policies):
            if policy.policy_id is None:
                continue
            if policy.policy_id in seen_ids:
                first_index = seen_ids[policy.policy_id]
                raise PolicyValidationError(
                    f"duplicate policy id {policy.policy_id!r} at policies[{index}]; "
                    f"first used at policies[{first_index}]"
                )
            seen_ids[policy.policy_id] = index

        object.__setattr__(self, "policies", policies)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "PolicySet":
        """Build and validate a policy set from a JSON-compatible mapping."""
        if not isinstance(data, Mapping):
            raise PolicyValidationError(
                f"policy document must be a JSON object, got {type(data).__name__}"
            )

        required = {"version", "policies"}
        keys = set(data)
        problems: list[str] = []

        missing = sorted(required - keys)
        if missing:
            problems.append(
                "missing required field(s): "
                + ", ".join(repr(name) for name in missing)
            )
        unknown = sorted(keys - required, key=repr)
        if unknown:
            problems.append(
                "unsupported field(s): "
                + ", ".join(repr(name) for name in unknown)
            )
        if problems:
            raise PolicyValidationError(
                "policy document: " + "; ".join(problems)
            )

        version = data["version"]
        if type(version) is not int or version != POLICY_FORMAT_VERSION:
            raise PolicyValidationError(
                f"version must be the integer {POLICY_FORMAT_VERSION}, "
                f"got {version!r}"
            )

        raw_policies = data["policies"]
        if not isinstance(raw_policies, list):
            raise PolicyValidationError(
                "policies must be a JSON array, "
                f"got {type(raw_policies).__name__}"
            )

        policies: list[Policy] = []
        for index, raw_policy in enumerate(raw_policies):
            policies.append(
                Policy.from_dict(raw_policy, context=f"policies[{index}]")
            )

        return cls(policies=tuple(policies), version=version)

    @classmethod
    def from_json(cls, text: str) -> "PolicySet":
        """Parse a strict JSON policy document from a string."""
        if not isinstance(text, str):
            raise PolicyValidationError(
                f"policy JSON must be a string, got {type(text).__name__}"
            )

        data = loads_strict_json(
            text,
            error_type=PolicyValidationError,
            document_name="policy JSON",
        )
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicySet":
        """Read and parse a UTF-8 JSON policy document from disk."""
        policy_path = Path(path)
        try:
            text = policy_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PolicyValidationError(
                f"cannot read policy file {policy_path}: {exc}"
            ) from exc

        try:
            return cls.from_json(text)
        except PolicyValidationError as exc:
            raise PolicyValidationError(f"{policy_path}: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Return the policy set in its JSON-compatible representation."""
        return {
            "version": self.version,
            "policies": [policy.to_dict() for policy in self.policies],
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize the policy set to deterministic JSON."""
        return (
            json.dumps(
                self.to_dict(),
                indent=indent,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )
