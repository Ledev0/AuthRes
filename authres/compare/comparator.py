"""Decision comparison layer for independent engine implementations.

The comparator consumes only neutral :class:`~authres.engines.contract.
EngineOutcome` values. It never sees engine-native structures and never
converts an execution failure, timeout, or non-decision into ALLOW or DENY.

Agreement is defined only among engines that returned ``DECIDED``:

- all decided engines identical  -> agreement ``True``
- all decided engines but differ -> agreement ``False``
- any engine non-DECIDED         -> agreement ``None`` (not a data point)

Errors and timeouts are reported as their own class and excluded from
agreement statistics.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from authres.core.models import AccessRequest, Decision
from authres.core.policy import PolicySet
from authres.engines.contract import EngineOutcome, EngineStatus


class EngineUnderTest(Protocol):
    """A runnable engine with a neutral, one-call evaluation interface.

    Adapters may implement their own compile/execute/normalize stages; the
    comparator only needs this composed entry point.
    """

    @property
    def engine_id(self) -> str:
        ...

    @property
    def engine_version(self) -> str:
        ...

    def evaluate(
        self, policy_set: PolicySet, request: AccessRequest
    ) -> EngineOutcome:
        ...


@dataclass(frozen=True, slots=True)
class EngineRun:
    """One engine's outcome for one comparison case."""

    engine_id: str
    engine_version: str
    outcome: EngineOutcome

    @property
    def status(self) -> EngineStatus:
        return self.outcome.status

    @property
    def decision(self) -> Decision | None:
        return self.outcome.decision


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Structured result of running a list of engines on one case."""

    runs: tuple[EngineRun, ...]
    agreement: bool | None

    @property
    def is_disagreement(self) -> bool:
        return self.agreement is False

    @property
    def decisions(self) -> dict[str, str | None]:
        """Engine id -> decision value, or None for non-decided outcomes."""
        return {
            run.engine_id: (
                run.decision.value if run.decision is not None else None
            )
            for run in self.runs
        }

    @property
    def reasons(self) -> dict[str, str | None]:
        """Engine id -> engine-provided diagnostic detail.

        The reference adapter records its reason code here; engines that do
        not expose a reason leave it as ``None``. No reason is invented.
        """
        return {run.engine_id: run.outcome.detail for run in self.runs}

    @property
    def error_runs(self) -> tuple[EngineRun, ...]:
        return tuple(
            run
            for run in self.runs
            if run.status in (EngineStatus.ERROR, EngineStatus.TIMEOUT)
        )

    @property
    def timeout_runs(self) -> tuple[EngineRun, ...]:
        return tuple(
            run for run in self.runs if run.status is EngineStatus.TIMEOUT
        )

    @property
    def non_decided_runs(self) -> tuple[EngineRun, ...]:
        return tuple(run for run in self.runs if not run.outcome.has_decision)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible record; never invents missing decisions."""
        return {
            "agreement": self.agreement,
            "engines": [
                {
                    "engine_id": run.engine_id,
                    "engine_version": run.engine_version,
                    **run.outcome.to_dict(),
                }
                for run in self.runs
            ],
        }


def _engine_identity(engine: EngineUnderTest) -> tuple[str, str]:
    try:
        engine_id = engine.engine_id
        engine_version = engine.engine_version
    except Exception as exc:  # identity properties are configuration errors
        raise ValueError(
            f"engine {type(engine).__name__} does not expose a valid identity: {exc}"
        ) from exc
    if not isinstance(engine_id, str) or not engine_id.strip():
        raise ValueError(
            f"engine {type(engine).__name__} has an invalid engine_id: {engine_id!r}"
        )
    if not isinstance(engine_version, str) or not engine_version.strip():
        raise ValueError(
            f"engine {type(engine).__name__} has an invalid engine_version: "
            f"{engine_version!r}"
        )
    return engine_id, engine_version


def _error_outcome(
    engine_id: str, engine_version: str, detail: str
) -> EngineOutcome:
    return EngineOutcome(
        engine_id=engine_id,
        engine_version=engine_version,
        status=EngineStatus.ERROR,
        decision=None,
        detail=detail,
    )


