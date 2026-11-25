"""Presentation-layer services for the AuthRes TUI.

Services are plain Python with no Textual imports and no authorization
logic of their own. They adapt the existing public core APIs
(``PolicySet``, ``AccessRequest``, ``ReferenceEngine``, ``EvaluationResult``
and the AuthRes error types) for display, and they record session
evaluations. All authorization behavior comes from the core reference
engine; nothing here duplicates or modifies it.
"""

from authres.tui.services.evaluation_service import (
    EvaluationRecord,
    EvaluationService,
)
from authres.tui.services.policy_service import (
    PolicyFileInfo,
    PolicyLoadResult,
    PolicyService,
)
from authres.tui.services.settings import (
    DEFAULT_SETTINGS_VERSION,
    TuiSettings,
    SettingsStore,
    default_settings,
)

__all__ = [
    "DEFAULT_SETTINGS_VERSION",
    "EvaluationRecord",
    "EvaluationService",
    "PolicyFileInfo",
    "PolicyLoadResult",
    "PolicyService",
    "SettingsStore",
    "TuiSettings",
    "default_settings",
]
