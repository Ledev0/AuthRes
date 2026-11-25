"""Settings screen: paths and one display preference."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label

from authres.tui.services.settings import TuiSettings
from authres.tui.widgets import TitledPanel


class SettingsScreen(Screen):
    BINDINGS = [
        Binding("s", "save_settings", "Save"),
        Binding("escape", "blur", "Unfocus input", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="content"):
            with TitledPanel("Paths", id="settings-paths"):
                yield Label(
                    "Policy directory (*.json files)", classes="status-text"
                )
                yield Input(
                    id="settings-policy-dir", placeholder="/path/to/policies"
                )
                yield Label(
                    "Export directory (session results)", classes="status-text"
                )
                yield Input(
                    id="settings-export-dir", placeholder="/path/to/results"
                )
            with TitledPanel("Display", id="settings-display"):
                yield Checkbox(
                    "Show matched policy details in result cards",
                    id="settings-show-trace",
                )
                yield Button("Save settings (s)", id="save-button")
        yield Label("", id="settings-status", classes="status-text")
        yield Footer()

    def on_screen_resume(self) -> None:
        settings = self.app.services.settings
        self.query_one("#settings-policy-dir", Input).value = str(
            settings.policy_dir
        )
        self.query_one("#settings-export-dir", Input).value = str(
            settings.export_dir
        )
        self.query_one("#settings-show-trace", Checkbox).value = (
            settings.show_matched_trace
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            self.action_save_settings()

    def action_save_settings(self) -> None:
        status = self.query_one("#settings-status", Label)
        policy_dir = Path(
            self.query_one("#settings-policy-dir", Input).value.strip()
            or self.app.services.settings.policy_dir
        ).expanduser()
        export_dir = Path(
            self.query_one("#settings-export-dir", Input).value.strip()
            or self.app.services.settings.export_dir
        ).expanduser()
        show_trace = self.query_one("#settings-show-trace", Checkbox).value

        new_settings = TuiSettings(
            policy_dir=policy_dir,
            export_dir=export_dir,
            show_matched_trace=show_trace,
        )
        error = self.app.services.settings_store.save(new_settings)
        if error is not None:
            status.update(error)
            status.add_class("error-text")
            return

        self.app.services.settings = new_settings
        warnings: list[str] = ["Settings saved."]
        if not policy_dir.is_dir():
            warnings.append(f"Warning: policy directory does not exist: {policy_dir}")
        if not export_dir.is_dir():
            warnings.append(f"Note: export directory will be created on export: {export_dir}")
        status.update(" ".join(warnings))
        status.remove_class("error-text")

    def action_blur(self) -> None:
        self.set_focus(None)
