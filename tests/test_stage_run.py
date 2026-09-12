from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from nlp_wayfinder.stage_run import (
    MAX_EXAMPLE_TOKENS,
    RESULT_LABELS,
    CostLimitError,
    StageRun,
    admit_example,
    confirm_manifest,
)


ROUTE_IDS = (
    "mistral/mistral-medium-3-5",
    "cf/@cf/zai-org/glm-4.7-flash",
    "groq/qwen/qwen3.6-27b",
)


class WordTokenizer:
    """Count whitespace tokens and the two outer special tokens."""

    def __call__(self, text: str, **kwargs: object) -> dict[str, object]:
        self.last_text = text
        self.last_options = kwargs
        return {"input_ids": [101, *range(len(text.split())), 102]}


def example(
    passage: str,
    *,
    company: str = "Harbor Grid Ltd",
    aspect: str = "operations, supply, and capacity",
    label: str | None = "neutral",
) -> dict[str, object]:
    sentences = [
        {"position": index, "text": sentence.strip() + "."}
        for index, sentence in enumerate(passage.rstrip(".").split(". "), start=20)
    ]
    value: dict[str, object] = {
        "company": {
            "name": company,
            "ticker": "HGL",
            "exchange": "LSE",
            "publicly_traded": True,
        },
        "aspect": aspect,
        "sentences": sentences,
        "target_evidence_positions": [20],
        "required_evidence_positions": [item["position"] for item in sentences],
    }
    if label is not None:
        value["label"] = label
    return value


