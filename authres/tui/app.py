"""AuthRes TUI application.

Presentation layer only. All authorization behavior is provided by the
existing core reference engine; screens communicate through
``authres.tui.services`` adapters. Importing this package never starts the
UI: run it explicitly with ``python -m authres.tui``.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import App
from textual.binding import Binding
from textual.screen import Screen

from authres.tui.screens.dashboard import DashboardScreen
from authres.tui.screens.evaluation import EvaluationScreen
from authres.tui.screens.help import HelpScreen
from authres.tui.screens.policy_explorer import PolicyExplorerScreen
from authres.tui.screens.request_builder import RequestBuilderScreen
from authres.tui.screens.results import ResultsScreen
from authres.tui.screens.settings import SettingsScreen
from authres.tui.services.evaluation_service import EvaluationService
from authres.tui.services.policy_service import PolicyService
from authres.tui.services.settings import SettingsStore, TuiSettings, default_settings


@dataclass
class TuiServices:
    """Container for the TUI's presentation services."""

    settings_store: SettingsStore
    settings: TuiSettings
    policy: PolicyService
    evaluation: EvaluationService


def _ensure_switchable(screen: Screen) -> None:
    """Workaround for a Textual 8.2.8 ``switch_screen`` requirement.

    Exact behavior (verified against Textual 8.2.8):

    - ``App.switch_screen`` (app.py ~3015) replaces the top of the screen
      stack and calls ``top_screen._pop_result_callback()`` (app.py ~3020)
      **unconditionally**. That method pops from
      ``Screen._result_callbacks`` without checking emptiness, so an
      outgoing screen with no callbacks raises ``IndexError: pop from
      empty list``.
    - ``switch_screen`` then pushes one placeholder callback onto the
      *incoming* screen. Therefore every screen that entered the stack via
      ``switch_screen`` sits at exactly one callback while current, and 0
      after being popped. The only screen that enters the stack any other
      way is the initial default screen (``get_default_screen``), which
      starts at 0 callbacks.

    This helper adds a no-op placeholder only when the outgoing screen has
    none, restoring the invariant ``push_screen`` normally maintains. It
    touches no Textual internals beyond the documented callback list, is
    idempotent, and can be deleted if a future Textual release guards the
    pop. Regression tests in ``tests/test_tui_app.py`` pin this behavior.
    """
    if not screen._result_callbacks:
        screen._result_callbacks.append(lambda _result: None)


def build_default_services() -> TuiServices:
    """Build services from the default settings location."""
    settings_store = SettingsStore()
    settings = settings_store.load()
    return TuiServices(
        settings_store=settings_store,
        settings=settings,
        policy=PolicyService(),
        evaluation=EvaluationService(),
    )


class AuthResApp(App):
    """Interactive interface over the AuthRes reference engine."""

    TITLE = "AuthRes"
    SUB_TITLE = "Phase 1 · reference engine"

    CSS = """
    #content {
        height: 1fr;
    }
    #dash-nav {
        width: 36;
    }
    #dash-project, #dash-engine, #dash-latest {
        height: 1fr;
    }
    #explorer-files {
        width: 40%;
    }
    #explorer-preview {
        width: 1fr;
    }
    #builder-form {
        width: 44%;
        height: auto;
    }
    #builder-preview {
        width: 1fr;
    }
    #eval-files-panel {
        width: 40%;
    }
    #eval-right {
        width: 1fr;
    }
    #eval-request-panel {
        height: 40%;
    }
    #results-list-panel {
        height: 45%;
    }
    #results-detail-panel {
        height: 1fr;
    }
    #settings-paths, #settings-display {
        height: auto;
    }
    .error-text {
        color: $error;
        text-style: bold;
    }
    .status-text {
        color: $text-muted;
    }
    .hint-text {
        color: $accent;
        padding: 0 1;
        height: 1;
    }
    ListView {
        border: round $panel;
        height: 1fr;
    }
    ListView:focus {
        border: round $accent;
    }
    DataTable {
        border: round $panel;
    }
    DataTable:focus {
        border: round $accent;
    }
    Input {
        border: round $panel;
    }
    Input:focus {
        border: round $accent;
    }
    Button:focus {
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding("d", "dashboard", "Dashboard"),
        Binding("p", "policy_explorer", "Policies"),
        Binding("b", "request_builder", "Request"),
        Binding("e", "evaluation", "Evaluate"),
        Binding("v", "results", "Results"),
        Binding("s", "settings", "Settings"),
        Binding("question_mark", "help", "Help", priority=True),
        Binding("q", "quit_app", "Quit"),
    ]

    SCREENS = {
        "dashboard": DashboardScreen,
        "policy_explorer": PolicyExplorerScreen,
        "request_builder": RequestBuilderScreen,
        "evaluation": EvaluationScreen,
        "results": ResultsScreen,
        "settings": SettingsScreen,
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._services: TuiServices | None = None
        self.policy_selection = None  # PolicyLoadResult | None
        self._screen_cache: dict[str, Screen] = {}

    @property
    def services(self) -> TuiServices:
        if self._services is None:
            self._services = build_default_services()
        return self._services

    @services.setter
    def services(self, value: TuiServices) -> None:
        self._services = value

    def get_default_screen(self) -> Screen:
        """Start the app on the Dashboard instead of a placeholder screen."""
        dashboard = DashboardScreen()
        self._screen_cache["dashboard"] = dashboard
        return dashboard

    def navigate(self, screen_name: str) -> None:
        """Single navigation entry point for all named screens.

        Every screen switch in the TUI must go through this method.

        Textual 8.2.8 behavior this method works around (see
        ``_ensure_switchable``): ``App.switch_screen`` replaces the top of
        the screen stack and pops one result callback from the outgoing
        screen unconditionally. Screens that never entered the stack through
        ``push_screen``/``switch_screen`` — the initial default screen —
        have an empty callback list, so a raw ``switch_screen`` from the
        Dashboard raises ``IndexError: pop from empty list``.

        Additional guarantees provided here:

        - unknown screen names are rejected loudly (``ValueError``);
        - navigating to the currently active screen is a no-op (raw
          name-based ``switch_screen`` would first *instantiate a duplicate*
          of the active screen before its own equality check);
        - one instance per screen is created and reused, so repeated
          navigation cannot accumulate duplicate instances and in-screen
          state (selections, scroll) survives;
        - if the Help modal is open, it is dismissed first, then the no-op
          check is re-evaluated against the revealed screen.
        """
        if screen_name not in self.SCREENS:
            raise ValueError(f"unknown screen name: {screen_name!r}")
        if not self.screen_stack:
            return  # nothing to navigate from or to (defensive)

        if isinstance(self.screen, HelpScreen):
            self.pop_screen()

        target_class = self.SCREENS[screen_name]
        if isinstance(self.screen, target_class):
            return  # already active: no-op

        screen = self._screen_cache.get(screen_name)
        if screen is None:
            screen = target_class()
            self._screen_cache[screen_name] = screen

        _ensure_switchable(self.screen)
        self.switch_screen(screen)

    def action_dashboard(self) -> None:
        self.navigate("dashboard")

    def action_policy_explorer(self) -> None:
        self.navigate("policy_explorer")

    def action_request_builder(self) -> None:
        self.navigate("request_builder")

    def action_evaluation(self) -> None:
        self.navigate("evaluation")

    def action_results(self) -> None:
        self.navigate("results")

    def action_settings(self) -> None:
        self.navigate("settings")

    def action_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        self.exit()


def run() -> None:
    """Run the TUI (entry point for ``python -m authres.tui``)."""
    AuthResApp().run()
