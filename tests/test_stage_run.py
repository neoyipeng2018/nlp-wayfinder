from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, cast

from nlp_wayfinder.stage_run import (
    MAX_EXAMPLE_TOKENS,
    SILVER_CALIBRATION_FOLDS,
    SILVER_MIN_PROBABILITY,
    OmniRouteHttpTransport,
    RESULT_LABELS,
    STAGE_1_ASPECTS,
    CostLimitError,
    OmniRouteResponse,
    StageRun,
    admit_example,
    allocate_stage_1,
    _calibration_fold,
    _silver_rejection,
    candidate_order_sha256,
    seal_candidate_manifest,
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


class FixedVoteTransport:
    """Return one valid fixed-route response and retain each request."""

    def __init__(self) -> None:
        self.requests: list[tuple[dict[str, object], float]] = []

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        request_copy = copy.deepcopy(dict(request))
        self.requests.append((request_copy, timeout_seconds))
        route_id = str(request["model"])
        provider, model = route_id.split("/", 1)
        body = {
            "id": f"response-{len(self.requests)}",
            "model": model,
            "choices": [
                {"message": {"content": '{"label":"positive"}'}}
            ],
            "usage": {
                "prompt_tokens": 91,
                "completion_tokens": 5,
                "total_tokens": 96,
            },
        }
        return OmniRouteResponse(
            status_code=200,
            headers={
                "x-omniroute-response-cost": "0.0000000000",
                "x-omniroute-tokens-in": "91",
                "x-omniroute-tokens-out": "5",
                "x-omniroute-model": model,
                "x-omniroute-provider": provider,
                "x-omniroute-latency-ms": "125",
                "x-omniroute-cache-hit": "false",
                "x-omniroute-fallback-attempts": "0",
                "x-omniroute-decision": (
                    f"strategy=single; provider={provider}; latency_ms=125"
                ),
                "x-omniroute-request-id": f"request-{len(self.requests)}",
                "x-omniroute-version": "3.8.49",
            },
            body=body,
        )


class SequenceVoteTransport(FixedVoteTransport):
    def __init__(self, first: OmniRouteResponse | BaseException) -> None:
        super().__init__()
        self.first = first

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        if not self.requests:
            self.requests.append((copy.deepcopy(dict(request)), timeout_seconds))
            if isinstance(self.first, BaseException):
                raise self.first
            return self.first
        return super().complete(request, timeout_seconds)


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


def candidate_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "stage": 1,
        "source": "financial-news",
        "annex": {
            "acquisition": {
                "method": "Fixed export from the approved source.",
                "evidence": "fixture-export-record",
            },
            "rights": {
                "access_permitted": True,
                "private_evaluation_permitted": True,
                "training_permitted": True,
                "weight_release_permitted": True,
                "text_redistribution_permitted": True,
                "evidence": "fixture-rights-record",
            },
            "extraction": {"method": "Extract complete article sentences."},
            "normalization": {"method": "Use NFC text and normalized whitespace."},
            "target_and_aspect_expansion": {
                "method": "Use each supported company and aspect."
            },
            "grouping": {"method": "Group reports about the same event."},
            "duplicate_review": {
                "exact_method": "Compare normalized passage hashes.",
                "near_method": "Review similarity groups.",
                "completed_at": "2026-09-09T00:00:00Z",
            },
            "split_rules": {
                "training_starts_on": "2026-01-01",
                "training_ends_on": "2026-06-30",
                "development_starts_on": "2026-07-01",
                "development_ends_on": "2026-08-31",
                "blind_starts_on": "2026-09-01",
                "blind_ends_on": "2026-12-31",
            },
            "limits": {
                "silver_candidate_limit": 6668,
                "development_target": 200,
                "blind_target": 400,
            },
            "software_versions": {"nlp-wayfinder": "fixture-revision"},
        },
        "candidates": [
            {
                "candidate_id": "candidate-b",
                "event_group_id": "event-b",
                "published_at": "2026-07-10T09:00:00Z",
                "normalized_passage": "Harbor Grid opened its second plant.",
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "candidate-a",
                "event_group_id": "event-a",
                "published_at": "2026-03-10T09:00:00Z",
                "normalized_passage": "Harbor Grid opened its first plant.",
                "near_duplicate_reviewed": True,
            },
        ],
    }


def allocation_manifest() -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest = candidate_manifest()
    candidates: list[dict[str, object]] = []
    reviews: list[dict[str, object]] = []

    def add_candidate(
        split: str,
        index: int,
        company_id: str,
        aspect: str,
        label: str,
        event_group_id: str,
    ) -> None:
        published_at = {
            "training": "2026-03-10T09:00:00Z",
            "development": "2026-07-10T09:00:00Z",
            "blind": "2026-09-10T09:00:00Z",
        }[split]
        candidate_id = f"{split}-{index:04d}"
        candidates.append(
            {
                "candidate_id": candidate_id,
                "event_group_id": event_group_id,
                "published_at": published_at,
                "normalized_passage": f"Unique passage for {candidate_id}.",
                "near_duplicate_reviewed": True,
                "company_id": company_id,
                "aspect": aspect,
            }
        )
        reviews.append(
            {
                "candidate_id": candidate_id,
                "disposition": "accepted",
                "label": label,
                "labeled_at": "2026-09-11T00:00:00Z",
            }
        )

    for index in range(4_000):
        add_candidate(
            "training",
            index,
            f"seen-{index // 5:04d}",
            STAGE_1_ASPECTS[index % 4],
            RESULT_LABELS[index % 4],
            f"training-event-{index:04d}",
        )
    for index in range(200):
        add_candidate(
            "development",
            index,
            f"development-{index // 5:04d}",
            STAGE_1_ASPECTS[index % 4],
            RESULT_LABELS[index % 4],
            f"development-event-{index:04d}",
        )
    blind_index = 0
    for aspect in STAGE_1_ASPECTS:
        for label in RESULT_LABELS:
            for _ in range(25):
                add_candidate(
                    "blind",
                    blind_index,
                    f"unseen-{blind_index // 4:03d}",
                    aspect,
                    label,
                    f"blind-event-{blind_index:04d}",
                )
                blind_index += 1
    manifest["candidates"] = candidates
    return manifest, reviews


