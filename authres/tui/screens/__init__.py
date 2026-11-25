"""Screens for the AuthRes TUI."""

from authres.tui.screens.dashboard import DashboardScreen
from authres.tui.screens.evaluation import EvaluationScreen
from authres.tui.screens.help import HelpScreen
from authres.tui.screens.policy_explorer import PolicyExplorerScreen
from authres.tui.screens.request_builder import RequestBuilderScreen
from authres.tui.screens.results import ResultsScreen
from authres.tui.screens.settings import SettingsScreen

__all__ = [
    "DashboardScreen",
    "EvaluationScreen",
    "HelpScreen",
    "PolicyExplorerScreen",
    "RequestBuilderScreen",
    "ResultsScreen",
    "SettingsScreen",
]