def route(route_id: str) -> dict[str, object]:
    return {
        "route_id": route_id,
        "model_identity_verified": True,
        "non_gpt_verified": True,
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

    def test_gpt_route_cannot_satisfy_the_non_gpt_route_minimum(self) -> None:
        manifest = draft_manifest()
        manifest["route_panel"]["routes"][0]["training_use_permitted"] = False  # type: ignore[index]
        gpt_route = route("provider/gpt-model")
        gpt_route["non_gpt_verified"] = False
        manifest["route_panel"]["routes"].append(gpt_route)  # type: ignore[index]

        decision = self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

        self.assertEqual("no-build", decision["decision"])
        self.assertEqual("insufficient-eligible-routes", decision["stop_reason"])

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

    def test_confirmation_evidence_cannot_change_after_it_is_recorded(self) -> None:
        manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        self.runner.evaluate(manifest)
        changed = copy.deepcopy(manifest)
        changed["confirmation"]["confirmed_by"] = "different-owner"  # type: ignore[index]

        decision = self.runner.evaluate(changed)

        self.assertEqual("no-build", decision["decision"])
        self.assertEqual("confirmation-evidence-changed", decision["stop_reason"])
        self.assertEqual(
            "confirmation-change-attempted",
            self.runner.decision_records()[-1]["event"],
        )

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

    def test_parallel_commitments_cannot_exceed_a_category_limit(self) -> None:
        worker_count = 40
        start = threading.Barrier(worker_count)

        def commit(index: int) -> None:
            start.wait()
            try:
                self.runner.record_cost(
                    action_id=f"parallel-{index}",
                    kind="commitment",
                    category="specialist",
                    amount_usd="1.00",
                    evidence="parallel limit test",
                )
            except CostLimitError:
                pass

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            list(executor.map(commit, range(worker_count)))

        self.assertEqual(Decimal("35.00"), self.runner.budget_exposure()["specialist"])
        self.assertEqual(35, len(self.runner.cost_records()))

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


class ExampleAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokenizer = WordTokenizer()

    def test_admits_one_shared_evidence_preserving_input(self) -> None:
        candidate = example(
            "Harbor Grid said the planned two-week maintenance shutdown is not "
            "expected to have a material effect on full-year output"
        )

        result = admit_example(candidate, self.tokenizer)

        self.assertEqual("accepted", result["admission"])
        self.assertIsNone(result["schema_result"])
        self.assertEqual("neutral", result["label"])
        self.assertEqual(list(RESULT_LABELS), result["allowed_result_labels"])
        self.assertEqual(
            ["human", "labeling-route", "specialist", "gpt"],
            result["consumers"],
        )
        self.assertEqual(result["serialized_input"], self.tokenizer.last_text)
        self.assertEqual(MAX_EXAMPLE_TOKENS, result["token_limit"])
        self.assertTrue(self.tokenizer.last_options["add_special_tokens"])
        self.assertFalse(self.tokenizer.last_options["truncation"])

    def test_rejects_a_target_that_is_not_a_publicly_traded_company(self) -> None:
        candidate = example("Consumer prices rose during the quarter")
        candidate["company"]["publicly_traded"] = False  # type: ignore[index]

        result = admit_example(candidate, self.tokenizer)

        self.assertEqual("Invalid", result["schema_result"])
        self.assertEqual("invalid-company", result["stop_reason"])

    def test_rejects_an_aspect_outside_the_stage_1_set(self) -> None:
        candidate = example(
            "Harbor Grid made a new investment",
            aspect="capital allocation",
        )

        result = admit_example(candidate, self.tokenizer)

        self.assertEqual("Invalid", result["schema_result"])
        self.assertEqual("invalid-aspect", result["stop_reason"])

    def test_invalid_is_not_a_result_label(self) -> None:
        candidate = example("Harbor Grid output was stable", label="Invalid")

        result = admit_example(candidate, self.tokenizer)

        self.assertEqual("Invalid", result["schema_result"])
        self.assertEqual("invalid-label", result["stop_reason"])
        self.assertNotIn("Invalid", result["allowed_result_labels"])

    def test_rejects_nonconsecutive_or_incomplete_sentences(self) -> None:
        candidate = example("Harbor Grid output rose. Demand remained stable")
        candidate["sentences"][1]["position"] = 22  # type: ignore[index]
        nonconsecutive = admit_example(candidate, self.tokenizer)
        candidate["sentences"][1]["position"] = 21  # type: ignore[index]
        candidate["sentences"][1]["text"] = "Demand remained stable"  # type: ignore[index]
        incomplete = admit_example(candidate, self.tokenizer)

        self.assertEqual("nonconsecutive-sentences", nonconsecutive["stop_reason"])
        self.assertEqual("invalid-sentence-span", incomplete["stop_reason"])

    def test_rejects_missing_target_or_required_evidence(self) -> None:
        candidate = example("Harbor Grid output rose")
        candidate["target_evidence_positions"] = []
        missing_target = admit_example(candidate, self.tokenizer)
        candidate["target_evidence_positions"] = [20]
        candidate["required_evidence_positions"] = [21]
        missing_required = admit_example(candidate, self.tokenizer)

        self.assertEqual("target-evidence-missing", missing_target["stop_reason"])
        self.assertEqual("required-evidence-missing", missing_required["stop_reason"])

    def test_counts_the_complete_serialized_input_at_the_token_boundary(self) -> None:
        candidate = example("Harbor Grid output was stable")
        base_result = admit_example(candidate, self.tokenizer)
        base_count = cast(int, base_result["token_count"])
        added = MAX_EXAMPLE_TOKENS - base_count
        candidate["sentences"][0]["text"] = (  # type: ignore[index]
            "Harbor Grid output was stable " + " ".join(["context"] * added) + "."
        )

        at_limit = admit_example(candidate, self.tokenizer)
        candidate["sentences"][0]["text"] = (  # type: ignore[index]
            str(candidate["sentences"][0]["text"])[:-1] + " context."
        )
        above_limit = admit_example(candidate, self.tokenizer)

        self.assertEqual(MAX_EXAMPLE_TOKENS, at_limit["token_count"])
        self.assertEqual("accepted", at_limit["admission"])
        self.assertEqual("evidence-does-not-fit", above_limit["stop_reason"])

    def test_frozen_manual_aspect_and_evidence_cases_are_valid(self) -> None:
        cases = (
            example(
                "Northstar Foods said quarterly revenue rose 8%. Its operating "
                "margin fell by two percentage points because input costs increased. "
                "The report gave no overall profit figure or assessment",
                company="Northstar Foods plc",
                aspect="financial performance",
                label="insufficient evidence",
            ),
            example(
                "The chief executive said bookings remain robust. An analyst then "
                "said channel checks showed more customer cancellations. Management "
                "did not answer the cancellation point",
                company="Cedar Cloud Inc",
                aspect="demand and commercial traction",
                label="insufficient evidence",
            ),
        )

        results = [admit_example(case, self.tokenizer) for case in cases]

        self.assertEqual(["accepted", "accepted"], [r["admission"] for r in results])


if __name__ == "__main__":
    unittest.main()
