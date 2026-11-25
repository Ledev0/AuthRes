"""Tests for the neutral engine contract types and independence boundaries.

These tests validate the ``authres.engines`` contract scaffold itself. They do
not validate any external engine, because no adapter exists yet.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from authres.core.models import Decision
from authres.engines import EngineAdapter, EngineOutcome, EngineStatus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINES_DIR = PROJECT_ROOT / "authres" / "engines"
REFERENCE_ENGINE_PATH = PROJECT_ROOT / "authres" / "core" / "reference_engine.py"


def make_outcome(**overrides: object) -> EngineOutcome:
    values: dict[str, object] = {
        "engine_id": "example-engine",
        "engine_version": "1.0.0",
        "status": EngineStatus.DECIDED,
        "decision": Decision.ALLOW,
        "detail": None,
    }
    values.update(overrides)
    return EngineOutcome(**values)  # type: ignore[arg-type]


class TestEngineStatus:
    def test_status_values(self) -> None:
        assert EngineStatus.DECIDED.value == "DECIDED"
        assert EngineStatus.NOT_APPLICABLE.value == "NOT_APPLICABLE"
        assert EngineStatus.INDETERMINATE.value == "INDETERMINATE"
        assert EngineStatus.ERROR.value == "ERROR"
        assert EngineStatus.TIMEOUT.value == "TIMEOUT"

    def test_only_five_statuses_exist(self) -> None:
        assert len(EngineStatus) == 5


class TestEngineOutcomeInvariants:
    def test_decided_outcome_accepts_allow_and_deny(self) -> None:
        allow = make_outcome(decision=Decision.ALLOW)
        deny = make_outcome(decision=Decision.DENY)

        assert allow.has_decision is True
        assert deny.has_decision is True

    def test_decided_requires_a_decision(self) -> None:
        with pytest.raises(ValueError, match="DECIDED requires"):
            make_outcome(decision=None)

    def test_decided_rejects_non_decision_value(self) -> None:
        with pytest.raises(ValueError, match="DECIDED requires"):
            make_outcome(decision="ALLOW")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "status",
        [
            EngineStatus.NOT_APPLICABLE,
            EngineStatus.INDETERMINATE,
            EngineStatus.ERROR,
            EngineStatus.TIMEOUT,
        ],
    )
    def test_non_decided_cannot_carry_decision(self, status: EngineStatus) -> None:
        kwargs: dict[str, object] = {"status": status, "decision": Decision.ALLOW}
        if status in (EngineStatus.ERROR, EngineStatus.TIMEOUT):
            kwargs["detail"] = "failure detail"

        with pytest.raises(ValueError, match="only DECIDED outcomes may carry"):
            make_outcome(**kwargs)

    @pytest.mark.parametrize(
        "status",
        [EngineStatus.NOT_APPLICABLE, EngineStatus.INDETERMINATE],
    )
    def test_non_decided_without_decision_is_valid(
        self, status: EngineStatus
    ) -> None:
        outcome = make_outcome(
            status=status, decision=None, detail="engine reported the state"
        )

        assert outcome.has_decision is False
        assert outcome.decision is None
        assert outcome.detail is not None

    def test_error_requires_detail(self) -> None:
        with pytest.raises(ValueError, match="ERROR requires a detail"):
            make_outcome(
                status=EngineStatus.ERROR,
                decision=None,
                detail=None,
            )

    def test_timeout_requires_detail(self) -> None:
        with pytest.raises(ValueError, match="TIMEOUT requires a detail"):
            make_outcome(
                status=EngineStatus.TIMEOUT,
                decision=None,
                detail="   ",
            )

    def test_not_applicable_allows_detail_but_does_not_require_it(self) -> None:
        outcome = make_outcome(
            status=EngineStatus.NOT_APPLICABLE, decision=None, detail=None
        )

        assert outcome.has_decision is False

    @pytest.mark.parametrize("field", ["engine_id", "engine_version"])
    def test_rejects_empty_identity_fields(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            make_outcome(**{field: ""})

    @pytest.mark.parametrize("field", ["engine_id", "engine_version"])
    def test_rejects_whitespace_identity_fields(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            make_outcome(**{field: "   "})

    @pytest.mark.parametrize("field", ["engine_id", "engine_version"])
    def test_rejects_non_string_identity_fields(self, field: str) -> None:
        with pytest.raises(TypeError, match=field):
            make_outcome(**{field: 7})

    def test_rejects_non_string_detail(self) -> None:
        with pytest.raises(TypeError, match="detail"):
            make_outcome(detail=42)

    def test_rejects_non_status(self) -> None:
        with pytest.raises(TypeError, match="status"):
            make_outcome(status="DECIDED")  # type: ignore[arg-type]


class TestEngineOutcomeSerialization:
    def test_to_dict_decided(self) -> None:
        outcome = make_outcome(
            engine_id="engine-a", engine_version="2.1", decision=Decision.DENY
        )

        assert outcome.to_dict() == {
            "engine_id": "engine-a",
            "engine_version": "2.1",
            "status": "DECIDED",
            "decision": "DENY",
            "detail": None,
        }

    def test_to_dict_error_with_detail(self) -> None:
        outcome = make_outcome(
            status=EngineStatus.ERROR,
            decision=None,
            detail="engine process crashed",
        )

        assert outcome.to_dict() == {
            "engine_id": "example-engine",
            "engine_version": "1.0.0",
            "status": "ERROR",
            "decision": None,
            "detail": "engine process crashed",
        }

    def test_to_dict_is_json_compatible(self) -> None:
        import json

        outcome = make_outcome(
            status=EngineStatus.INDETERMINATE,
            decision=None,
            detail="engine returned an unexpected result",
        )

        assert json.loads(json.dumps(outcome.to_dict())) == outcome.to_dict()


class TestEngineAdapterProtocol:
    def test_protocol_defines_the_three_stages(self) -> None:
        # Python 3.11 has no Protocol.__protocol_attrs__, so inspect the class
        # namespace directly. The explicit members are declared in the body.
        names = {
            name for name in EngineAdapter.__dict__ if not name.startswith("_")
        }

        assert {"engine_id", "engine_version", "compile", "execute", "normalize"} <= names


def _collect_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class TestIndependenceBoundaries:
    def test_engines_package_files_exist(self) -> None:
        assert ENGINES_DIR.is_dir()
        source_files = sorted(ENGINES_DIR.glob("*.py"))
        assert source_files, "authres/engines must contain source files"

    def test_engines_never_imports_reference_engine(self) -> None:
        for path in ENGINES_DIR.glob("*.py"):
            imports = _collect_imports(path)
            prohibited = {
                module for module in imports
                if module.startswith("authres.core.reference_engine")
            }
            assert not prohibited, (
                f"{path.name} imports reference engine logic {prohibited}; "
                "adapters must not silently reuse reference decision logic"
            )

    def test_engines_depends_only_on_core_models_and_policy(self) -> None:
        for path in ENGINES_DIR.glob("*.py"):
            imports = _collect_imports(path)
            internal = {
                module for module in imports if module == "authres" or module.startswith(
                    ("authres.",)
                )
            }
            allowed_prefixes = ("authres.core.models", "authres.core.policy", "authres.engines")
            assert all(module.startswith(allowed_prefixes) for module in internal), (
                f"{path.name} imports {[m for m in internal if not m.startswith(allowed_prefixes)]}; "
                "the engine contract may depend only on authres.core.models, "
                "authres.core.policy, and its own package"
            )

    def test_reference_engine_does_not_import_engines_package(self) -> None:
        imports = _collect_imports(REFERENCE_ENGINE_PATH)
        prohibited = {
            module for module in imports
            if module == "authres.engines" or module.startswith("authres.engines.")
        }
        assert not prohibited, (
            "reference engine must stay independent of the adapters package"
        )
