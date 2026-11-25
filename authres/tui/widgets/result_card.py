"""Result summary card widget.

Formats an :class:`~authres.tui.services.evaluation_service.EvaluationRecord`
for display. Decision coloring uses fixed markup for the two known decision
values; all variable data is escaped so policy/request content can never be
interpreted as markup.
"""

from __future__ import annotations

from textual.widgets import Static
from rich.markup import escape

from authres.tui.services.evaluation_service import EvaluationRecord

_EMPTY_TEXT = (
    "No evaluation yet.\n"
    "Build a request (b), choose a policy set (p), then run it (e)."
)

_DECISION_STYLE = {
    "ALLOW": "bold green",
    "DENY": "bold red",
}


class ResultCard(Static):
    """Shows the latest or selected evaluation, or a helpful empty state."""

    DEFAULT_CSS = """
    ResultCard {
        padding: 0 1;
        height: auto;
    }
    """

    def __init__(self, *, show_trace: bool = True, **kwargs) -> None:
        super().__init__(markup=True, **kwargs)
        self._show_trace = show_trace
        self.update(_EMPTY_TEXT)

    def set_show_trace(self, show_trace: bool) -> None:
        self._show_trace = show_trace

    def set_record(self, record: EvaluationRecord | None) -> None:
        if record is None:
            self.update(_EMPTY_TEXT)
            return

        decision = record.result.decision.value
        style = _DECISION_STYLE.get(decision, "bold")
        lines = [
            f"[{style}]Decision: {decision}[/]",
            f"Reason: {escape(record.result.reason.value)}",
            f"Request: {escape(record.request_summary())}",
        ]
        if record.policy_path:
            lines.append(f"Policy file: {escape(record.policy_path)}")
        if self._show_trace:
            ids = ", ".join(
                str(pid) if pid is not None else "(no id)"
                for pid in record.result.matched_policy_ids
            )
            lines.append(
                f"Matched policy IDs: {escape(ids) if ids else '(none)'}"
            )
        self.update("\n".join(lines))
