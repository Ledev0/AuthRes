"""Shared helpers for TUI tests.

Provides headless app sessions via Textual's ``run_test`` pilot and a
services factory that isolates settings from any real user configuration.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Callable

from authres.tui.app import AuthResApp, TuiServices
from authres.tui.services.evaluation_service import EvaluationService
from authres.tui.services.policy_service import PolicyService
from authres.tui.services.settings import SettingsStore, default_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "policies" / "examples"


def make_services(
    tmp_path: Path,
    *,
    policy_dir: Path | str | None = None,
    export_dir: Path | str | None = None,
) -> TuiServices:
    """Build TUI services with a settings file isolated inside tmp_path."""
    store = SettingsStore(tmp_path / "tui_settings.json")
    settings = default_settings()
    if policy_dir is not None:
        settings = replace(settings, policy_dir=Path(policy_dir))
    if export_dir is not None:
        settings = replace(settings, export_dir=Path(export_dir))
    return TuiServices(
        settings_store=store,
        settings=settings,
        policy=PolicyService(),
        evaluation=EvaluationService(),
    )


def make_app(
    tmp_path: Path,
    *,
    policy_dir: Path | str | None = None,
    export_dir: Path | str | None = None,
) -> AuthResApp:
    """Create a fresh app with isolated services (never a user profile)."""
    app = AuthResApp()
    app.services = make_services(
        tmp_path, policy_dir=policy_dir, export_dir=export_dir
    )
    return app


def run_pilot(
    app: AuthResApp,
    body: Callable[..., object],
    *,
    size: tuple[int, int] = (120, 44),
) -> None:
    """Run ``async def body(pilot, app)`` inside a headless app session."""

    async def runner() -> None:
        async with app.run_test(size=size) as pilot:
            await body(pilot, app)

    asyncio.run(runner())
