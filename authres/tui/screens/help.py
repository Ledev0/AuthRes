"""Help modal: keyboard shortcuts reference."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from authres.tui.widgets import TitledPanel

_HELP_TEXT = """\
Global navigation
  d   Dashboard
  p   Policy Explorer
  b   Request Builder
  e   Evaluation
  v   Results
  s   Settings
  ?   Toggle this help
  q   Quit

Note: while a text field is focused, letters are typed into the field.
Press escape (or tab) to leave the field first.

Policy Explorer
  r        Refresh the policy file list
  up/down  Move through files (selection loads the preview)
  enter    Load the selected file

Request Builder
  ctrl+b   Validate and build the request

Evaluation
  up/down  Choose the policy set
  r        Run the evaluation with the pending request

Results
  up/down  Move through session evaluations
  x        Export the selected evaluation as JSON
  enter    Show details of the selected row

Settings
  s        Save settings
"""


class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close_help", "Close"),
        Binding("q", "close_help", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TitledPanel("Keyboard shortcuts"):
            yield Static(_HELP_TEXT, id="help-text")
        yield Footer()

    def action_close_help(self) -> None:
        self.app.pop_screen()
