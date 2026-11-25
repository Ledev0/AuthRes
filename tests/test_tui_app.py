"""Pilot-driven tests for TUI navigation and app-level behavior."""

from __future__ import annotations

import pytest

from authres.tui.app import AuthResApp
from authres.tui.screens.dashboard import DashboardScreen
from authres.tui.screens.evaluation import EvaluationScreen
from authres.tui.screens.help import HelpScreen
from authres.tui.screens.policy_explorer import PolicyExplorerScreen
from authres.tui.screens.request_builder import RequestBuilderScreen
from authres.tui.screens.results import ResultsScreen
from authres.tui.screens.settings import SettingsScreen
from tui_support import EXAMPLES_DIR, make_app, run_pilot


def test_app_starts_on_dashboard(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        assert isinstance(app.screen, DashboardScreen)
        nav = app.screen.query_one("#dashboard-nav")
        assert len(nav.children) == 7

    run_pilot(app, body)


@pytest.mark.parametrize(
    ("key", "screen_type"),
    [
        ("p", PolicyExplorerScreen),
        ("b", RequestBuilderScreen),
        ("e", EvaluationScreen),
        ("v", ResultsScreen),
        ("s", SettingsScreen),
        ("d", DashboardScreen),
    ],
)
def test_navigation_keys_switch_screens(tmp_path, key, screen_type) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("escape")  # leave any auto-focused input
        await pilot.press(key)
        await pilot.pause()
        assert isinstance(app.screen, screen_type), type(app.screen).__name__

    run_pilot(app, body)


def test_full_navigation_round_trip(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        expected = [
            ("p", PolicyExplorerScreen),
            ("b", RequestBuilderScreen),
            ("e", EvaluationScreen),
            ("v", ResultsScreen),
            ("s", SettingsScreen),
            ("d", DashboardScreen),
        ]
        for key, screen_type in expected:
            await pilot.press("escape")
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, screen_type)

    run_pilot(app, body)


def test_help_opens_with_question_mark_and_closes_with_escape(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        assert "d   Dashboard" in str(app.screen.query_one("#help-text").render())

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

    run_pilot(app, body)


def test_question_mark_toggles_help_off(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("?")
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

    run_pilot(app, body)


def test_quit_binding_exits_cleanly(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("escape")
        await pilot.press("q")

    run_pilot(app, body)

    assert app.return_code == 0


def test_dashboard_shows_latest_evaluation(tmp_path) -> None:
    app = make_app(tmp_path)
    from authres.core.models import AccessRequest
    from authres.core.policy import PolicySet

    conflict_path = EXAMPLES_DIR / "conflict.json"
    policy_set = PolicySet.from_file(conflict_path)
    app.services.evaluation.evaluate(
        policy_set=policy_set,
        request=AccessRequest("alice", "report", "read"),
        policy_path=str(conflict_path),
    )

    async def body(pilot, app) -> None:
        card = app.screen.query_one("#dashboard-latest")
        text = str(card.render())
        assert "Decision: DENY" in text
        assert "DENY_OVERRIDE" in text

    run_pilot(app, body)


# --- Navigation regression tests (screen-stack safety) ----------------------


def test_dashboard_to_policy_explorer_to_dashboard_round_trip(tmp_path) -> None:
    """The reported crash flow: nav-list selection, back, re-select."""
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("down", "enter")  # select Policy Explorer in nav
        await pilot.pause()
        assert isinstance(app.screen, PolicyExplorerScreen)

        await pilot.press("escape", "d")  # back to Dashboard
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

        await pilot.press("escape", "up", "enter")  # select Dashboard again
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)  # was IndexError before

        await pilot.press("enter")  # select the active screen once more
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

    run_pilot(app, body)


def test_nav_selection_of_active_screen_is_noop(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.pause()
        dashboard = app.screen
        await pilot.press("enter")  # Dashboard item is preselected
        await pilot.pause()

        assert app.screen is dashboard

    run_pilot(app, body)


def test_repeated_navigation_between_all_screens(tmp_path) -> None:
    app = make_app(tmp_path)
    cycle = [
        ("p", PolicyExplorerScreen),
        ("b", RequestBuilderScreen),
        ("e", EvaluationScreen),
        ("v", ResultsScreen),
        ("s", SettingsScreen),
        ("d", DashboardScreen),
    ]

    async def body(pilot, app) -> None:
        for _round in range(3):
            for key, screen_type in cycle:
                await pilot.press("escape")
                await pilot.press(key)
                await pilot.pause()
                assert isinstance(app.screen, screen_type), (
                    f"round {_round}, key {key}: {type(app.screen).__name__}"
                )

        # Callback stacks stay balanced after heavy navigation.
        for screen in app._screen_cache.values():
            assert len(screen._result_callbacks) <= 1

    run_pilot(app, body)
    assert app._exception is None


def test_screen_instances_are_reused_not_duplicated(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("escape", "p")
        await pilot.pause()
        explorer_first = app.screen

        await pilot.press("escape", "d")
        await pilot.pause()
        await pilot.press("escape", "p")
        await pilot.pause()

        assert app.screen is explorer_first
        assert len([s for s in app._screen_cache.values()
                    if isinstance(s, PolicyExplorerScreen)]) == 1

    run_pilot(app, body)


@pytest.mark.parametrize("start_key", ["p", "b", "e", "v", "s"])
def test_help_opens_and_closes_from_every_screen(tmp_path, start_key) -> None:
    from authres.tui.screens.help import HelpScreen

    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("escape")
        await pilot.press(start_key)
        await pilot.pause()
        origin = app.screen

        # Escape first: some screens focus an Input, which would otherwise
        # consume "?" as text instead of invoking the priority help binding.
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is origin

    run_pilot(app, body)


def test_navigation_after_returning_from_results(tmp_path) -> None:
    from authres.core.models import AccessRequest
    from authres.core.policy import PolicySet

    app = make_app(tmp_path)
    conflict_path = EXAMPLES_DIR / "conflict.json"
    app.services.evaluation.evaluate(
        policy_set=PolicySet.from_file(conflict_path),
        request=AccessRequest("alice", "report", "read"),
        policy_path=str(conflict_path),
    )

    async def body(pilot, app) -> None:
        await pilot.press("escape", "v")
        await pilot.pause()
        assert isinstance(app.screen, ResultsScreen)
        assert app.screen.query_one("#results-table").row_count == 1

        await pilot.press("escape", "d")
        await pilot.pause()
        await pilot.press("escape", "v")
        await pilot.pause()

        assert isinstance(app.screen, ResultsScreen)
        assert app.screen.query_one("#results-table").row_count == 1

        await pilot.press("escape", "d")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

    run_pilot(app, body)
    assert app._exception is None


def test_help_modal_dismissal_reveals_previous_screen(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.press("escape", "e")
        await pilot.pause()
        await pilot.press("escape", "d")
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        # Modal help blocks non-priority app bindings, so navigation while
        # help is open is exercised through the centralized navigation API.
        # It must dismiss the modal and then switch to the requested screen.
        app.navigate("policy_explorer")
        await pilot.pause()
        assert isinstance(app.screen, PolicyExplorerScreen)

    run_pilot(app, body)
    assert app._exception is None


def test_unknown_screen_name_is_rejected_loudly(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        with pytest.raises(ValueError, match="unknown screen name"):
            app.navigate("does-not-exist")

    run_pilot(app, body)


def test_no_callback_stack_corruption_after_mixed_navigation(tmp_path) -> None:
    """Mixes keyboard nav, nav-list selection, and help toggles."""
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        await pilot.pause()
        for key in ("p", "b", "e", "v", "s"):
            await pilot.press("escape")
            await pilot.press(key)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("?")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

        await pilot.press("escape", "d")
        await pilot.pause()
        for _ in range(3):
            await pilot.press("down", "enter")  # nav-list driven switches
            await pilot.pause()

        for screen in app._screen_cache.values():
            assert len(screen._result_callbacks) in (0, 1)

    run_pilot(app, body)
    assert app._exception is None


def test_dashboard_empty_state_before_any_evaluation(tmp_path) -> None:
    app = make_app(tmp_path)

    async def body(pilot, app) -> None:
        card = app.screen.query_one("#dashboard-latest")
        assert "No evaluation yet." in str(card.render())

    run_pilot(app, body)
