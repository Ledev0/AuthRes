"""Import-safety tests: importing the TUI must never start a UI session."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_importing_tui_modules_has_no_side_effects() -> None:
    code = (
        "import authres.tui, authres.tui.app, authres.tui.screens, "
        "authres.tui.widgets, authres.tui.services, authres.tui.__main__; "
        "print('import-ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout


def test_package_exports_entry_points_without_running_them() -> None:
    code = (
        "import authres.tui as t; "
        "assert callable(t.run); "
        "assert hasattr(t.AuthResApp, 'run'); "
        "app = t.AuthResApp(); "
        "assert app._screen_stack == [], 'UI started at construction'; "
        "print('exports-ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "exports-ok" in result.stdout


def test_ui_layers_never_import_reference_engine_directly() -> None:
    """Screens and widgets are presentation only; services adapt the core.

    Only ``authres/tui/services`` may import the reference engine, so no
    authorization logic can creep into UI components.
    """
    import ast

    tui_root = PROJECT_ROOT / "authres" / "tui"
    ui_layers = [tui_root / "screens", tui_root / "widgets", tui_root / "app.py"]

    offenders: list[str] = []
    for layer in ui_layers:
        paths = [layer] if layer.is_file() else sorted(layer.glob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                for module in modules:
                    if module.startswith("authres.core.reference_engine"):
                        offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {module}")

    assert not offenders, (
        f"UI layers must not import the reference engine directly: {offenders}"
    )


def test_services_may_import_reference_engine() -> None:
    """Sanity: the boundary above must not be accidentally over-broad."""
    import ast

    services_dir = PROJECT_ROOT / "authres" / "tui" / "services"
    found = any(
        "authres.core.reference_engine" in path.read_text(encoding="utf-8")
        for path in services_dir.glob("*.py")
    )
    assert found, "evaluation service should use the existing reference engine"
