"""Reference-engine wrapper for the comparison layer.

The reference engine remains untouched. This module only adapts its
``EvaluationResult`` into the neutral ``EngineOutcome`` consumed by the
comparator. It is the only comparison module that imports the reference
engine; Engine B has no dependency on it.
"""

from __future__ import annotations

from authres import __version__
from authres.core.models import AccessRequest
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine
from authres.engines.contract import EngineOutcome, EngineStatus

REFERENCE_ENGINE_ID = "authres-reference-engine"
REFERENCE_ENGINE_VERSION = __version__


class ReferenceEngineUnderTest:
    """Neutral adapter around the project's reference engine."""

    @property
    def engine_id(self) -> str:
        return REFERENCE_ENGINE_ID

    @property
    def engine_version(self) -> str:
        return REFERENCE_ENGINE_VERSION

    def __init__(self, engine: ReferenceEngine | None = None) -> None:
        self._engine = engine if engine is not None else ReferenceEngine()

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        result = self._engine.evaluate(policy_set, request)
        return EngineOutcome(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            status=EngineStatus.DECIDED,
            decision=result.decision,
            detail=f"reason={result.reason.value}",
        )
