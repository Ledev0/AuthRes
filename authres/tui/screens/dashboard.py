"""Dashboard screen: project status, engine status, latest result, navigation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from authres.tui.widgets import ResultCard, TitledPanel

_PROJECT_STATUS = (
    "Phase 1 prototype. Reference engine only.\n"
    "No external engines, comparison, or experimental results.\n"
    "No engine compatibility is established or claimed."
)

_ENGINE_STATUS = (
    "Engine: authres.core.reference_engine.ReferenceEngine\n"
    "Semantics: authres-policy-v1 (docs/policy-semantics.md)\n"
    "Deterministic · exact matching · DENY overrides ALLOW · default DENY\n"
    "Validation status: self-consistency + hand-authored conformance\n"
    "(docs/semantic-validation.md). Not independently validated."
)

_NAVIGATION = [
    ("dashboard", "Dashboard", "d"),
    ("policy_explorer", "Policy Explorer", "p"),
    ("request_builder", "Request Builder", "b"),
    ("evaluation", "Evaluation", "e"),
    ("results", "Results", "v"),
    ("settings", "Settings", "s"),
    ("help", "Help", "?"),
]


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("escape", "blur", "Unfocus input", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TitledPanel("Navigation", id="dash-nav"):
            yield ListView(
                *(
                    ListItem(Label(f"{label}  ({key})"), name=name)
                    for name, label, key in _NAVIGATION
                ),
                id="dashboard-nav",
            )
        with TitledPanel("Project status", id="dash-project"):
            yield Static(_PROJECT_STATUS, id="dashboard-project")
        with TitledPanel("Reference engine", id="dash-engine"):
            yield Static(_ENGINE_STATUS, id="dashboard-engine")
        with TitledPanel("Latest evaluation", id="dash-latest"):
            yield ResultCard(id="dashboard-latest")
        yield Footer()

    def on_screen_resume(self) -> None:
        self.query_one("#dashboard-latest", ResultCard).set_record(
            self.app.services.evaluation.latest()
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item.name == "help":
            self.app.action_help()
            # Restore nav highlight so the selection is not stuck on Help.
            self.call_after_refresh(self._reset_nav_selection)
            return
        if item.name is not None and item.name in self.app.SCREENS:
            # All named-screen navigation must go through the app's
            # centralized navigate() (raw switch_screen crashes on screens
            # that were never pushed; see AuthResApp.navigate).
            self.app.navigate(item.name)

    def _reset_nav_selection(self) -> None:
        nav = self.query_one("#dashboard-nav", ListView)
        nav.index = 0

    def action_blur(self) -> None:
        self.set_focus(None)
