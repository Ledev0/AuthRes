"""Pilot-driven behavior tests for each TUI screen."""

from __future__ import annotations

import json
from pathlib import Path

from authres.core.models import AccessRequest
from authres.core.policy import PolicySet
from tui_support import EXAMPLES_DIR, make_app, run_pilot


def _set_pending(app, *, policy_path: Path | None) -> None:
    app.services.evaluation.set_pending_request(
        AccessRequest("alice", "report", "read"),
        json.dumps({"subject": "alice", "resource": "report", "action": "read"}),
    )
    if policy_path is not None:
        app.services.evaluation.selected_policy_path = policy_path


class TestPolicyExplorer:
    def test_lists_examples_and_previews_selected_file(self, tmp_path) -> None:
        app = make_app(tmp_path)  # default policy dir = project examples

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("p")
            await pilot.pause()

            list_view = app.screen.query_one("#policy-file-list")
            names = [str(child.children[0].render()) for child in list_view.children]
            assert [str(name) for name in names] == [
                "basic_allow.json",
                "conflict.json",
                "default_deny.json",
            ]

            summary = str(app.screen.query_one("#policy-summary").render())
            assert "Valid" in summary

            preview = str(app.screen.query_one("#policy-preview").render())
            assert "ALLOW" in preview

        run_pilot(app, body)

    def test_selection_down_updates_preview(self, tmp_path) -> None:
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("p")
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            # Second file is conflict.json: preview contains both effects.
            preview = str(app.screen.query_one("#policy-preview").render())
            assert "DENY" in preview
            assert app.policy_selection is not None
            assert app.policy_selection.path.name == "conflict.json"

        run_pilot(app, body)

    def test_invalid_policy_file_shows_validation_error(self, tmp_path) -> None:
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        (policy_dir / "broken.json").write_text(
            json.dumps({"version": 1, "policies": [{"subject": "alice"}]}),
            encoding="utf-8",
        )
        app = make_app(tmp_path, policy_dir=policy_dir)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("p")
            await pilot.pause()

            summary = str(app.screen.query_one("#policy-summary").render())
            assert "Invalid ·" in summary
            assert "missing required field(s)" in summary

        run_pilot(app, body)

    def test_empty_directory_shows_empty_state(self, tmp_path) -> None:
        policy_dir = tmp_path / "empty-policies"
        policy_dir.mkdir()
        app = make_app(tmp_path, policy_dir=policy_dir)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("p")
            await pilot.pause()

            status = str(app.screen.query_one("#policy-status").render())
            assert "No *.json files" in status
            preview = str(app.screen.query_one("#policy-preview").render())
            assert "No policy files found." in preview

        run_pilot(app, body)


class TestRequestBuilder:
    def test_builds_and_previews_valid_request(self, tmp_path) -> None:
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("b")
            await pilot.pause()

            await pilot.click("#subject")
            await pilot.press(*"alice")
            await pilot.click("#resource")
            await pilot.press(*"report")
            await pilot.click("#action")
            await pilot.press(*"read")
            await pilot.press("ctrl+b")
            await pilot.pause()

            status = str(app.screen.query_one("#request-status").render())
            assert "Request ready" in status

            preview = str(app.screen.query_one("#request-preview").render())
            assert '"subject": "alice"' in preview
            assert '"resource": "report"' in preview
            assert '"action": "read"' in preview

            pending = app.services.evaluation.pending_request
            assert pending is not None
            assert (pending.subject, pending.resource, pending.action) == (
                "alice",
                "report",
                "read",
            )

        run_pilot(app, body)

    def test_rejects_empty_request_without_crashing(self, tmp_path) -> None:
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("b")
            await pilot.pause()
            await pilot.press("ctrl+b")
            await pilot.pause()

            status = str(app.screen.query_one("#request-status").render())
            assert "Invalid request" in status
            assert "must not be empty" in status
            assert app.services.evaluation.pending_request is None

        run_pilot(app, body)

    def test_duplicate_attribute_rejected_via_core_validation(
        self, tmp_path
    ) -> None:
        # The builder routes through AccessRequest.from_dict, so only the
        # documented validation applies; here we check the whitespace-only
        # rule is surfaced rather than silently accepted.
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("b")
            await pilot.pause()
            await pilot.click("#subject")
            await pilot.press(*"   ")
            await pilot.click("#resource")
            await pilot.press(*"report")
            await pilot.click("#action")
            await pilot.press(*"read")
            await pilot.press("ctrl+b")
            await pilot.pause()

            status = str(app.screen.query_one("#request-status").render())
            assert "must not be empty" in status

        run_pilot(app, body)