def inspection_records(
    sealed: Mapping[str, object], reviews: list[dict[str, object]]
) -> list[dict[str, object]]:
    manifest_sha256 = str(cast(Mapping[str, object], sealed["seal"])["semantic_sha256"])
    reviewed_ids = {str(review["candidate_id"]) for review in reviews}
    return [
        {
            "event": "candidate-inspected",
            "manifest_sha256": manifest_sha256,
            "candidate_id": candidate["candidate_id"],
        }
        for candidate in cast(list[dict[str, object]], sealed["candidates"])
        if str(candidate["candidate_id"]) in reviewed_ids
    ]


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


class CandidateManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runner = StageRun(
            self.temp_dir.name,
            clock=lambda: "2026-09-10T00:00:00Z",
        )

    def test_seal_creates_the_frozen_sha256_candidate_order(self) -> None:
        sealed = seal_candidate_manifest(
            candidate_manifest(),
            "fixture-owner",
            sealed_at="2026-09-10T00:00:00Z",
        )

        candidates = cast(list[dict[str, object]], sealed["candidates"])
        hashes = [str(candidate["order_sha256"]) for candidate in candidates]
        self.assertEqual(sorted(hashes), hashes)
        for candidate in candidates:
            expression = (
                "nlp-wayfinder"
                f"1financial-news{candidate['split']}"
                f"{candidate['candidate_id']}20260905"
            )
            self.assertEqual(
                hashlib.sha256(expression.encode("utf-8")).hexdigest(),
                candidate["order_sha256"],
            )
        self.assertEqual(
            {"training", "development"},
            {candidate["split"] for candidate in candidates},
        )
        self.assertEqual(
            "fixture-owner", sealed["seal"]["sealed_by"]  # type: ignore[index]
        )

    def test_seal_rejects_an_incomplete_source_annex(self) -> None:
        manifest = candidate_manifest()
        del manifest["annex"]["normalization"]  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "source-annex-incomplete"):
            seal_candidate_manifest(manifest, "fixture-owner")

    def test_seal_rejects_unresolved_exact_or_near_duplicates(self) -> None:
        exact = candidate_manifest()
        exact["candidates"][1]["normalized_passage"] = (  # type: ignore[index]
            exact["candidates"][0]["normalized_passage"]  # type: ignore[index]
        )
        near = candidate_manifest()
        for candidate in near["candidates"]:  # type: ignore[union-attr]
            candidate["near_duplicate_group_id"] = "near-1"

        with self.assertRaisesRegex(ValueError, "exact-duplicate-unresolved"):
            seal_candidate_manifest(exact, "fixture-owner")
        with self.assertRaisesRegex(ValueError, "near-duplicate-unresolved"):
            seal_candidate_manifest(near, "fixture-owner")

    def test_seal_does_not_trust_a_supplied_content_hash(self) -> None:
        manifest = candidate_manifest()
        manifest["candidates"][0]["content_sha256"] = "0" * 64  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "candidate-content-hash-mismatch"):
            seal_candidate_manifest(manifest, "fixture-owner")

    def test_seal_rejects_an_event_group_that_crosses_splits(self) -> None:
        manifest = candidate_manifest()
        manifest["candidates"][1]["event_group_id"] = "event-b"  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "event-group-crosses-splits"):
            seal_candidate_manifest(manifest, "fixture-owner")

    def test_stage_run_rejects_an_unsealed_candidate_manifest(self) -> None:
        result = self.runner.inspect_candidate(candidate_manifest(), "candidate-a")

        self.assertEqual("rejected", result["inspection"])
        self.assertEqual("unsealed-annex", result["stop_reason"])

    def test_stage_run_rejects_out_of_order_inspection(self) -> None:
        sealed = seal_candidate_manifest(candidate_manifest(), "fixture-owner")
        candidates = cast(list[dict[str, object]], sealed["candidates"])

        rejected = self.runner.inspect_candidate(
            sealed, str(candidates[1]["candidate_id"])
        )
        first = self.runner.inspect_candidate(
            sealed, str(candidates[0]["candidate_id"])
        )
        second = self.runner.inspect_candidate(
            sealed, str(candidates[1]["candidate_id"])
        )

        self.assertEqual("out-of-order-inspection", rejected["stop_reason"])
        self.assertEqual(
            ["accepted", "accepted"],
            [first["inspection"], second["inspection"]],
        )
        self.assertEqual(2, len(self.runner.candidate_inspection_records()))

    def test_candidate_manifest_cli_seals_and_inspects_first_candidate(self) -> None:
        draft_path = Path(self.temp_dir.name) / "draft-candidates.json"
        sealed_path = Path(self.temp_dir.name) / "sealed-candidates.json"
        draft_path.write_text(json.dumps(candidate_manifest()), encoding="utf-8")
        sealed_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "nlp_wayfinder.stage_run",
                "seal-candidates",
                str(draft_path),
                "--sealed-by",
                "fixture-owner",
                "--output",
                str(sealed_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        sealed = json.loads(sealed_path.read_text(encoding="utf-8"))
        first_id = sealed["candidates"][0]["candidate_id"]

        inspection_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "nlp_wayfinder.stage_run",
                "inspect-candidate",
                str(sealed_path),
                first_id,
                "--state-dir",
                self.temp_dir.name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, sealed_result.returncode, sealed_result.stdout)
        self.assertEqual(0, inspection_result.returncode, inspection_result.stdout)
        self.assertEqual("accepted", json.loads(inspection_result.stdout)["inspection"])


