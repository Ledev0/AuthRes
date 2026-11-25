"""Evaluation screen: select a policy set, run the reference engine, show the result."""

from __future__ import annotations

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static

from authres.tui.widgets import ResultCard, TitledPanel

_NO_REQUEST = (
    "No pending request.\n"
    "Build one in the Request Builder (b), then return here."
)


class EvaluationScreen(Screen):
    BINDINGS = [
        Binding("r", "run_evaluation", "Run evaluation"),
        Binding("escape", "blur", "Unfocus input", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="content"):
            with TitledPanel("Policy set", id="eval-files-panel"):
                yield Label("", id="eval-policy-status", classes="status-text")
                yield ListView(id="eval-policy-list")
            with Vertical(id="eval-right"):
                with TitledPanel("Request", id="eval-request-panel"):
                    yield Static(_NO_REQUEST, id="eval-request-preview")
                with TitledPanel("Result"):
                    yield ResultCard(id="eval-result", show_trace=True)
                    yield Label("", id="eval-status", classes="status-text")
                    yield Button("Run evaluation (r)", id="run-button")
        yield Footer()

    def on_screen_resume(self) -> None:
        self.action_refresh()

    def action_refresh(self) -> None:
        listing = self.app.services.policy.list_policy_files(
            self.app.services.settings.policy_dir
        )
        self._files = listing
        list_view = self.query_one("#eval-policy-list", ListView)
        list_view.clear()
        for info in listing:
            list_view.append(ListItem(Label(info.name), name=str(info.path)))

        status = self.query_one("#eval-policy-status", Label)
        if not listing:
            status.update(
                f"No *.json files in {self.app.services.settings.policy_dir}. "
                "Adjust the directory in Settings (s)."
            )
            status.add_class("error-text")
        else:
            status.remove_class("error-text")
            selected = self.app.services.evaluation.selected_policy_path
            target = (
                selected
                if selected is not None
                and any(info.path == selected for info in listing)
                else listing[0].path
            )
            list_view.index = [
                index
                for index, info in enumerate(listing)
                if info.path == target
            ][0]
            self._update_policy_status()
        self._update_request_preview()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_view = self.query_one("#eval-policy-list", ListView)
        if list_view.index is not None and self._files:
            path = self._files[min(list_view.index, len(self._files) - 1)].path
            self.app.services.evaluation.selected_policy_path = path
            self._update_policy_status()

    def _update_policy_status(self) -> None:
        files = getattr(self, "_files", [])
        list_view = self.query_one("#eval-policy-list", ListView)
        status = self.query_one("#eval-policy-status", Label)
        if list_view.index is None or not files:
            return
        path = files[min(list_view.index, len(files) - 1)].path
        self.app.services.evaluation.selected_policy_path = path
        result = self.app.services.policy.load(path)
        if result.is_valid:
            status.remove_class("error-text")
            status.update(
                f"{path.name}: valid · "
                f"{len(result.policy_set.policies)} policy(ies)"
            )
        else:
            status.add_class("error-text")
            status.update(f"{path.name}: INVALID — {escape(result.error or '')}")

    def _update_request_preview(self) -> None:
        preview = self.query_one("#eval-request-preview", Static)
        pending = self.app.services.evaluation.pending_request
        if pending is None:
            preview.update(_NO_REQUEST)
            return
        source = self.app.services.evaluation.pending_request_source
        try:
            data = json.loads(source) if source else pending.to_dict()
        except json.JSONDecodeError:
            data = pending.to_dict()
        preview.update(
            "Pending request:\n\n"
            + escape(json.dumps(data, indent=2, ensure_ascii=False))
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-button":
            self.action_run_evaluation()

    def action_run_evaluation(self) -> None:
        status = self.query_one("#eval-status", Label)
        result_card = self.query_one("#eval-result", ResultCard)
        evaluation = self.app.services.evaluation

        if evaluation.pending_request is None:
            status.update("No request. Press b to build one first.")
            status.add_class("error-text")
            return

        policy_path = evaluation.selected_policy_path
        if policy_path is None:
            status.update("No policy file selected.")
            status.add_class("error-text")
            return

        loaded = self.app.services.policy.load(policy_path)
        if not loaded.is_valid:
            status.update(f"Policy invalid: {escape(loaded.error or '')}")
            status.add_class("error-text")
            return

        try:
            record = evaluation.evaluate(
                policy_set=loaded.policy_set,
                request=evaluation.pending_request,
                policy_path=str(policy_path),
                policy_source=loaded.raw_text,
            )
        except Exception as exc:  # surface, never crash the TUI
            status.update(f"Evaluation failed: {escape(str(exc))}")
            status.add_class("error-text")
            return

        status.remove_class("error-text")
        result_card.set_record(record)
        status.update(
            f"Evaluation #{record.record_id} complete. "
            "See Results (v) for the session log."
        )

    def action_blur(self) -> None:
        self.set_focus(None)
