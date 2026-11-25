"""Request Builder screen: construct and validate an AccessRequest."""

from __future__ import annotations

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from authres.core.errors import RequestValidationError
from authres.core.models import AccessRequest
from authres.tui.widgets import TitledPanel


class RequestBuilderScreen(Screen):
    BINDINGS = [
        Binding("ctrl+b", "build_request", "Build request"),
        Binding("escape", "blur", "Unfocus input", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="content"):
            with TitledPanel("Attributes", id="builder-form"):
                yield Label("subject", classes="status-text")
                yield Input(id="subject", placeholder="e.g. alice")
                yield Label("resource", classes="status-text")
                yield Input(id="resource", placeholder="e.g. report")
                yield Label("action", classes="status-text")
                yield Input(id="action", placeholder="e.g. read")
                yield Button("Build request (ctrl+b)", id="build-button")
                yield Label("", id="request-status", classes="status-text")
            with TitledPanel("Preview", id="builder-preview"):
                yield Static(
                    "No request built yet.\n"
                    "Fill the three attributes and press ctrl+b.",
                    id="request-preview",
                )
        yield Footer()

    def on_screen_resume(self) -> None:
        pending = self.app.services.evaluation.pending_request
        if pending is not None:
            for field in ("subject", "resource", "action"):
                query = self.query_one(f"#{field}", Input)
                if not query.value:
                    query.value = getattr(pending, field)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "build-button":
            self.action_build_request()

    def action_build_request(self) -> None:
        status = self.query_one("#request-status", Label)
        preview = self.query_one("#request-preview", Static)
        values = {
            field: self.query_one(f"#{field}", Input).value
            for field in ("subject", "resource", "action")
        }

        try:
            request = AccessRequest.from_dict(values)
        except RequestValidationError as exc:
            status.update(f"Invalid request: {escape(str(exc))}")
            status.add_class("error-text")
            return

        source = json.dumps(request.to_dict(), ensure_ascii=False)
        self.app.services.evaluation.set_pending_request(request, source)
        preview.update(
            "Validated request:\n\n" + escape(json.dumps(request.to_dict(), indent=2))
        )
        status.remove_class("error-text")
        status.update("Request ready. Press e to evaluate it.")

    def action_blur(self) -> None:
        self.set_focus(None)
