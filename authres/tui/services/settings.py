"""Settings persistence for the AuthRes TUI.

Settings are a small, explicit JSON document: two paths and one display
preference. Nothing experimental depends on these values; they only steer
where the TUI looks for policy files and where it writes exports.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS_VERSION = 1

SETTINGS_ENV_VAR = "AUTHRES_TUI_SETTINGS"


def _project_root() -> Path:
    """Locate the AuthRes project root from this file's location."""
    # services/settings.py -> tui -> authres -> project root
    return Path(__file__).resolve().parents[3]


def default_settings_path() -> Path:
    """Default settings file location (overridable for tests)."""
    override = os.environ.get(SETTINGS_ENV_VAR)
    if override:
        return Path(override)
    return Path.home() / ".authres" / "tui_settings.json"


def default_settings() -> TuiSettings:
    """Factory defaults derived from the repository layout."""
    root = _project_root()
    return TuiSettings(
        policy_dir=root / "policies" / "examples",
        export_dir=root / "results",
        show_matched_trace=True,
    )


@dataclass(frozen=True)
class TuiSettings:
    """User-adjustable TUI preferences."""

    policy_dir: Path
    export_dir: Path
    show_matched_trace: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings_version": DEFAULT_SETTINGS_VERSION,
            "policy_dir": str(self.policy_dir),
            "export_dir": str(self.export_dir),
            "show_matched_trace": self.show_matched_trace,
        }


class SettingsStore:
    """Load and save :class:`TuiSettings` as strict JSON on disk.

    A missing or malformed settings file is never fatal: the store falls
    back to defaults and records the reason in ``load_error`` so the UI can
    surface it instead of guessing.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else default_settings_path()
        self.load_error: str | None = None

    def load(self) -> TuiSettings:
        self.load_error = None
        defaults = default_settings()

        if not self.path.exists():
            return defaults

        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.load_error = f"cannot read settings file {self.path}: {exc}"
            return defaults

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            self.load_error = (
                f"settings file {self.path} is not valid JSON: {exc}"
            )
            return defaults

        if not isinstance(data, dict):
            self.load_error = (
                f"settings file {self.path} must contain a JSON object"
            )
            return defaults

        policy_dir = _parse_path(data.get("policy_dir"), defaults.policy_dir)
        export_dir = _parse_path(data.get("export_dir"), defaults.export_dir)
        show_trace = data.get("show_matched_trace", defaults.show_matched_trace)
        if not isinstance(show_trace, bool):
            show_trace = defaults.show_matched_trace

        return TuiSettings(
            policy_dir=policy_dir,
            export_dir=export_dir,
            show_matched_trace=show_trace,
        )

    def save(self, settings: TuiSettings) -> str | None:
        """Write settings to disk. Returns an error message, or None."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            return f"cannot save settings to {self.path}: {exc}"
        return None


def _parse_path(value: object, fallback: Path) -> Path:
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser()
    return fallback
