"""Reusable display widgets for the AuthRes TUI.

Widgets are presentation only. They format values produced by the core
models and services and never compute authorization outcomes.
"""

from authres.tui.widgets.panels import TitledPanel
from authres.tui.widgets.result_card import ResultCard

__all__ = ["ResultCard", "TitledPanel"]
