"""Exception types used by AuthRes.

Validation failures are deliberately represented as errors rather than as
authorization decisions. Malformed input must never silently become a DENY
or ALLOW result.
"""

from __future__ import annotations


class AuthResError(ValueError):
    """Base class for validation errors raised by AuthRes."""


class PolicyValidationError(AuthResError):
    """Raised when policy data is structurally or semantically invalid."""


class RequestValidationError(AuthResError):
    """Raised when access request data is structurally or semantically invalid."""