class TestEvaluationScreen:
    def test_runs_reference_engine_and_shows_result(self, tmp_path) -> None:
        app = make_app(tmp_path)
        _set_pending(app, policy_path=EXAMPLES_DIR / "conflict.json")

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("e")
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

            result_text = str(app.screen.query_one("#eval-result").render())
            assert "Decision: DENY" in result_text
            assert "Reason: DENY_OVERRIDE" in result_text
            assert "allow-alice-read-report" in result_text

            status = str(app.screen.query_one("#eval-status").render())
            assert "Evaluation #1 complete" in status
            assert len(app.services.evaluation.records) == 1

        run_pilot(app, body)

    def test_allow_result_for_basic_policy(self, tmp_path) -> None:
        app = make_app(tmp_path)
        _set_pending(app, policy_path=EXAMPLES_DIR / "basic_allow.json")

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("e")
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

            result_text = str(app.screen.query_one("#eval-result").render())
            assert "Decision: ALLOW" in result_text
            assert "Reason: MATCHED_ALLOW" in result_text

        run_pilot(app, body)

    def test_missing_request_shows_error_and_records_nothing(self, tmp_path) -> None:
        app = make_app(tmp_path)
        app.services.evaluation.selected_policy_path = (
            EXAMPLES_DIR / "basic_allow.json"
        )

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("e")
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

            status = str(app.screen.query_one("#eval-status").render())
            assert "No request" in status
            assert len(app.services.evaluation.records) == 0

        run_pilot(app, body)

    def test_invalid_policy_reports_error_without_crashing(self, tmp_path) -> None:
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        broken = policy_dir / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        app = make_app(tmp_path, policy_dir=policy_dir)
        _set_pending(app, policy_path=broken)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("e")
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

            status = str(app.screen.query_one("#eval-status").render())
            assert "Policy invalid" in status
            assert "invalid JSON" in status
            assert len(app.services.evaluation.records) == 0

        run_pilot(app, body)


class TestResultsScreen:
    def _add_record(self, app) -> None:
        policy_set = PolicySet.from_file(EXAMPLES_DIR / "conflict.json")
        app.services.evaluation.evaluate(
            policy_set=policy_set,
            request=AccessRequest("alice", "report", "read"),
            policy_path=str(EXAMPLES_DIR / "conflict.json"),
        )

    def test_empty_state(self, tmp_path) -> None:
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("v")
            await pilot.pause()

            empty = str(app.screen.query_one("#results-empty").render())
            assert "No evaluations" in empty

        run_pilot(app, body)

    def test_lists_record_and_shows_details(self, tmp_path) -> None:
        app = make_app(tmp_path)
        self._add_record(app)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("v")
            await pilot.pause()

            table = app.screen.query_one("#results-table")
            assert table.row_count == 1

            detail = str(app.screen.query_one("#results-detail").render())
            assert "Decision: DENY" in detail
            assert "DENY_OVERRIDE" in detail

            payload = str(app.screen.query_one("#results-json").render())
            assert '"decision": "DENY"' in payload
            assert '"record_id": 1' in payload

        run_pilot(app, body)

    def test_export_selected_record(self, tmp_path) -> None:
        export_dir = tmp_path / "exports"
        app = make_app(tmp_path, export_dir=export_dir)
        self._add_record(app)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("v")
            await pilot.pause()
            await pilot.press("x")
            await pilot.pause()

            status = str(app.screen.query_one("#results-status").render())
            assert "Exported evaluation #1" in status

            files = list(export_dir.glob("authres_eval_*.json"))
            assert len(files) == 1
            data = json.loads(files[0].read_text(encoding="utf-8"))
            assert data["result"]["decision"] == "DENY"

        run_pilot(app, body)


class TestSettingsScreen:
    def test_shows_current_settings(self, tmp_path) -> None:
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("s")
            await pilot.pause()

            policy_dir = app.screen.query_one("#settings-policy-dir").value
            export_dir = app.screen.query_one("#settings-export-dir").value
            assert policy_dir == str(app.services.settings.policy_dir)
            assert export_dir == str(app.services.settings.export_dir)

        run_pilot(app, body)

    def test_save_updates_services_and_persists_file(self, tmp_path) -> None:
        app = make_app(tmp_path)
        new_policy_dir = tmp_path / "my-policies"
        new_policy_dir.mkdir()

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("s")
            await pilot.pause()
            app.screen.query_one("#settings-policy-dir").value = str(
                new_policy_dir
            )
            await pilot.press("escape")  # leave the input
            await pilot.press("s")  # screen binding: save
            await pilot.pause()

            status = str(app.screen.query_one("#settings-status").render())
            assert "Settings saved." in status
            assert app.services.settings.policy_dir == new_policy_dir
            assert app.services.settings_store.path.exists()

        run_pilot(app, body)

    def test_save_warns_when_policy_dir_missing(self, tmp_path) -> None:
        app = make_app(tmp_path)

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("s")
            await pilot.pause()
            app.screen.query_one("#settings-policy-dir").value = str(
                tmp_path / "does-not-exist"
            )
            await pilot.press("escape")  # leave the input
            await pilot.press("s")
            await pilot.pause()

            status = str(app.screen.query_one("#settings-status").render())
            assert "Settings saved." in status
            assert "Warning: policy directory does not exist" in status

        run_pilot(app, body)

    def test_saved_policy_dir_feeds_policy_explorer(self, tmp_path) -> None:
        app = make_app(tmp_path)
        policy_dir = tmp_path / "custom"
        policy_dir.mkdir()
        (policy_dir / "custom.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "policies": [
                        {
                            "id": "deny-bob",
                            "subject": "bob",
                            "resource": "report",
                            "action": "read",
                            "effect": "DENY",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        async def body(pilot, app) -> None:
            await pilot.press("escape")
            await pilot.press("s")
            await pilot.pause()
            app.screen.query_one("#settings-policy-dir").value = str(policy_dir)
            await pilot.press("s")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.press("p")
            await pilot.pause()

            preview = str(app.screen.query_one("#policy-preview").render())
            assert "bob" in preview

        run_pilot(app, body)
