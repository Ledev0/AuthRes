"""Results screen: session evaluation log with detail view and export."""

from __future__ import annotations

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Static

from authres.tui.services.evaluation_service import EvaluationRecord
from authres.tui.widgets import ResultCard, TitledPanel

_EMPTY_STATE = "No evaluations in this session yet. Run one on the Evaluation screen (e)."


class ResultsScreen(Screen):
    BINDINGS = [
        Binding("x", "export_selected", "Export selected"),
        Binding("escape", "blur", "Unfocus input", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            with TitledPanel("Session evaluations", id="results-list-panel"):
                yield Label(_EMPTY_STATE, id="results-empty", classes="status-text")
                yield DataTable(id="results-table")
            with TitledPanel("Details", id="results-detail-panel"):
                yield ResultCard(id="results-detail", show_trace=True)
                yield Static("", id="results-json")
        yield Label("", id="results-status", classes="status-text")
        yield Footer()

    def on_screen_resume(self) -> None:
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        records = self.app.services.evaluation.records
        table = self.query_one("#results-table", DataTable)
        empty = self.query_one("#results-empty", Label)

        table.clear(columns=True)
        table.add_columns("#", "Decision", "Reason", "Policy file", "Request")
        self._row_records: list[EvaluationRecord] = []

        if not records:
            empty.update(_EMPTY_STATE)
            self.query_one("#results-detail", ResultCard).set_record(None)
            self.query_one("#results-json", Static).update("")
            return

        empty.update("")
        for record in records:
            self._row_records.append(record)
            table.add_row(
                str(record.record_id),
                record.result.decision.value,
                record.result.reason.value,
                record.policy_path or "(pasted policy)",
                record.request_summary(),
            )

        if table.row_count:
            table.move_cursor(row=table.row_count - 1)
            self._show_record(records[-1])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        records = getattr(self, "_row_records", [])
        if not records:
            return
        table = self.query_one("#results-table", DataTable)
        index = min(table.cursor_row, len(records) - 1)
        self._show_record(records[index])

    def _show_record(self, record: EvaluationRecord) -> None:
        self._selected_record = record
        show_trace = self.app.services.settings.show_matched_trace
        detail = self.query_one("#results-detail", ResultCard)
        detail.set_show_trace(show_trace)
        detail.set_record(record)

        payload = record.to_export_dict()
        self.query_one("#results-json", Static).update(
            escape(json.dumps(payload, indent=2, ensure_ascii=False))
        )

    def action_export_selected(self) -> None:
        status = self.query_one("#results-status", Label)
        record = getattr(self, "_selected_record", None)
        if record is None:
            status.update("Select an evaluation to export.")
            status.add_class("error-text")
            return

        path, error = self.app.services.evaluation.export_record(
            record, self.app.services.settings.export_dir
        )
        if error is not None:
            status.update(error)
            status.add_class("error-text")
            return
        status.remove_class("error-text")
        status.update(f"Exported evaluation #{record.record_id} to {path}")

    def action_blur(self) -> None:
        self.set_focus(None)
