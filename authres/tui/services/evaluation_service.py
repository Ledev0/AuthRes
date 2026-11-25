"""Session evaluation recording for the AuthRes TUI.

The service orchestrates the existing ``ReferenceEngine`` and records each
evaluation performed in the current session. It implements no authorization
logic: the decision always comes from ``ReferenceEngine.evaluate``, and
exports use the existing serialization contracts (``to_dict`` methods and
``PolicySet.to_json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from authres.core.models import AccessRequest, EvaluationResult
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine


@dataclass(frozen=True)
class EvaluationRecord:
    """One reference evaluation performed during the current TUI session."""

    record_id: int
    policy_path: str | None
    policy_set: PolicySet | None
    policy_source: str | None
    request: AccessRequest
    request_source: str
    result: EvaluationResult

    def request_summary(self) -> str:
        return (
            f"{self.request.subject} / {self.request.resource}"
            f" / {self.request.action}"
        )

    def to_export_dict(self) -> dict[str, Any]:
        """Export through existing serialization contracts only."""
        return {
            "record_id": self.record_id,
            "policy": self.policy_set.to_dict() if self.policy_set else None,
            "policy_path": self.policy_path,
            "request": self.request.to_dict(),
            "result": self.result.to_dict(),
        }


class EvaluationService:
    """Run the reference engine and keep session-scoped results."""

    def __init__(self) -> None:
        self._records: list[EvaluationRecord] = []
        self._next_id = 1
        self.pending_request: AccessRequest | None = None
        self.pending_request_source: str | None = None
        self.selected_policy_path: Path | None = None

    @property
    def records(self) -> tuple[EvaluationRecord, ...]:
        return tuple(self._records)

    def evaluate(
        self,
        *,
        policy_set: PolicySet,
        request: AccessRequest,
        policy_path: str | None = None,
        policy_source: str | None = None,
    ) -> EvaluationRecord:
        """Evaluate one request and record the result.

        Raises whatever ``ReferenceEngine.evaluate`` raises on invalid
        arguments; callers are responsible for surfacing errors. Only
        successful evaluations are recorded.
        """
        result = ReferenceEngine().evaluate(policy_set, request)
        record = EvaluationRecord(
            record_id=self._next_id,
            policy_path=policy_path,
            policy_set=policy_set,
            policy_source=policy_source,
            request=request,
            request_source=json.dumps(
                request.to_dict(), ensure_ascii=False, sort_keys=True
            ),
            result=result,
        )
        self._next_id += 1
        self._records.append(record)
        return record

    def latest(self) -> EvaluationRecord | None:
        return self._records[-1] if self._records else None

    def set_pending_request(
        self, request: AccessRequest, source: str
    ) -> None:
        self.pending_request = request
        self.pending_request_source = source

    def export_record(
        self, record: EvaluationRecord, directory: Path | str
    ) -> tuple[Path, str | None]:
        """Write one record as JSON. Returns (path, error)."""
        export_dir = Path(directory).expanduser()
        path = export_dir / f"authres_eval_{record.record_id:04d}.json"
        try:
            export_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    record.to_export_dict(), indent=2, ensure_ascii=False
                )
                + "\n",
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            return path, f"cannot export record {record.record_id}: {exc}"
        return path, None
