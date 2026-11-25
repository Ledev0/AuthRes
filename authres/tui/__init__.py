"""AuthRes TUI package.

Importing this package has no side effects and never starts a UI loop.
Run the interface explicitly with ``python -m authres.tui`` or by calling
:func:`run` / :class:`AuthResApp` from ``authres.tui.app``.
"""

from authres.tui.app import AuthResApp, TuiServices, build_default_services, run

__all__ = ["AuthResApp", "TuiServices", "build_default_services", "run"]