class StageOneAllocationTests(unittest.TestCase):
    def test_review_cannot_replace_an_append_only_inspection_record(self) -> None:
        manifest, reviews = allocation_manifest()
        sealed = seal_candidate_manifest(manifest, "fixture-owner")

        with self.assertRaisesRegex(ValueError, "allocation-review-not-inspected"):
            allocate_stage_1(sealed, reviews, [])

    def test_complete_allocation_has_fixed_quotas_balance_and_relabel_sample(
        self,
    ) -> None:
        manifest, reviews = allocation_manifest()
        sealed = seal_candidate_manifest(
            manifest,
            "fixture-owner",
            sealed_at="2026-09-10T00:00:00Z",
        )

        result = allocate_stage_1(sealed, reviews, inspection_records(sealed, reviews))

        self.assertEqual("complete", result["allocation"])
        self.assertIsNone(result["stop_reason"])
        self.assertEqual(
            {"training": 4_000, "development": 200, "blind": 400},
            result["selected_counts"],
        )
        self.assertEqual(4_000, result["silver_candidates_inspected"])
        blind = cast(list[dict[str, object]], result["blind"])
        cells = {
            (aspect, label): sum(
                item["aspect"] == aspect and item["label"] == label
                for item in blind
            )
            for aspect in STAGE_1_ASPECTS
            for label in RESULT_LABELS
        }
        self.assertEqual({25}, set(cells.values()))
        self.assertEqual(400, len({item["event_group_id"] for item in blind}))
        self.assertGreaterEqual(
            sum(item["unseen_issuer"] is True for item in blind), 100
        )
        relabel = cast(list[dict[str, object]], result["blind_relabel_sample"])
        self.assertEqual(60, len(relabel))
        self.assertEqual(60, len({item["candidate_id"] for item in relabel}))
        self.assertEqual(
            {3, 4},
            {
                sum(
                    item["aspect"] == aspect and item["label"] == label
                    for item in relabel
                )
                for aspect in STAGE_1_ASPECTS
                for label in RESULT_LABELS
            },
        )
        self.assertEqual(
            {"2026-09-25T00:00:00Z"},
            {item["relabel_not_before"] for item in relabel},
        )
        allocation_hash = str(result.pop("allocation_sha256"))
        self.assertEqual(
            hashlib.sha256(
                json.dumps(
                    result,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest(),
            allocation_hash,
        )

    def test_silver_source_stops_when_its_inspection_limit_cannot_fill_quota(
        self,
    ) -> None:
        manifest, reviews = allocation_manifest()
        candidates = cast(list[dict[str, object]], manifest["candidates"])
        reviews_by_id = {
            str(review["candidate_id"]): review for review in reviews
        }
        for review in reviews:
            if str(review["candidate_id"]).startswith("training-"):
                review["disposition"] = "excluded"
        for index in range(4_000, 6_668):
            candidate_id = f"training-{index:04d}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "event_group_id": f"training-event-{index:04d}",
                    "published_at": "2026-03-10T09:00:00Z",
                    "normalized_passage": f"Unique passage for {candidate_id}.",
                    "near_duplicate_reviewed": True,
                    "company_id": f"seen-{index // 5:04d}",
                    "aspect": STAGE_1_ASPECTS[index % 4],
                }
            )
            reviews_by_id[candidate_id] = {
                "candidate_id": candidate_id,
                "disposition": "excluded",
                "label": RESULT_LABELS[index % 4],
                "labeled_at": "2026-09-11T00:00:00Z",
            }
        sealed = seal_candidate_manifest(manifest, "fixture-owner")
        result = allocate_stage_1(
            sealed, [], inspection_records(sealed, list(reviews_by_id.values()))
        )

        self.assertEqual("stopped", result["allocation"])
        self.assertEqual("silver-candidate-limit-exhausted", result["stop_reason"])
        self.assertEqual(6_668, result["silver_candidates_inspected"])
        self.assertEqual(0, result["selected_counts"]["training"])  # type: ignore[index]

    def test_blind_replacement_is_the_next_eligible_item_in_the_same_cell(
        self,
    ) -> None:
        manifest, reviews = allocation_manifest()
        candidates = cast(list[dict[str, object]], manifest["candidates"])
        replacement_id = "blind-replacement"
        candidates.append(
            {
                "candidate_id": replacement_id,
                "event_group_id": "blind-event-replacement",
                "published_at": "2026-09-10T09:00:00Z",
                "normalized_passage": "Unique passage for the blind replacement.",
                "near_duplicate_reviewed": True,
                "company_id": "unseen-replacement",
                "aspect": STAGE_1_ASPECTS[0],
            }
        )
        reviews.append(
            {
                "candidate_id": replacement_id,
                "disposition": "accepted",
                "label": RESULT_LABELS[0],
                "labeled_at": "2026-09-11T00:00:00Z",
            }
        )
        sealed = seal_candidate_manifest(manifest, "fixture-owner")
        ordered_cell = [
            candidate
            for candidate in cast(list[dict[str, object]], sealed["candidates"])
            if candidate["split"] == "blind"
            and candidate["aspect"] == STAGE_1_ASPECTS[0]
            and next(
                review["label"]
                for review in reviews
                if review["candidate_id"] == candidate["candidate_id"]
            )
            == RESULT_LABELS[0]
        ]
        excluded_id = str(ordered_cell[0]["candidate_id"])
        next(
            review for review in reviews if review["candidate_id"] == excluded_id
        )["disposition"] = "excluded"

        result = allocate_stage_1(sealed, reviews, inspection_records(sealed, reviews))

        selected_ids = {
            item["candidate_id"]
            for item in cast(list[dict[str, object]], result["blind"])
        }
        expected_ids = {
            candidate["candidate_id"] for candidate in ordered_cell[1:26]
        }
        self.assertEqual("complete", result["allocation"])
        self.assertEqual(expected_ids, selected_ids.intersection(expected_ids))
        self.assertNotIn(excluded_id, selected_ids)

    def test_blind_balance_uses_the_next_eligible_same_cell_replacement(self) -> None:
        manifest, reviews = allocation_manifest()
        candidates = cast(list[dict[str, object]], manifest["candidates"])
        first_cell = [
            candidate
            for candidate in candidates
            if candidate["aspect"] == STAGE_1_ASPECTS[0]
            and str(candidate["candidate_id"]).startswith("blind-")
            and next(
                review["label"]
                for review in reviews
                if review["candidate_id"] == candidate["candidate_id"]
            )
            == RESULT_LABELS[0]
        ]
        for candidate in first_cell[:6]:
            candidate["company_id"] = "unseen-shared"
        candidates.append(
            {
                "candidate_id": "blind-balance-replacement",
                "event_group_id": "blind-balance-replacement-event",
                "published_at": "2026-09-10T09:00:00Z",
                "normalized_passage": "Unique balance replacement passage.",
                "near_duplicate_reviewed": True,
                "company_id": "unseen-balance-replacement",
                "aspect": STAGE_1_ASPECTS[0],
            }
        )
        reviews.append(
            {
                "candidate_id": "blind-balance-replacement",
                "disposition": "accepted",
                "label": RESULT_LABELS[0],
                "labeled_at": "2026-09-11T00:00:00Z",
            }
        )
        sealed = seal_candidate_manifest(manifest, "fixture-owner")

        result = allocate_stage_1(
            sealed, reviews, inspection_records(sealed, reviews)
        )

        blind = cast(list[dict[str, object]], result["blind"])
        self.assertEqual("complete", result["allocation"])
        self.assertLessEqual(
            max(Counter(item["company_id"] for item in blind).values()), 5
        )
        self.assertIn(
            "blind-balance-replacement",
            {item["candidate_id"] for item in blind},
        )

    def test_blind_search_can_coordinate_replacements_between_cells(self) -> None:
        manifest, reviews = allocation_manifest()
        candidates = cast(list[dict[str, object]], manifest["candidates"])
        reviews_by_id = {
            str(review["candidate_id"]): review for review in reviews
        }
        blind_candidates = [
            candidate
            for candidate in candidates
            if str(candidate["candidate_id"]).startswith("blind-")
        ]
        ordered_blind = sorted(
            blind_candidates,
            key=lambda candidate: candidate_order_sha256(
                1, "financial-news", "blind", str(candidate["candidate_id"])
            ),
        )
        first_cell = [
            candidate
            for candidate in ordered_blind
            if candidate["aspect"] == STAGE_1_ASPECTS[0]
            and reviews_by_id[str(candidate["candidate_id"])]["label"]
            == RESULT_LABELS[0]
        ]
        for candidate in first_cell[:3]:
            candidate["event_group_id"] = "shared-event"
        event_candidate_ids = {
            str(candidate["candidate_id"]) for candidate in first_cell[:3]
        }
        other_blind = [
            candidate
            for candidate in ordered_blind
            if str(candidate["candidate_id"]) not in event_candidate_ids
        ]
        for index, candidate in enumerate(first_cell[:3]):
            candidate["company_id"] = f"single-{index}"
        for index, candidate in enumerate(other_blind):
            candidate["company_id"] = f"unseen-{index % 97}"

        def tail_id(prefix: str, cell_candidates: list[dict[str, object]]) -> str:
            largest = max(
                candidate_order_sha256(
                    1, "financial-news", "blind", str(candidate["candidate_id"])
                )
                for candidate in cell_candidates
            )
            suffix = 0
            while True:
                candidate_id = f"{prefix}-{suffix}"
                if (
                    candidate_order_sha256(1, "financial-news", "blind", candidate_id)
                    > largest
                ):
                    return candidate_id
                suffix += 1

        def add_replacement(
            candidate_id: str, company_id: str, aspect: str, label: str
        ) -> None:
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "event_group_id": f"event-{candidate_id}",
                    "published_at": "2026-09-10T09:00:00Z",
                    "normalized_passage": f"Unique passage for {candidate_id}.",
                    "near_duplicate_reviewed": True,
                    "company_id": company_id,
                    "aspect": aspect,
                }
            )
            reviews.append(
                {
                    "candidate_id": candidate_id,
                    "disposition": "accepted",
                    "label": label,
                    "labeled_at": "2026-09-11T00:00:00Z",
                }
            )

        add_replacement(
            tail_id("seen-replacement", first_cell),
            "seen-0000",
            STAGE_1_ASPECTS[0],
            RESULT_LABELS[0],
        )
        last_cell = [
            candidate
            for candidate in ordered_blind
            if candidate["aspect"] == STAGE_1_ASPECTS[-1]
            and reviews_by_id[str(candidate["candidate_id"])]["label"]
            == RESULT_LABELS[-1]
        ]
        unseen_replacement_id = tail_id("unseen-replacement", last_cell)
        add_replacement(
            unseen_replacement_id,
            "new-unseen-issuer",
            STAGE_1_ASPECTS[-1],
            RESULT_LABELS[-1],
        )
        sealed = seal_candidate_manifest(manifest, "fixture-owner")

        result = allocate_stage_1(
            sealed, reviews, inspection_records(sealed, reviews)
        )

        self.assertEqual("complete", result["allocation"])
        self.assertIn(
            unseen_replacement_id,
            {
                item["candidate_id"]
                for item in cast(list[dict[str, object]], result["blind"])
            },
        )

    def test_large_invalid_blind_cell_stops_without_a_call_stack_failure(self) -> None:
        manifest, reviews = allocation_manifest()
        candidates = cast(list[dict[str, object]], manifest["candidates"])
        first_cell_ids = {
            str(review["candidate_id"])
            for review in reviews
            if str(review["candidate_id"]).startswith("blind-")
            and review["label"] == RESULT_LABELS[0]
        }
        first_cell = [
            candidate
            for candidate in candidates
            if candidate["candidate_id"] in first_cell_ids
            and candidate["aspect"] == STAGE_1_ASPECTS[0]
        ]
        for candidate in first_cell:
            candidate["event_group_id"] = "one-large-event"
        for index in range(25, 1_100):
            candidate_id = f"large-cell-{index:04d}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "event_group_id": "one-large-event",
                    "published_at": "2026-09-10T09:00:00Z",
                    "normalized_passage": f"Unique large-cell passage {index}.",
                    "near_duplicate_reviewed": True,
                    "company_id": f"large-cell-company-{index:04d}",
                    "aspect": STAGE_1_ASPECTS[0],
                }
            )
            reviews.append(
                {
                    "candidate_id": candidate_id,
                    "disposition": "accepted",
                    "label": RESULT_LABELS[0],
                    "labeled_at": "2026-09-11T00:00:00Z",
                }
            )
        sealed = seal_candidate_manifest(manifest, "fixture-owner")

        result = allocate_stage_1(
            sealed, reviews, inspection_records(sealed, reviews)
        )

        self.assertEqual("stopped", result["allocation"])
        self.assertEqual("blind-event-group-balance-failed", result["stop_reason"])

    def test_allocation_is_repeatable_for_the_same_review_records(self) -> None:
        manifest, reviews = allocation_manifest()
        sealed = seal_candidate_manifest(manifest, "fixture-owner")
        result = allocate_stage_1(
            sealed, reviews, inspection_records(sealed, reviews)
        )

        self.assertEqual("complete", result["allocation"])

    def test_blind_diversity_rules_stop_an_invalid_allocation(self) -> None:
        cases = {
            "too-few-event-groups": (
                lambda candidates: [
                    candidate.update(
                        event_group_id=f"blind-pair-{index // 2:03d}"
                    )
                    for index, candidate in enumerate(candidates)
                ],
                "blind-event-group-balance-failed",
            ),
            "too-many-for-event": (
                lambda candidates: [
                    candidate.update(event_group_id="blind-event-shared")
                    for candidate in candidates[:3]
                ],
                "blind-event-group-balance-failed",
            ),
            "too-many-for-company": (
                lambda candidates: [
                    candidate.update(company_id="unseen-shared")
                    for candidate in candidates[:6]
                ],
                "blind-company-balance-failed",
            ),
            "too-few-unseen-issuers": (
                lambda candidates: [
                    candidate.update(company_id=f"unseen-{index // 5:03d}")
                    for index, candidate in enumerate(candidates)
                ],
                "blind-unseen-issuer-balance-failed",
            ),
        }
        for name, (change, expected_reason) in cases.items():
            with self.subTest(name=name):
                manifest, reviews = allocation_manifest()
                blind_candidates = [
                    candidate
                    for candidate in cast(
                        list[dict[str, object]], manifest["candidates"]
                    )
                    if str(candidate["candidate_id"]).startswith("blind-")
                ]
                change(blind_candidates)
                sealed = seal_candidate_manifest(manifest, "fixture-owner")

                result = allocate_stage_1(
                    sealed, reviews, inspection_records(sealed, reviews)
                )

                self.assertEqual("stopped", result["allocation"])
                self.assertEqual(expected_reason, result["stop_reason"])


class VoteCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name)
        self.runner = StageRun(
            self.state_dir,
            clock=lambda: "2026-09-12T00:00:00Z",
        )

    def vote_inputs(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        stage_manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        candidates = candidate_manifest()
        candidates["candidates"] = [
            {
                "candidate_id": "silver-1",
                "event_group_id": "event-silver-1",
                "company_id": "Harbor Grid Ltd",
                "aspect": STAGE_1_ASPECTS[0],
                "published_at": "2026-03-10T09:00:00Z",
                "normalized_passage": "Harbor Grid revenue increased by ten percent.",
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "development-1",
                "event_group_id": "event-development-1",
                "company_id": "Harbor Grid Ltd",
                "aspect": STAGE_1_ASPECTS[1],
                "published_at": "2026-07-10T09:00:00Z",
                "normalized_passage": "Harbor Grid won three new supply contracts.",
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "blind-1",
                "event_group_id": "event-blind-1",
                "company_id": "Harbor Grid Ltd",
                "aspect": STAGE_1_ASPECTS[2],
                "published_at": "2026-09-10T09:00:00Z",
                "normalized_passage": "Harbor Grid opened a new factory.",
                "near_duplicate_reviewed": True,
            },
        ]
        sealed_candidates = seal_candidate_manifest(candidates, "fixture-owner")
        allocation = {
            "allocation": "complete",
            "stop_reason": None,
            "candidate_manifest_sha256": cast(
                Mapping[str, object], sealed_candidates["seal"]
            )["semantic_sha256"],
            "training": [{"candidate_id": "silver-1"}],
            "development": [{"candidate_id": "development-1"}],
            "blind": [{"candidate_id": "blind-1"}],
        }
        return stage_manifest, sealed_candidates, allocation

    def test_each_frozen_route_votes_on_silver_and_development_only(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        transport = FixedVoteTransport()

        result = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            transport,
            timeout_seconds=30,
        )

        self.assertEqual("complete", result["collection"])
        self.assertEqual(6, result["raw_vote_count"])
        self.assertEqual(list(ROUTE_IDS), result["frozen_route_ids"])
        self.assertEqual(6, len(transport.requests))
        self.assertNotIn(
            "blind-1",
            {
                request["user"]
                for request, _ in transport.requests
            },
        )
        for request, timeout_seconds in transport.requests:
            self.assertIn(request["model"], ROUTE_IDS)
            self.assertNotIn("combo", request)
            self.assertFalse(request["stream"])
            self.assertEqual(30, timeout_seconds)
        records = self.runner.raw_vote_records()
        self.assertEqual(6, len(records))
        self.assertEqual({"valid"}, {record["outcome"] for record in records})
        self.assertEqual({"positive"}, {record["label"] for record in records})
        for record in records:
            self.assertTrue(record["prompt"])
            self.assertEqual(64, len(record["request_sha256"]))
            self.assertEqual(64, len(record["response_sha256"]))
            self.assertEqual(96, record["token_use"]["total_tokens"])  # type: ignore[index]
            self.assertEqual("0.0000000000", record["cost"]["response_cost_usd"])  # type: ignore[index]
            self.assertEqual("2026-09-12T00:00:00Z", record["recorded_at"])

    def response(
        self,
        *,
        content: str = '{"label":"positive"}',
        model: str = "mistral-medium-3-5",
        status_code: int = 200,
        refusal: str | None = None,
    ) -> OmniRouteResponse:
        message: dict[str, object] = {"content": content}
        if refusal is not None:
            message["refusal"] = refusal
        return OmniRouteResponse(
            status_code=status_code,
            headers={
                "x-omniroute-response-cost": "0.0000000000",
                "x-omniroute-tokens-in": "91",
                "x-omniroute-tokens-out": "5",
                "x-omniroute-model": model,
                "x-omniroute-provider": "mistral",
                "x-omniroute-latency-ms": "125",
                "x-omniroute-cache-hit": "false",
                "x-omniroute-fallback-attempts": "0",
                "x-omniroute-decision": (
                    "strategy=single; provider=mistral; latency_ms=125"
                ),
                "x-omniroute-request-id": "request-first",
                "x-omniroute-version": "3.8.49",
            },
            body={
                "model": model,
                "choices": [{"message": message}],
                "usage": {
                    "prompt_tokens": 91,
                    "completion_tokens": 5,
                    "total_tokens": 96,
                },
            },
        )

    def test_failures_and_substitution_are_abstentions(self) -> None:
        cases: dict[str, OmniRouteResponse | BaseException] = {
            "refusal": self.response(refusal="I cannot classify this passage."),
            "malformed-answer": self.response(content="positive"),
            "timeout": TimeoutError("The route timed out."),
            "route-substitution": self.response(
                content='{ "label": "insufficient evidence" }',
                model="substituted-model",
            ),
        }
        for expected_reason, first_response in cases.items():
            with self.subTest(reason=expected_reason):
                with tempfile.TemporaryDirectory() as state_dir:
                    runner = StageRun(
                        state_dir,
                        clock=lambda: "2026-09-12T00:00:00Z",
                    )
                    stage_manifest, candidates, allocation = self.vote_inputs()

                    result = runner.collect_votes(
                        stage_manifest,
                        candidates,
                        allocation,
                        SequenceVoteTransport(first_response),
                    )

                    self.assertEqual("complete", result["collection"])
                    first_vote = runner.raw_vote_records()[0]
                    self.assertEqual("abstention", first_vote["outcome"])
                    self.assertEqual(expected_reason, first_vote["abstention_reason"])
                    self.assertIsNone(first_vote["label"])

    def test_free_limit_failure_is_recorded_and_stops_collection(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        transport = SequenceVoteTransport(
            self.response(content="", status_code=429)
        )

        result = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            transport,
        )

        self.assertEqual("stopped", result["collection"])
        self.assertEqual("free-limit-failure", result["stop_reason"])
        self.assertEqual(1, len(transport.requests))
        self.assertEqual(1, result["raw_vote_count"])
        vote = self.runner.raw_vote_records()[0]
        self.assertEqual("abstention", vote["outcome"])
        self.assertEqual("free-limit", vote["abstention_reason"])
        self.assertNotEqual("insufficient evidence", vote["label"])

    def test_automatic_or_bare_route_cannot_enter_the_frozen_set(self) -> None:
        for invalid_route_id in ("auto", "fusion/free", "provider/latest"):
            with self.subTest(route_id=invalid_route_id):
                with tempfile.TemporaryDirectory() as state_dir:
                    manifest = draft_manifest()
                    manifest["route_panel"]["routes"].append(  # type: ignore[index]
                        route(invalid_route_id)
                    )
                    runner = StageRun(state_dir)

                    decision = runner.evaluate(
                        confirm_manifest(manifest, "fixture-owner")
                    )

                    self.assertEqual("no-build", decision["decision"])
                    self.assertEqual("route-panel-incomplete", decision["stop_reason"])

    def test_routing_and_cache_telemetry_failures_are_abstentions(self) -> None:
        response = self.response()
        cases = {
            "route-substitution": {
                "x-omniroute-decision": (
                    "strategy=fallback; provider=mistral; latency_ms=125"
                )
            },
            "cache-hit": {"x-omniroute-cache-hit": "true"},
        }
        for expected_reason, changed_headers in cases.items():
            with self.subTest(reason=expected_reason):
                with tempfile.TemporaryDirectory() as state_dir:
                    runner = StageRun(
                        state_dir, clock=lambda: "2026-09-12T00:00:00Z"
                    )
                    stage_manifest, candidates, allocation = self.vote_inputs()
                    headers = dict(response.headers)
                    headers.update(changed_headers)

                    runner.collect_votes(
                        stage_manifest,
                        candidates,
                        allocation,
                        SequenceVoteTransport(response._replace(headers=headers)),
                    )

                    vote = runner.raw_vote_records()[0]
                    self.assertEqual("abstention", vote["outcome"])
                    self.assertEqual(expected_reason, vote["abstention_reason"])
                    self.assertIsNone(vote["label"])

    def test_a_free_limit_vote_is_collected_again_after_the_reset(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()

        stopped = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            SequenceVoteTransport(self.response(content="", status_code=429)),
        )
        self.assertEqual("free-limit-failure", stopped["stop_reason"])

        transport = FixedVoteTransport()
        result = self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        self.assertEqual("complete", result["collection"])
        self.assertEqual(6, len(transport.requests))
        valid = [
            record
            for record in self.runner.raw_vote_records()
            if record["outcome"] == "valid"
        ]
        self.assertEqual(6, len(valid))

    def test_a_cloudflare_free_limit_error_body_stops_collection(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        response = self.response(status_code=403)
        transport = SequenceVoteTransport(
            response._replace(
                body={
                    "errors": [
                        {"code": 3040, "message": "Account limit reached"}
                    ]
                }
            )
        )

        result = self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        self.assertEqual("free-limit-failure", result["stop_reason"])
        vote = self.runner.raw_vote_records()[0]
        self.assertEqual("free-limit", vote["abstention_reason"])

    def test_a_network_failure_is_an_abstention(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()

        result = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            SequenceVoteTransport(OSError("The OmniRoute request failed.")),
        )

        self.assertEqual("complete", result["collection"])
        vote = self.runner.raw_vote_records()[0]
        self.assertEqual("abstention", vote["outcome"])
        self.assertEqual("transport-error", vote["abstention_reason"])

    def test_a_malformed_fallback_header_is_an_abstention(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        response = self.response()
        headers = dict(response.headers)
        headers["x-omniroute-fallback-attempts"] = "unknown"

        result = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            SequenceVoteTransport(response._replace(headers=headers)),
        )

        self.assertEqual("complete", result["collection"])
        vote = self.runner.raw_vote_records()[0]
        self.assertEqual("route-substitution", vote["abstention_reason"])

    def test_a_changed_request_template_stops_collection(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        self.runner.collect_votes(
            stage_manifest, candidates, allocation, FixedVoteTransport()
        )

        with unittest.mock.patch(
            "nlp_wayfinder.stage_run.LABELING_SYSTEM_PROMPT", "Other instructions."
        ):
            changed = self.runner.collect_votes(
                stage_manifest, candidates, allocation, FixedVoteTransport()
            )

        self.assertEqual("frozen-vote-collection-changed", changed["stop_reason"])
        freeze = self.runner.vote_collection_records()[0]
        self.assertEqual(sorted(ROUTE_IDS), freeze["route_ids"])

    def test_transport_uses_the_dedicated_provider_endpoint(self) -> None:
        sent: dict[str, Any] = {}

        class Response:
            status = 200
            headers = {"x-omniroute-model": "qwen/qwen3.6-27b"}

            def read(self) -> bytes:
                return b"{}"

            def __enter__(self) -> Response:
                return self

            def __exit__(self, *exception: object) -> None:
                return None

        def fake_urlopen(request: Any, timeout: float) -> Response:
            sent["url"] = request.full_url
            sent["headers"] = dict(request.headers)
            sent["body"] = json.loads(request.data)
            return Response()

        transport = OmniRouteHttpTransport("http://127.0.0.1:20128/")
        with unittest.mock.patch(
            "nlp_wayfinder.stage_run.urllib.request.urlopen", fake_urlopen
        ):
            transport.complete({"model": "groq/qwen/qwen3.6-27b"}, 30)

        self.assertEqual(
            "http://127.0.0.1:20128/v1/providers/groq/chat/completions",
            sent["url"],
        )
        self.assertEqual("qwen/qwen3.6-27b", sent["body"]["model"])
        headers = {key.lower(): value for key, value in sent["headers"].items()}
        self.assertEqual("true", headers["x-omniroute-no-cache"])
        self.assertEqual("true", headers["x-omniroute-no-memory"])

    def test_paid_overflow_is_an_abstention_and_stops_collection(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        response = self.response()
        paid_headers = dict(response.headers)
        paid_headers["x-omniroute-response-cost"] = "0.0001000000"
        transport = SequenceVoteTransport(response._replace(headers=paid_headers))

        result = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            transport,
        )

        self.assertEqual("stopped", result["collection"])
        self.assertEqual("paid-overflow-detected", result["stop_reason"])
        self.assertEqual(1, len(transport.requests))
        vote = self.runner.raw_vote_records()[0]
        self.assertEqual("abstention", vote["outcome"])
        self.assertEqual("paid-overflow", vote["abstention_reason"])


class SilverAggregationTests(unittest.TestCase):
    """Aggregate the collected votes into calibrated accepted silver labels."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runner = StageRun(
            Path(self.temp_dir.name),
            clock=lambda: "2026-09-12T00:00:00Z",
        )
        self.stage_manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        self.candidates = seal_candidate_manifest(
            candidate_manifest(), "fixture-owner"
        )
        self.development = [
            {
                "candidate_id": f"development-{index:04d}",
                "label": RESULT_LABELS[index % 4],
            }
            for index in range(200)
        ]

    def allocation(self, training_ids: list[str]) -> dict[str, object]:
        return {
            "allocation": "complete",
            "stop_reason": None,
            "candidate_manifest_sha256": cast(
                Mapping[str, object], self.candidates["seal"]
            )["semantic_sha256"],
            "training": [{"candidate_id": item} for item in training_ids],
            "development": self.development,
            "blind": [],
        }

    def add_votes(self, candidate_id: str, labels: Mapping[str, str]) -> None:
        for route_id, label in labels.items():
            self.runner._raw_vote_log.append(
                {
                    "event": "raw-vote",
                    "candidate_id": candidate_id,
                    "requested_route_id": route_id,
                    "outcome": "valid",
                    "label": label,
                }
            )

    def add_development_votes(self, *, noisy_routes: int = 0) -> None:
        """Vote on every development example. The first routes can be unreliable."""
        for index, item in enumerate(self.development):
            gold = str(item["label"])
            gold_index = RESULT_LABELS.index(gold)
            self.add_votes(
                str(item["candidate_id"]),
                {
                    route_id: RESULT_LABELS[
                        (gold_index + 1 + (index + position) % 3) % 4
                    ]
                    if position < noisy_routes and (index + position) % 5 < 2
                    else gold
                    for position, route_id in enumerate(ROUTE_IDS)
                },
            )

    def aggregate(self, training_ids: list[str]) -> dict[str, object]:
        return self.runner.aggregate_silver_labels(
            self.stage_manifest, self.candidates, self.allocation(training_ids)
        )

    def test_agreed_votes_become_one_accepted_silver_label(self) -> None:
        self.add_development_votes()
        self.add_votes("silver-1", dict.fromkeys(ROUTE_IDS, "positive"))

        result = self.aggregate(["silver-1"])

        self.assertEqual("complete", result["aggregation"])
        self.assertIsNone(result["stop_reason"])
        self.assertEqual(1, result["accepted_silver_count"])
        accepted = cast(list[Mapping[str, object]], result["accepted_silver"])[0]
        self.assertEqual("silver-1", accepted["candidate_id"])
        self.assertEqual("positive", accepted["label"])
        self.assertGreaterEqual(
            cast(float, accepted["probability"]), SILVER_MIN_PROBABILITY
        )
        self.assertEqual(64, len(cast(str, result["aggregation_sha256"])))

    def test_the_sealed_fit_keeps_one_four_by_four_matrix_for_each_voter(self) -> None:
        self.add_development_votes(noisy_routes=1)
        self.add_votes("silver-1", dict.fromkeys(ROUTE_IDS, "positive"))

        result = self.aggregate(["silver-1"])

        records = self.runner.silver_aggregation_records()
        fit = next(item for item in records if item["event"] == "silver-fit-sealed")
        posteriors = next(
            item for item in records if item["event"] == "silver-posteriors-sealed"
        )
        self.assertEqual("1.4.2", fit["crowd_kit_version"])
        self.assertEqual(100, fit["n_iter"])
        self.assertEqual(1e-8, fit["tol"])
        self.assertEqual(0, fit["route_dependency_parameter_count"])
        self.assertEqual("20260905", fit["calibration_seed"])
        self.assertEqual(SILVER_CALIBRATION_FOLDS, fit["calibration_folds"])
        self.assertEqual(
            SILVER_CALIBRATION_FOLDS, len(cast(list[float], fit["fold_temperatures"]))
        )
        matrices = cast(Mapping[str, Mapping[str, Mapping[str, float]]], fit["confusion_matrices"])
        self.assertEqual(set(ROUTE_IDS), set(matrices))
        for matrix in matrices.values():
            self.assertEqual(set(RESULT_LABELS), set(matrix))
            for row in matrix.values():
                self.assertEqual(set(RESULT_LABELS), set(row))
        self.assertEqual(
            200, len(cast(Mapping[str, object], posteriors["development_out_of_fold"]))
        )
        self.assertEqual(
            64, len(cast(str, result["fit_sha256"]))
        )
        self.assertEqual(64, len(cast(str, result["posterior_sha256"])))

    def test_a_route_that_always_abstains_keeps_its_matrix(self) -> None:
        for item in self.development:
            gold = str(item["label"])
            self.add_votes(
                str(item["candidate_id"]),
                {ROUTE_IDS[0]: gold, ROUTE_IDS[1]: gold},
            )
        self.add_votes("silver-1", dict.fromkeys(ROUTE_IDS[:2], "positive"))

        self.aggregate(["silver-1"])

        fit = next(
            item
            for item in self.runner.silver_aggregation_records()
            if item["event"] == "silver-fit-sealed"
        )
        matrices = cast(Mapping[str, object], fit["confusion_matrices"])
        self.assertEqual(set(ROUTE_IDS), set(matrices))

    def test_an_abstention_is_a_missing_vote(self) -> None:
        self.add_development_votes()
        self.runner._raw_vote_log.append(
            {
                "event": "raw-vote",
                "candidate_id": "silver-1",
                "requested_route_id": ROUTE_IDS[1],
                "outcome": "abstention",
                "abstention_reason": "refusal",
                "label": None,
            }
        )
        self.add_votes("silver-1", {ROUTE_IDS[0]: "positive"})

        result = self.aggregate(["silver-1"])

        self.assertEqual(0, result["accepted_silver_count"])
        self.assertEqual({"insufficient-votes": 1}, result["rejected_counts"])

    def test_a_split_vote_has_no_strict_majority(self) -> None:
        self.add_development_votes(noisy_routes=2)
        self.add_votes(
            "silver-1",
            {
                ROUTE_IDS[0]: "positive",
                ROUTE_IDS[1]: "neutral",
                ROUTE_IDS[2]: "negative",
            },
        )

        result = self.aggregate(["silver-1"])

        self.assertEqual({"no-strict-majority": 1}, result["rejected_counts"])

    def test_an_unsure_posterior_is_below_the_confidence_floor(self) -> None:
        unsure = {
            "positive": 0.60,
            "neutral": 0.30,
            "negative": 0.06,
            "insufficient evidence": 0.04,
        }

        self.assertEqual(
            "low-confidence",
            _silver_rejection(["positive", "positive", "neutral"], unsure),
        )
        self.assertLess(unsure["positive"], SILVER_MIN_PROBABILITY)

    def test_a_thin_development_class_stops_the_source(self) -> None:
        self.development = [
            {"candidate_id": f"development-{index:04d}", "label": RESULT_LABELS[index % 3]}
            for index in range(24)
        ]
        self.add_development_votes()

        result = self.aggregate(["silver-1"])

        self.assertEqual("stopped", result["aggregation"])
        self.assertEqual("development-class-underfilled", result["stop_reason"])
        self.assertEqual([], self.runner.silver_aggregation_records())

    def test_an_incomplete_allocation_stops_the_aggregation(self) -> None:
        allocation = self.allocation(["silver-1"])
        allocation["allocation"] = "stopped"

        result = self.runner.aggregate_silver_labels(
            self.stage_manifest, self.candidates, allocation
        )

        self.assertEqual("allocation-not-complete", result["stop_reason"])

    def test_a_changed_fit_cannot_replace_the_sealed_fit(self) -> None:
        self.add_development_votes()
        self.add_votes("silver-1", dict.fromkeys(ROUTE_IDS, "positive"))
        self.aggregate(["silver-1"])
        self.add_votes("silver-2", dict.fromkeys(ROUTE_IDS, "negative"))

        result = self.aggregate(["silver-1", "silver-2"])

        self.assertEqual("stopped", result["aggregation"])
        self.assertEqual("frozen-aggregation-changed", result["stop_reason"])

    def test_the_calibration_fold_is_fixed_by_the_seed(self) -> None:
        folds = [_calibration_fold(f"development-{index:04d}") for index in range(200)]

        self.assertEqual(
            folds, [_calibration_fold(f"development-{index:04d}") for index in range(200)]
        )
        self.assertEqual(set(range(SILVER_CALIBRATION_FOLDS)), set(folds))

    def test_a_close_posterior_is_a_tie(self) -> None:
        tied = {
            "positive": 0.5,
            "neutral": 0.5 - 1e-13,
            "negative": 0.0,
            "insufficient evidence": 0.0,
        }

        self.assertEqual(
            "posterior-tie",
            _silver_rejection(["positive", "positive", "neutral"], tied),
        )

    def test_a_majority_for_another_class_does_not_support_the_top_class(self) -> None:
        calibrated = {
            "positive": 0.9,
            "neutral": 0.1,
            "negative": 0.0,
            "insufficient evidence": 0.0,
        }

        self.assertEqual(
            "top-class-unsupported",
            _silver_rejection(["neutral", "neutral", "positive"], calibrated),
        )
        self.assertIsNone(
            _silver_rejection(["positive", "positive", "neutral"], calibrated)
        )



if __name__ == "__main__":
    unittest.main()
