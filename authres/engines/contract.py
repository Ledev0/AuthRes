"""Neutral adapter and outcome contract for future external engines.

The reference implementation remains in ``authres.core.reference_engine`` and
does not import this package. External adapters must compile AuthRes policies
into engine-specific artifacts, execute their own engine, and normalize the
raw result into :class:`EngineOutcome`.

No adapter is implemented here. The contract intentionally distinguishes an
authorization decision from execution statuses such as not applicable,
indeterminate, error, and timeout.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeVar

from authres.core.models import AccessRequest, Decision
from authres.core.policy import PolicySet


class EngineStatus(str, Enum):
    """Normalized status of one external-engine execution.

    ``DECIDED`` is the only status that carries an authorization decision.
    The other statuses are execution outcomes and must never be silently
    coerced to ALLOW or DENY.
    """

    DECIDED = "DECIDED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INDETERMINATE = "INDETERMINATE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


def _require_non_empty(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{field} must not be empty or whitespace-only")
    return value


@dataclass(frozen=True, slots=True)
class EngineOutcome:
    """A normalized external-engine outcome.

    ``detail`` is a human-readable diagnostic. It is required for ERROR and
    TIMEOUT so those outcomes cannot be recorded without an explanation.

    This type deliberately has no reference-specific reason or matched-policy
    trace. Those belong to the reference engine and must not be fabricated for
    external engines.
    """

    engine_id: str
    engine_version: str
    status: EngineStatus
    decision: Decision | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.engine_id, "EngineOutcome.engine_id")
        _require_non_empty(self.engine_version, "EngineOutcome.engine_version")

        if not isinstance(self.status, EngineStatus):
            raise TypeError("EngineOutcome.status must be an EngineStatus")

        if self.status is EngineStatus.DECIDED:
            if not isinstance(self.decision, Decision):
                raise ValueError(
                    "EngineOutcome: DECIDED requires an ALLOW or DENY decision"
                )
        elif self.decision is not None:
            raise ValueError(
                "EngineOutcome: only DECIDED outcomes may carry a decision; "
                f"{self.status.value} must use decision=None"
            )

        if self.detail is not None and not isinstance(self.detail, str):
            raise TypeError("EngineOutcome.detail must be a string or None")

        if self.status in (EngineStatus.ERROR, EngineStatus.TIMEOUT):
            if not self.detail or not self.detail.strip():
                raise ValueError(
                    f"EngineOutcome: {self.status.value} requires a detail"
                )

    @property
    def has_decision(self) -> bool:
        """True only for a normalized authorization decision."""
        return self.status is EngineStatus.DECIDED

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible normalized outcome."""
        return {
            "engine_id": self.engine_id,
            "engine_version": self.engine_version,
            "status": self.status.value,
            "decision": (
                self.decision.value if self.decision is not None else None
            ),
            "detail": self.detail,
        }


TCompiled = TypeVar("TCompiled")
TRaw = TypeVar("TRaw")


class EngineAdapter(Protocol[TCompiled, TRaw]):
    """Structural protocol for a future independent engine adapter.

    The stages are intentionally separate:

    1. ``compile`` translates a canonical AuthRes policy set into an opaque
       engine-specific artifact.
    2. ``execute`` runs the engine against one canonical request and returns
       an opaque raw result.
    3. ``normalize`` converts the raw result into a neutral
       :class:`EngineOutcome`.

    The future comparison layer is outside this protocol. Adapters must not
    import or call the reference engine or its private matching helper.
    """

    @property
    def engine_id(self) -> str:
        """Stable identifier recorded in every outcome."""
        ...

    @property
    def engine_version(self) -> str:
        """Engine version recorded in every outcome."""
        ...

    def compile(self, policy_set: PolicySet) -> TCompiled:
        """Translate canonical policies into an engine-native artifact."""
        ...

    def execute(
        self,
        compiled_policy: TCompiled,
        request: AccessRequest,
    ) -> TRaw:
        """Execute one request against an engine-native policy artifact."""
        ...

    def normalize(self, raw_result: TRaw) -> EngineOutcome:
        """Normalize a raw engine result without inventing a decision."""
        ...