def _invoke(
    engine: EngineUnderTest,
    policy_set: PolicySet,
    request: AccessRequest,
    engine_id: str,
    engine_version: str,
) -> EngineOutcome:
    try:
        outcome = engine.evaluate(policy_set, request)
    except Exception as exc:
        return _error_outcome(
            engine_id,
            engine_version,
            f"{type(exc).__name__}: {exc}",
        )

    if not isinstance(outcome, EngineOutcome):
        return _error_outcome(
            engine_id,
            engine_version,
            "engine returned a non-EngineOutcome value: "
            f"{type(outcome).__name__}",
        )
    if outcome.engine_id != engine_id or outcome.engine_version != engine_version:
        return _error_outcome(
            engine_id,
            engine_version,
            "outcome identity does not match engine identity: "
            f"declared {engine_id!r}/{engine_version!r}, "
            f"returned {outcome.engine_id!r}/{outcome.engine_version!r}",
        )
    return outcome


def _invoke_with_timeout(
    engine: EngineUnderTest,
    policy_set: PolicySet,
    request: AccessRequest,
    engine_id: str,
    engine_version: str,
    timeout_seconds: float,
) -> EngineOutcome:
    """Run an engine call with a wall-clock budget.

    A daemon worker thread performs the call. On timeout this function returns
    a TIMEOUT outcome immediately; the worker thread may continue in the
    background because Python cannot safely kill it. Callers must treat a
    timed-out engine as unavailable for that case.
    """
    results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("outcome", engine.evaluate(policy_set, request)))
        except Exception as exc:
            results.put(("error", exc))

    thread = threading.Thread(
        target=worker,
        name=f"authres-compare-{engine_id}",
        daemon=True,
    )
    thread.start()
    try:
        kind, payload = results.get(timeout=timeout_seconds)
    except queue.Empty:
        return EngineOutcome(
            engine_id=engine_id,
            engine_version=engine_version,
            status=EngineStatus.TIMEOUT,
            decision=None,
            detail=(
                f"engine did not return within {timeout_seconds:g} seconds; "
                "worker thread left running as daemon"
            ),
        )

    if kind == "error":
        assert isinstance(payload, Exception)
        return _error_outcome(
            engine_id,
            engine_version,
            f"{type(payload).__name__}: {payload}",
        )

    outcome = payload
    if not isinstance(outcome, EngineOutcome):
        return _error_outcome(
            engine_id,
            engine_version,
            "engine returned a non-EngineOutcome value: "
            f"{type(outcome).__name__}",
        )
    if outcome.engine_id != engine_id or outcome.engine_version != engine_version:
        return _error_outcome(
            engine_id,
            engine_version,
            "outcome identity does not match engine identity: "
            f"declared {engine_id!r}/{engine_version!r}, "
            f"returned {outcome.engine_id!r}/{outcome.engine_version!r}",
        )
    return outcome


def run_comparison(
    engines: Sequence[EngineUnderTest],
    policy_set: PolicySet,
    request: AccessRequest,
    *,
    timeout_seconds: float | None = None,
) -> ComparisonResult:
    """Run every engine on one policy-set/request pair.

    ``timeout_seconds`` is optional; when omitted, engines run inline and a
    slow engine blocks the comparison (the recommended mode for the built-in
    deterministic engines).
    """
    if not engines:
        raise ValueError("run_comparison requires at least one engine")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive when provided")

    identities = [_engine_identity(engine) for engine in engines]
    ids = [engine_id for engine_id, _ in identities]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate engine ids in comparison: {ids!r}")

    runs: list[EngineRun] = []
    for engine, (engine_id, engine_version) in zip(engines, identities):
        if timeout_seconds is None:
            outcome = _invoke(
                engine, policy_set, request, engine_id, engine_version
            )
        else:
            outcome = _invoke_with_timeout(
                engine,
                policy_set,
                request,
                engine_id,
                engine_version,
                timeout_seconds,
            )
        runs.append(
            EngineRun(
                engine_id=engine_id,
                engine_version=engine_version,
                outcome=outcome,
            )
        )

    decided = [run for run in runs if run.outcome.has_decision]
    if len(decided) != len(runs):
        agreement: bool | None = None
    else:
        agreement = len({run.decision for run in decided}) == 1

    return ComparisonResult(runs=tuple(runs), agreement=agreement)
