"""Policy Explorer screen: browse, preview, and validate policy JSON files."""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from authres.tui.services.policy_service import PolicyFileInfo
from authres.tui.widgets import TitledPanel

_EMPTY_STATE = "No policy files found."


class PolicyExplorerScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Refresh list"),
        Binding("escape", "blur", "Unfocus input", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="content"):
            with TitledPanel("Policy files", id="explorer-files"):
                yield Label("", id="policy-status", classes="status-text")
                yield ListView(id="policy-file-list")
            with TitledPanel("Preview", id="explorer-preview"):
                yield Static(_EMPTY_STATE, id="policy-preview")
                yield Label("", id="policy-summary", classes="status-text")
        yield Footer()

    def on_screen_resume(self) -> None:
        self.action_refresh()

    def action_refresh(self) -> None:
        listing = self.app.services.policy.list_policy_files(
            self.app.services.settings.policy_dir
        )
        self._files: list[PolicyFileInfo] = listing
        list_view = self.query_one("#policy-file-list", ListView)
        list_view.clear()
        for info in listing:
            list_view.append(ListItem(Label(info.name), name=str(info.path)))

        status = self.query_one("#policy-status", Label)
        if not listing:
            status.update(
                f"No *.json files in {self.app.services.settings.policy_dir}. "
                "Adjust the directory in Settings (s)."
            )
            status.add_class("error-text")
            self.query_one("#policy-preview", Static).update(_EMPTY_STATE)
            self.query_one("#policy-summary", Label).update("")
            return
        status.remove_class("error-text")
        status.update(
            f"{len(listing)} file(s) in {self.app.services.settings.policy_dir}"
        )

        previous = getattr(self, "_selected_path", None)
        index = next(
            (
                position
                for position, info in enumerate(listing)
                if info.path == previous
            ),
            0,
        )
        list_view.index = index
        self._show_selected()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._show_selected()

    def _show_selected(self) -> None:
        files = getattr(self, "_files", [])
        list_view = self.query_one("#policy-file-list", ListView)
        if list_view.index is None or not files:
            return
        index = min(list_view.index, len(files) - 1)
        info = files[index]
        self._selected_path = info.path
        result = self.app.services.policy.load(info.path)
        self.app.policy_selection = result

        preview = self.query_one("#policy-preview", Static)
        summary = self.query_one("#policy-summary", Label)

        if result.is_valid:
            preview.update(escape(result.raw_text or ""))
            count = len(result.policy_set.policies)
            ids = [
                policy.policy_id if policy.policy_id is not None else "(no id)"
                for policy in result.policy_set.policies
            ]
            summary.update(
                f"Valid · {count} policy(ies) · ids: "
                + escape(", ".join(ids) if ids else "(empty set)")
            )
        else:
            preview.update(escape(result.raw_text or "(unreadable file)"))
            summary.update(f"Invalid · {escape(result.error or '')}")
            summary.add_class("error-text")
            return
        summary.remove_class("error-text")

    def action_blur(self) -> None:
        self.set_focus(None)
