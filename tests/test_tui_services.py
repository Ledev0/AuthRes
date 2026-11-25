"""Unit tests for the TUI services layer (no UI involved)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from authres.core.models import AccessRequest
from authres.core.policy import PolicySet
from authres.core.reference_engine import ReferenceEngine
from authres.tui.services.evaluation_service import EvaluationService
from authres.tui.services.policy_service import PolicyService
from authres.tui.services.settings import (
    SettingsStore,
    TuiSettings,
    default_settings,
)
from tui_support import PROJECT_ROOT

VALID_POLICY = {
    "version": 1,
    "policies": [
        {
            "id": "allow-alice",
            "subject": "alice",
            "resource": "report",
            "action": "read",
            "effect": "ALLOW",
        }
    ],
}


class TestSettings:
    def test_default_settings_point_at_project_directories(self) -> None:
        settings = default_settings()

        assert settings.policy_dir == PROJECT_ROOT / "policies" / "examples"
        assert settings.export_dir == PROJECT_ROOT / "results"
        assert settings.show_matched_trace is True

    def test_missing_file_returns_defaults_without_error(self, tmp_path) -> None:
        store = SettingsStore(tmp_path / "settings.json")

        loaded = store.load()

        assert loaded == default_settings()
        assert store.load_error is None

    def test_save_then_load_round_trip(self, tmp_path) -> None:
        store = SettingsStore(tmp_path / "settings.json")
        settings = TuiSettings(
            policy_dir=tmp_path / "policies",
            export_dir=tmp_path / "exports",
            show_matched_trace=False,
        )

        assert store.save(settings) is None
        loaded = store.load()

        assert loaded == settings

    def test_malformed_settings_file_falls_back_with_error(self, tmp_path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{not json", encoding="utf-8")
        store = SettingsStore(path)

        loaded = store.load()

        assert loaded == default_settings()
        assert store.load_error is not None
        assert "not valid JSON" in store.load_error

    def test_non_object_settings_file_falls_back_with_error(self, tmp_path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        store = SettingsStore(path)

        assert store.load() == default_settings()
        assert store.load_error is not None

    def test_save_reports_write_errors(self, tmp_path) -> None:
        # A file where a directory is expected makes mkdir fail.
        blocker = tmp_path / "blocker"
        blocker.write_text("x", encoding="utf-8")
        store = SettingsStore(blocker / "settings.json")

        error = store.save(default_settings())

        assert error is not None
        assert "cannot save settings" in error


class TestPolicyService:
    def test_lists_json_files_sorted_and_ignores_others(self, tmp_path) -> None:
        (tmp_path / "b.json").write_text("{}", encoding="utf-8")
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
        (tmp_path / "subdir").mkdir()

        files = PolicyService.list_policy_files(tmp_path)

        assert [info.name for info in files] == ["a.json", "b.json"]

    def test_missing_directory_yields_empty_list(self, tmp_path) -> None:
        assert PolicyService.list_policy_files(tmp_path / "nope") == []

    def test_none_directory_yields_empty_list(self) -> None:
        assert PolicyService.list_policy_files(None) == []

    def test_load_valid_file(self, tmp_path) -> None:
        path = tmp_path / "valid.json"
        path.write_text(json.dumps(VALID_POLICY), encoding="utf-8")

        result = PolicyService.load(path)

        assert result.is_valid
        assert result.error is None
        assert len(result.policy_set.policies) == 1
        assert result.policy_set.policies[0].policy_id == "allow-alice"
        assert result.raw_text is not None

    def test_load_invalid_json_reports_error_without_raising(self, tmp_path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")

        result = PolicyService.load(path)

        assert not result.is_valid
        assert result.policy_set is None
        assert result.error is not None
        assert "invalid JSON" in result.error
        assert result.raw_text == "{not json"

    def test_load_invalid_policy_document_reports_core_validation_error(
        self, tmp_path
    ) -> None:
        path = tmp_path / "incomplete.json"
        path.write_text(
            json.dumps({"version": 1, "policies": [{"subject": "alice"}]}),
            encoding="utf-8",
        )

        result = PolicyService.load(path)

        assert not result.is_valid
        assert "missing required field(s)" in result.error

    def test_load_missing_file_reports_error(self, tmp_path) -> None:
        result = PolicyService.load(tmp_path / "missing.json")

        assert not result.is_valid
        assert "cannot read policy file" in result.error


class TestEvaluationService:
    def _inputs(self) -> tuple[PolicySet, AccessRequest]:
        policy_set = PolicySet.from_json(json.dumps(VALID_POLICY))
        request = AccessRequest("alice", "report", "read")
        return policy_set, request

    def test_delegates_to_reference_engine_without_duplicating_logic(self) -> None:
        policy_set, request = self._inputs()
        service = EvaluationService()

        record = service.evaluate(policy_set=policy_set, request=request)
        direct = ReferenceEngine().evaluate(policy_set, request)

        assert record.result.to_dict() == direct.to_dict()

    def test_records_are_sequential_and_latest_returns_last(self) -> None:
        policy_set, request = self._inputs()
        service = EvaluationService()

        first = service.evaluate(policy_set=policy_set, request=request)
        deny_request = AccessRequest("bob", "report", "read")
        second = service.evaluate(
            policy_set=policy_set, request=deny_request
        )

        assert first.record_id == 1
        assert second.record_id == 2
        assert service.latest() is second
        assert len(service.records) == 2

    def test_empty_service_has_no_latest(self) -> None:
        assert EvaluationService().latest() is None

    def test_export_dict_uses_existing_serialization_contracts(self) -> None:
        policy_set, request = self._inputs()
        service = EvaluationService()

        record = service.evaluate(policy_set=policy_set, request=request)
        payload = record.to_export_dict()

        assert payload["request"] == request.to_dict()
        assert payload["result"] == record.result.to_dict()
        assert payload["policy"] == policy_set.to_dict()
        assert set(payload) == {
            "record_id",
            "policy",
            "policy_path",
            "request",
            "result",
        }

    def test_export_record_writes_json_file(self, tmp_path) -> None:
        policy_set, request = self._inputs()
        service = EvaluationService()
        record = service.evaluate(policy_set=policy_set, request=request)
        export_dir = tmp_path / "exports"

        path, error = service.export_record(record, export_dir)

        assert error is None
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["result"]["decision"] == "ALLOW"
        assert data["result"]["reason"] == "MATCHED_ALLOW"
        assert data["request"] == request.to_dict()

    def test_export_record_reports_write_errors(self, tmp_path) -> None:
        policy_set, request = self._inputs()
        service = EvaluationService()
        record = service.evaluate(policy_set=policy_set, request=request)
        blocker = tmp_path / "blocker"
        blocker.write_text("x", encoding="utf-8")

        _, error = service.export_record(record, blocker / "exports")

        assert error is not None
        assert "cannot export record" in error
