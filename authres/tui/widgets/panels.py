"""Titled bordered panel container used across TUI screens."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Label


class TitledPanel(Vertical):
    """A bordered panel with a small title line at the top.

    Used with Textual's ``with`` composition:

        with TitledPanel("Preview"):
            yield Static(...)
    """

    DEFAULT_CSS = """
    TitledPanel {
        border: round $panel;
        padding: 0 1;
        width: 1fr;
        height: 1fr;
    }
    TitledPanel .panel-title {
        color: $text-muted;
        text-style: bold;
        height: 1;
    }
    """

    def __init__(
        self,
        title: str,
        *,
        id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, name=name)
        self._panel_title = title

    def compose(self):
        yield Label(self._panel_title, classes="panel-title")
