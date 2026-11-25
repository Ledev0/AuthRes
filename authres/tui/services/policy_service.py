"""Policy file listing and validation for the AuthRes TUI.

This service only adapts ``PolicySet.from_file`` / ``from_json`` for display.
It contains no parsing or authorization logic; all validation comes from the
existing core loader and its documented error messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from authres.core.policy import PolicySet


@dataclass(frozen=True)
class PolicyFileInfo:
    """A discoverable policy JSON file."""

    path: Path
    name: str


@dataclass(frozen=True)
class PolicyLoadResult:
    """Outcome of loading one policy file for display."""

    path: Path
    policy_set: PolicySet | None
    error: str | None
    raw_text: str | None

    @property
    def is_valid(self) -> bool:
        return self.policy_set is not None and self.error is None


class PolicyService:
    """List and validate policy JSON files using the core loader."""

    @staticmethod
    def list_policy_files(directory: Path | str | None) -> list[PolicyFileInfo]:
        """Return ``*.json`` files in a directory, sorted by name.

        A missing or unreadable directory yields an empty list; callers show
        their own empty state.
        """
        if directory is None:
            return []
        base = Path(directory).expanduser()
        try:
            entries = sorted(
                (
                    item
                    for item in base.iterdir()
                    if item.is_file() and item.suffix == ".json"
                ),
                key=lambda item: item.name,
            )
        except OSError:
            return []
        return [
            PolicyFileInfo(path=item, name=item.name) for item in entries
        ]

    @staticmethod
    def load(path: Path | str | None) -> PolicyLoadResult:
        """Load and validate one policy file via ``PolicySet.from_file``."""
        policy_path = Path(path).expanduser() if path is not None else Path()
        raw_text: str | None = None
        try:
            raw_text = policy_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return PolicyLoadResult(
                path=policy_path,
                policy_set=None,
                error=f"cannot read policy file {policy_path}: {exc}",
                raw_text=None,
            )

        try:
            policy_set = PolicySet.from_file(policy_path)
        except Exception as exc:  # core loader raises AuthResError subclasses
            return PolicyLoadResult(
                path=policy_path,
                policy_set=None,
                error=f"{exc}",
                raw_text=raw_text,
            )

        return PolicyLoadResult(
            path=policy_path,
            policy_set=policy_set,
            error=None,
            raw_text=raw_text,
        )
