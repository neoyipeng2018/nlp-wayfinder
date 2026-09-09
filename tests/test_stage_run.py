from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from nlp_wayfinder.stage_run import CostLimitError, StageRun, confirm_manifest


ROUTE_IDS = (
    "mistral/mistral-medium-3-5",
    "cf/@cf/zai-org/glm-4.7-flash",
    "groq/qwen/qwen3.6-27b",
)


def route(route_id: str) -> dict[str, object]:
    return {
        "route_id": route_id,
        "model_identity_verified": True,
        "account_free_limit_verified": True,
        "training_use_permitted": True,
        "audit_fields_supported": True,
        "no_paid_overflow": True,
        "current_stage_requests": 6868,
        "remaining_experiment_requests": 21000,
        "free_requests_remaining": 21000,
        "requests_per_day": 1000,
        "available_days": 7,
        "evidence": {
            "checked_at": "2026-09-10T00:00:00Z",
            "account": "fixture-account",
            "terms_url": "https://example.test/terms",
        },
    }


def draft_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": "stage-1-fixture",
        "stage": 1,
        "source": {
            "source_id": "financial-news-fixture",
            "source_type": "financial-news",
            "access_permitted": True,
            "private_evaluation_permitted": True,
            "training_permitted": True,
            "weight_release_permitted": True,
            "text_redistribution_permitted": True,
            "evidence": {
                "checked_at": "2026-09-10T00:00:00Z",
                "terms_url": "https://example.test/news-terms",
                "reviewer": "fixture-reviewer",
            },
        },
        "route_panel": {
            "inspection_complete": True,
            "routes": [route(route_id) for route_id in ROUTE_IDS],
        },
        "schedule": {
            "starts_on": "2026-09-14",
            "must_finish_by": "2026-09-20",
            "evidence": "fixture schedule review",
        },
        "budget": {
            "planned_commitments_usd": {
                "paid-silver-labels": "0.00",
                "specialist": "30.00",
                "gpt": "25.00",
                "data-and-storage": "20.00",
                "contingency": "0.00",
            },
            "evidence": "fixture cost projection",
        },
    }


class StageRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name)
        self.runner = StageRun(
            self.state_dir,
            clock=lambda: "2026-09-10T00:00:00Z",
        )

    def test_failed_source_right_stops_before_any_external_action(self) -> None:
        manifest = draft_manifest()
        manifest["source"]["training_permitted"] = False  # type: ignore[index]

        decision = self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

        self.assertEqual("no-build", decision["decision"])
        self.assertEqual("source-rights-failed", decision["stop_reason"])
        self.assertEqual([], decision["permitted_external_actions"])
        self.assertFalse((self.state_dir / "spend-ledger.jsonl").exists())

    def test_fewer_than_three_eligible_routes_stops_the_run(self) -> None:
        manifest = draft_manifest()
        manifest["route_panel"]["routes"][0]["training_use_permitted"] = False  # type: ignore[index]

        decision = self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

        self.assertEqual("no-build", decision["decision"])
        self.assertEqual("insufficient-eligible-routes", decision["stop_reason"])
        self.assertEqual([], decision["permitted_external_actions"])

    def test_valid_preflight_records_all_gate_evidence(self) -> None:
        decision = self.runner.evaluate(
            confirm_manifest(draft_manifest(), "fixture-owner")
        )

        self.assertEqual("build-eligible", decision["decision"])
        self.assertIsNone(decision["stop_reason"])
        self.assertEqual(["stage-1-build"], decision["permitted_external_actions"])
        evidence = cast(dict[str, Any], decision["evidence"])
        self.assertEqual("financial-news-fixture", evidence["source"]["source_id"])
        self.assertEqual(list(ROUTE_IDS), evidence["routes"]["eligible_route_ids"])
        self.assertEqual(7, evidence["schedule"]["required_days"])
        self.assertEqual("fixture-owner", evidence["confirmation"]["confirmed_by"])
        self.assertEqual("100.00", evidence["budget"]["total_limit_usd"])
        self.assertEqual("75.00", evidence["budget"]["planned_total_usd"])

    def test_complete_route_panel_includes_an_added_eligible_route(self) -> None:
        manifest = draft_manifest()
        extra_route = route("provider/fixed-extra-model")
        extra_route["current_stage_requests"] = 500
        manifest["route_panel"]["routes"].append(extra_route)  # type: ignore[index]

        decision = self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

        evidence = cast(dict[str, Any], decision["evidence"])
        self.assertEqual("build-eligible", decision["decision"])
        self.assertEqual(
            [*ROUTE_IDS, "provider/fixed-extra-model"],
            evidence["routes"]["eligible_route_ids"],
        )

    def test_schedule_window_must_hold_the_slowest_route(self) -> None:
        manifest = draft_manifest()
        manifest["schedule"]["must_finish_by"] = "2026-09-19"  # type: ignore[index]

        decision = self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

        self.assertEqual("no-build", decision["decision"])
        self.assertEqual("route-schedule-infeasible", decision["stop_reason"])

    def test_semantic_change_stops_and_appends_a_decision_record(self) -> None:
        manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        first = self.runner.evaluate(manifest)
        log_path = self.state_dir / "decision-log.jsonl"
        original_log = log_path.read_text(encoding="utf-8")
        changed = copy.deepcopy(manifest)
        changed["source"]["source_id"] = "changed-source"  # type: ignore[index]

        second = self.runner.evaluate(changed)

        self.assertEqual("build-eligible", first["decision"])
        self.assertEqual("no-build", second["decision"])
        self.assertEqual("semantic-manifest-change", second["stop_reason"])
        changed_log = log_path.read_text(encoding="utf-8")
        self.assertTrue(changed_log.startswith(original_log))
        records = [json.loads(line) for line in changed_log.splitlines()]
        self.assertEqual("semantic-change-attempted", records[-1]["event"])

    def test_cost_ledger_keeps_commitments_and_actual_costs_in_one_file(self) -> None:
        self.runner.record_cost(
            action_id="gpu-pilot",
            kind="commitment",
            category="specialist",
            amount_usd="5.00",
            evidence="rental quote",
        )
        self.runner.record_cost(
            action_id="gpu-pilot",
            kind="actual",
            category="specialist",
            amount_usd="4.25",
            evidence="provider receipt",
        )

        records = self.runner.cost_records()

        self.assertEqual(["commitment", "actual"], [r["kind"] for r in records])
        self.assertEqual(Decimal("4.25"), self.runner.budget_exposure()["specialist"])
        self.assertEqual(
            self.state_dir / "spend-ledger.jsonl", self.runner.spend_ledger_path
        )

    def test_cost_that_exceeds_a_category_limit_is_not_written(self) -> None:
        before = self.runner.record_cost(
            action_id="training",
            kind="commitment",
            category="specialist",
            amount_usd="35.00",
            evidence="approved quote",
        )

        with self.assertRaisesRegex(CostLimitError, "category-budget-exceeded"):
            self.runner.record_cost(
                action_id="extra-pilot",
                kind="commitment",
                category="specialist",
                amount_usd="0.01",
                evidence="second quote",
            )

        self.assertEqual([before], self.runner.cost_records())

    def test_initial_manifest_cli_returns_machine_readable_no_build(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "nlp_wayfinder.stage_run",
                "check",
                "manifests/stage-1.initial.json",
                "--state-dir",
                str(self.state_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, result.returncode)
        output = json.loads(result.stdout)
        self.assertEqual("no-build", output["decision"])
        self.assertEqual("source-rights-failed", output["stop_reason"])


if __name__ == "__main__":
    unittest.main()
