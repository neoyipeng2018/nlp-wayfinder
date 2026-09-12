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
from typing import Any, Mapping, Sequence, cast

from nlp_wayfinder.stage_run import (
    BLIND_RELABEL_SEED,
    BLIND_RELABEL_TARGET,
    MAX_EXAMPLE_TOKENS,
    MODERNBERT_MODEL_ID,
    MODERNBERT_REVISION,
    SILVER_CALIBRATION_FOLDS,
    SILVER_MIN_PROBABILITY,
    SOURCE_ALLOCATION_TARGETS,
    SOURCE_SILVER_CANDIDATE_LIMITS,
    STAGE_SOURCES,
    OmniRouteHttpTransport,
    RESULT_LABELS,
    RIGHTS_FIELDS,
    STAGE_1_ASPECTS,
    VOTE_CONFIDENCE_BANDS,
    VOTE_FIELDS,
    VOTE_MAX_OUTPUT_TOKENS,
    VOTE_REASON_CODES,
    CostLimitError,
    OmniRouteResponse,
    StageRun,
    admit_example,
    allocate_source,
    main as stage_run_main,
    project_gpt_blind_cost,
    project_specialist_training_cost,
    _calibration_fold,
    _silver_rejection,
    candidate_order_sha256,
    cumulative_sources,
    seal_candidate_manifest,
    confirm_manifest,
)


ROUTE_IDS = (
    "mistral/mistral-medium-3-5",
    "cf/@cf/zai-org/glm-4.7-flash",
    "groq/qwen/qwen3.6-27b",
)


SILVER_PASSAGE = "Harbor Grid revenue increased by ten percent."


def vote_content(
    passage: str,
    *,
    label: str = "positive",
    confidence_band: str = "high",
    reason_code: str = "favorable evidence",
    **changed: object,
) -> str:
    """Build one full auditable vote whose evidence is the complete passage."""
    vote: dict[str, object] = {
        "label": label,
        "confidence_band": confidence_band,
        "evidence_start": 0,
        "evidence_end": len(passage),
        "evidence_text": passage,
        "reason_code": reason_code,
    }
    vote.update(changed)
    return json.dumps(vote)


def request_passage(request: Mapping[str, object]) -> str:
    messages = cast(Sequence[Mapping[str, str]], request["messages"])
    return str(json.loads(messages[1]["content"])["passage"])


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
        self.bodies: dict[str, bytes] = {}

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
                {"message": {"content": vote_content(request_passage(request))}}
            ],
            "usage": {
                "prompt_tokens": 91,
                "completion_tokens": 5,
                "total_tokens": 96,
            },
        }
        raw_body = json.dumps(body, indent=1).encode("utf-8")
        self.bodies[f"request-{len(self.requests)}"] = raw_body
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
            raw_body=raw_body,
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


class ScriptedVoteTransport(FixedVoteTransport):
    """Answer from a fixed script, then fall back to the valid response."""

    def __init__(self, *scripted: OmniRouteResponse) -> None:
        super().__init__()
        self.scripted = list(scripted)

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        if not self.scripted:
            return super().complete(request, timeout_seconds)
        self.requests.append((copy.deepcopy(dict(request)), timeout_seconds))
        return self.scripted.pop(0)


class MalformedVoteTransport(FixedVoteTransport):
    """Answer every fixed route with a bare label that no schema accepts."""

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        response = super().complete(request, timeout_seconds)
        body = copy.deepcopy(dict(response.body))
        body["choices"] = [{"message": {"content": "positive"}}]
        return response._replace(body=body)


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


def company_record(company_id: str) -> dict[str, object]:
    """Give the verified public company record for one company ID."""
    return {
        "name": f"{company_id} Ltd",
        "ticker": company_id.upper().replace(" ", "")[:8],
        "exchange": "LSE",
        "publicly_traded": True,
    }


def candidate_manifest(
    stage: int = 1, source: str = "financial-news"
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "stage": stage,
        "source": source,
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
                "silver_candidate_limit": SOURCE_SILVER_CANDIDATE_LIMITS[source],
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
                "company_id": "harbor-grid",
                "company": company_record("harbor-grid"),
            },
            {
                "candidate_id": "candidate-a",
                "event_group_id": "event-a",
                "published_at": "2026-03-10T09:00:00Z",
                "normalized_passage": "Harbor Grid opened its first plant.",
                "near_duplicate_reviewed": True,
                "company_id": "harbor-grid",
                "company": company_record("harbor-grid"),
            },
        ],
    }


def allocation_manifest(
    stage: int = 1, source: str = "financial-news"
) -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest = candidate_manifest(stage, source)
    targets = SOURCE_ALLOCATION_TARGETS[source]
    prefix = "" if source == "financial-news" else f"{source}-"
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
        candidate_id = f"{prefix}{split}-{index:04d}"
        candidates.append(
            {
                "candidate_id": candidate_id,
                "event_group_id": event_group_id,
                "published_at": published_at,
                "normalized_passage": f"Unique passage for {candidate_id}.",
                "near_duplicate_reviewed": True,
                "company_id": company_id,
                "company": company_record(company_id),
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

    for index in range(targets["training"]):
        add_candidate(
            "training",
            index,
            f"{prefix}seen-{index // 5:04d}",
            STAGE_1_ASPECTS[index % 4],
            RESULT_LABELS[index % 4],
            f"{prefix}training-event-{index:04d}",
        )
    for index in range(200):
        add_candidate(
            "development",
            index,
            f"{prefix}development-{index // 5:04d}",
            STAGE_1_ASPECTS[index % 4],
            RESULT_LABELS[index % 4],
            f"{prefix}development-event-{index:04d}",
        )
    blind_index = 0
    for aspect in STAGE_1_ASPECTS:
        for label in RESULT_LABELS:
            for _ in range(25):
                add_candidate(
                    "blind",
                    blind_index,
                    f"{prefix}unseen-{blind_index // 4:03d}",
                    aspect,
                    label,
                    f"{prefix}blind-event-{blind_index:04d}",
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
        self.assertEqual(
            "financial-news-fixture",
            evidence["sources"]["financial-news"]["source_id"],
        )
        self.assertEqual(list(ROUTE_IDS), evidence["routes"]["eligible_route_ids"])
        self.assertEqual(7, evidence["schedule"]["financial-news"]["required_days"])
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
            allocate_source(sealed, reviews, [])

    def test_complete_allocation_has_fixed_quotas_balance_and_relabel_sample(
        self,
    ) -> None:
        manifest, reviews = allocation_manifest()
        sealed = seal_candidate_manifest(
            manifest,
            "fixture-owner",
            sealed_at="2026-09-10T00:00:00Z",
        )

        result = allocate_source(sealed, reviews, inspection_records(sealed, reviews))

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
                    "company": company_record(f"seen-{index // 5:04d}"),
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
        result = allocate_source(
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
                "company": company_record("unseen-replacement"),
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

        result = allocate_source(sealed, reviews, inspection_records(sealed, reviews))

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
            candidate["company"] = company_record("unseen-shared")
        candidates.append(
            {
                "candidate_id": "blind-balance-replacement",
                "event_group_id": "blind-balance-replacement-event",
                "published_at": "2026-09-10T09:00:00Z",
                "normalized_passage": "Unique balance replacement passage.",
                "near_duplicate_reviewed": True,
                "company_id": "unseen-balance-replacement",
                "company": company_record("unseen-balance-replacement"),
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

        result = allocate_source(
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
            candidate["company"] = company_record(f"single-{index}")
        for index, candidate in enumerate(other_blind):
            candidate["company_id"] = f"unseen-{index % 97}"
            candidate["company"] = company_record(f"unseen-{index % 97}")

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
                    "company": company_record(company_id),
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

        result = allocate_source(
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
                    "company": company_record(f"large-cell-company-{index:04d}"),
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

        result = allocate_source(
            sealed, reviews, inspection_records(sealed, reviews)
        )

        self.assertEqual("stopped", result["allocation"])
        self.assertEqual("blind-event-group-balance-failed", result["stop_reason"])

    def test_allocation_is_repeatable_for_the_same_review_records(self) -> None:
        manifest, reviews = allocation_manifest()
        sealed = seal_candidate_manifest(manifest, "fixture-owner")
        result = allocate_source(
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
                    candidate.update(
                        company_id="unseen-shared",
                        company=company_record("unseen-shared"),
                    )
                    for candidate in candidates[:6]
                ],
                "blind-company-balance-failed",
            ),
            "too-few-unseen-issuers": (
                lambda candidates: [
                    candidate.update(
                        company_id=f"unseen-{index // 5:03d}",
                        company=company_record(f"unseen-{index // 5:03d}"),
                    )
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

                result = allocate_source(
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
                "company": company_record("Harbor Grid Ltd"),
                "aspect": STAGE_1_ASPECTS[0],
                "published_at": "2026-03-10T09:00:00Z",
                "normalized_passage": SILVER_PASSAGE,
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "development-1",
                "event_group_id": "event-development-1",
                "company_id": "Harbor Grid Ltd",
                "company": company_record("Harbor Grid Ltd"),
                "aspect": STAGE_1_ASPECTS[1],
                "published_at": "2026-07-10T09:00:00Z",
                "normalized_passage": "Harbor Grid won three new supply contracts.",
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "blind-1",
                "event_group_id": "event-blind-1",
                "company_id": "Harbor Grid Ltd",
                "company": company_record("Harbor Grid Ltd"),
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
        content: str = vote_content(SILVER_PASSAGE),
        model: str = "mistral-medium-3-5",
        status_code: int = 200,
        refusal: str | None = None,
    ) -> OmniRouteResponse:
        message: dict[str, object] = {"content": content}
        if refusal is not None:
            message["refusal"] = refusal
        body = {
            "model": model,
            "choices": [{"message": message}],
            "usage": {
                "prompt_tokens": 91,
                "completion_tokens": 5,
                "total_tokens": 96,
            },
        }
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
            body=body,
            raw_body=json.dumps(body, indent=1).encode("utf-8"),
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

    def test_a_malformed_answer_earns_one_identical_repair_attempt(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        transport = SequenceVoteTransport(self.response(content="positive"))

        result = self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        self.assertEqual("complete", result["collection"])
        self.assertEqual(7, len(transport.requests))
        self.assertEqual(transport.requests[0][0], transport.requests[1][0])
        records = self.runner.raw_vote_records()
        self.assertEqual(7, len(records))
        first, repair = records[0], records[1]
        self.assertEqual(0, first["retry_ordinal"])
        self.assertEqual("malformed-answer", first["abstention_reason"])
        self.assertEqual(1, repair["retry_ordinal"])
        self.assertEqual(first["requested_route_id"], repair["requested_route_id"])
        self.assertEqual(first["candidate_id"], repair["candidate_id"])
        self.assertEqual(first["request_sha256"], repair["request_sha256"])
        self.assertEqual("valid", repair["outcome"])
        # Only the final attempt votes, so each route still counts once.
        votes = self.runner._valid_votes()[str(first["candidate_id"])]
        self.assertEqual(sorted(ROUTE_IDS), sorted(votes))

    def test_one_repair_attempt_is_the_limit_across_runs(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, MalformedVoteTransport()
        )
        again = self.runner.collect_votes(
            stage_manifest, candidates, allocation, FixedVoteTransport()
        )

        self.assertEqual("complete", again["collection"])
        # The repaired route keeps its two attempts and earns no third one.
        counted = Counter(
            (record["candidate_id"], record["requested_route_id"])
            for record in self.runner.raw_vote_records()
        )
        self.assertEqual({2}, set(counted.values()))
        repaired = [
            record
            for record in self.runner.raw_vote_records()
            if record["abstention_reason"] == "malformed-answer"
        ]
        self.assertEqual(
            [0, 1] * 6, [record["retry_ordinal"] for record in repaired]
        )

    def test_a_free_limit_repair_keeps_one_ordinal_for_each_attempt(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()

        stopped = self.runner.collect_votes(
            stage_manifest,
            candidates,
            allocation,
            ScriptedVoteTransport(
                self.response(content="positive"),
                self.response(content="", status_code=429),
            ),
        )
        again = self.runner.collect_votes(
            stage_manifest, candidates, allocation, FixedVoteTransport()
        )

        self.assertEqual("free-limit-failure", stopped["stop_reason"])
        self.assertEqual("complete", again["collection"])
        repaired = [
            record
            for record in self.runner.raw_vote_records()
            if record["candidate_id"] == "silver-1"
            and record["requested_route_id"] == ROUTE_IDS[0]
        ]
        self.assertEqual([0, 1, 2], [record["retry_ordinal"] for record in repaired])
        self.assertEqual(
            ["malformed-answer", "free-limit", None],
            [record["abstention_reason"] for record in repaired],
        )
        # The free-limit attempt spends no repair, so the vote still arrives.
        self.assertEqual("valid", repaired[-1]["outcome"])

    def test_other_abstentions_earn_no_repair_attempt(self) -> None:
        cases: dict[str, OmniRouteResponse | BaseException] = {
            "refusal": self.response(refusal="I cannot classify this passage."),
            "timeout": TimeoutError("The route timed out."),
            "route-substitution": self.response(model="substituted-model"),
            "cache-hit": self.response()._replace(
                headers={
                    **self.response().headers,
                    "x-omniroute-cache-hit": "true",
                }
            ),
        }
        for expected_reason, first_response in cases.items():
            with self.subTest(reason=expected_reason):
                with tempfile.TemporaryDirectory() as state_dir:
                    runner = StageRun(state_dir, clock=lambda: "2026-09-12T00:00:00Z")
                    stage_manifest, candidates, allocation = self.vote_inputs()
                    transport = SequenceVoteTransport(first_response)

                    runner.collect_votes(
                        stage_manifest, candidates, allocation, transport
                    )

                    records = runner.raw_vote_records()
                    self.assertEqual(6, len(records))
                    self.assertEqual(6, len(transport.requests))
                    self.assertEqual(expected_reason, records[0]["abstention_reason"])
                    self.assertEqual(0, records[0]["retry_ordinal"])

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

    def test_a_changed_vote_schema_stops_collection(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        self.runner.collect_votes(
            stage_manifest, candidates, allocation, FixedVoteTransport()
        )

        with unittest.mock.patch(
            "nlp_wayfinder.stage_run.VOTE_REASON_CODES",
            (*VOTE_REASON_CODES, "other"),
        ):
            changed = self.runner.collect_votes(
                stage_manifest, candidates, allocation, FixedVoteTransport()
            )

        self.assertEqual("frozen-vote-collection-changed", changed["stop_reason"])

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

    def test_each_raw_vote_keeps_the_original_response_bytes(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        transport = FixedVoteTransport()

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        records = self.runner.raw_vote_records()
        self.assertEqual(6, len(records))
        for record in records:
            raw_body = transport.bodies[record["transport"]["request_id"]]  # type: ignore[index]
            self.assertEqual(
                hashlib.sha256(raw_body).hexdigest(), record["raw_body_sha256"]
            )
            self.assertNotEqual(record["raw_body_sha256"], record["response_sha256"])
            pointer = Path(self.temp_dir.name) / str(record["raw_body_pointer"])
            self.assertEqual(raw_body, pointer.read_bytes())

    def test_a_refused_response_keeps_its_raw_body(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        refused = self.response(content="", refusal="I cannot help with that.")
        transport = SequenceVoteTransport(refused)

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        record = self.runner.raw_vote_records()[0]
        self.assertEqual("refusal", record["abstention_reason"])
        pointer = Path(self.temp_dir.name) / str(record["raw_body_pointer"])
        self.assertEqual(refused.raw_body, pointer.read_bytes())

    def test_a_malformed_response_keeps_its_raw_body(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        malformed = self.response(content="not an answer")
        transport = SequenceVoteTransport(malformed)

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        record = self.runner.raw_vote_records()[0]
        self.assertEqual("malformed-answer", record["abstention_reason"])
        pointer = Path(self.temp_dir.name) / str(record["raw_body_pointer"])
        self.assertEqual(malformed.raw_body, pointer.read_bytes())

    def test_the_transport_keeps_the_bytes_of_a_response_that_is_not_json(
        self,
    ) -> None:
        def transport_for(payload: bytes) -> OmniRouteResponse:
            class Response:
                status = 200
                headers = {"x-omniroute-model": "qwen/qwen3.6-27b"}

                def read(self) -> bytes:
                    return payload

                def __enter__(self) -> Response:
                    return self

                def __exit__(self, *exception: object) -> None:
                    return None

            transport = OmniRouteHttpTransport("http://127.0.0.1:20128/")
            with unittest.mock.patch(
                "nlp_wayfinder.stage_run.urllib.request.urlopen",
                lambda request, timeout: Response(),
            ):
                return transport.complete({"model": "groq/qwen/qwen3.6-27b"}, 30)

        broken = transport_for(b'{"label": ')
        valid = transport_for(b'{"label":"positive"}')

        self.assertEqual(b'{"label": ', broken.raw_body)
        self.assertEqual(
            hashlib.sha256(b'{"label": ').hexdigest(),
            hashlib.sha256(broken.raw_body).hexdigest(),
        )
        self.assertEqual(b'{"label":"positive"}', valid.raw_body)

    def test_two_bodies_that_parse_the_same_keep_different_raw_hashes(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        compact = self.response()
        spaced = compact._replace(
            raw_body=json.dumps(dict(compact.body), indent=2).encode("utf-8")
        )

        class TwoEncodingsTransport:
            """Return one parsed body twice, with two different byte forms."""

            def __init__(self) -> None:
                self.responses = [compact, spaced]

            def complete(
                self, request: Mapping[str, object], timeout_seconds: float
            ) -> OmniRouteResponse:
                return self.responses.pop(0) if self.responses else compact

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, TwoEncodingsTransport()
        )

        first, second = self.runner.raw_vote_records()[:2]
        self.assertEqual(first["response_sha256"], second["response_sha256"])
        self.assertNotEqual(first["raw_body_sha256"], second["raw_body_sha256"])

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


    def test_the_vote_request_holds_the_full_auditable_vote_schema(self) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()
        transport = FixedVoteTransport()

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, transport
        )

        request, _ = transport.requests[0]
        self.assertEqual(VOTE_MAX_OUTPUT_TOKENS, request["max_tokens"])
        schema = cast(Mapping[str, Any], request["response_format"])["json_schema"]
        self.assertTrue(schema["strict"])
        body = schema["schema"]
        self.assertEqual(set(VOTE_FIELDS), set(body["properties"]))
        self.assertEqual(sorted(VOTE_FIELDS), sorted(body["required"]))
        self.assertFalse(body["additionalProperties"])
        self.assertEqual(
            list(RESULT_LABELS), body["properties"]["label"]["enum"]
        )
        self.assertEqual(
            list(VOTE_CONFIDENCE_BANDS),
            body["properties"]["confidence_band"]["enum"],
        )
        self.assertEqual(
            list(VOTE_REASON_CODES), body["properties"]["reason_code"]["enum"]
        )

    def test_the_raw_vote_keeps_the_band_the_evidence_and_the_reason_code(
        self,
    ) -> None:
        stage_manifest, candidates, allocation = self.vote_inputs()

        self.runner.collect_votes(
            stage_manifest, candidates, allocation, FixedVoteTransport()
        )

        record = self.runner.raw_vote_records()[0]
        self.assertEqual("valid", record["outcome"])
        self.assertEqual("positive", record["label"])
        self.assertEqual("high", record["confidence_band"])
        self.assertEqual("favorable evidence", record["reason_code"])
        self.assertEqual(0, record["evidence_start"])
        self.assertEqual(len(SILVER_PASSAGE), record["evidence_end"])
        self.assertEqual(SILVER_PASSAGE, record["evidence_text"])

    def test_an_invalid_field_or_a_wrong_offset_is_an_abstention(self) -> None:
        cases: dict[str, str] = {
            "unknown-band": vote_content(SILVER_PASSAGE, confidence_band="certain"),
            "unknown-reason-code": vote_content(
                SILVER_PASSAGE, reason_code="it looks good"
            ),
            "unknown-label": vote_content(SILVER_PASSAGE, label="bullish"),
            "missing-field": json.dumps(
                {
                    key: value
                    for key, value in json.loads(
                        vote_content(SILVER_PASSAGE)
                    ).items()
                    if key != "reason_code"
                }
            ),
            "added-property": vote_content(SILVER_PASSAGE, comment="very clear"),
            "shifted-offset": vote_content(SILVER_PASSAGE, evidence_start=1),
            "offset-after-the-passage": vote_content(
                SILVER_PASSAGE, evidence_end=len(SILVER_PASSAGE) + 5
            ),
            "text-that-is-not-in-the-passage": vote_content(
                SILVER_PASSAGE, evidence_text="Harbor Grid revenue decreased."
            ),
            "empty-span": vote_content(SILVER_PASSAGE, evidence_end=0, evidence_text=""),
            "text-without-offsets": vote_content(
                SILVER_PASSAGE, evidence_start=None, evidence_end=None
            ),
        }
        for name, content in cases.items():
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory() as state_dir:
                    runner = StageRun(
                        state_dir, clock=lambda: "2026-09-12T00:00:00Z"
                    )
                    stage_manifest, candidates, allocation = self.vote_inputs()

                    runner.collect_votes(
                        stage_manifest,
                        candidates,
                        allocation,
                        SequenceVoteTransport(self.response(content=content)),
                    )

                    vote = runner.raw_vote_records()[0]
                    self.assertEqual("abstention", vote["outcome"])
                    self.assertEqual("malformed-answer", vote["abstention_reason"])
                    self.assertIsNone(vote["label"])
                    self.assertIsNone(vote["confidence_band"])
                    self.assertIsNone(vote["reason_code"])
                    self.assertIsNone(vote["evidence_text"])

    def test_null_evidence_is_valid_only_for_insufficient_evidence(self) -> None:
        cases = {
            "insufficient evidence": "valid",
            "neutral": "abstention",
        }
        for label, expected_outcome in cases.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as state_dir:
                    runner = StageRun(
                        state_dir, clock=lambda: "2026-09-12T00:00:00Z"
                    )
                    stage_manifest, candidates, allocation = self.vote_inputs()
                    content = vote_content(
                        SILVER_PASSAGE,
                        label=label,
                        confidence_band="low",
                        reason_code="evidence absent",
                        evidence_start=None,
                        evidence_end=None,
                        evidence_text=None,
                    )

                    runner.collect_votes(
                        stage_manifest,
                        candidates,
                        allocation,
                        SequenceVoteTransport(self.response(content=content)),
                    )

                    vote = runner.raw_vote_records()[0]
                    self.assertEqual(expected_outcome, vote["outcome"])
                    if expected_outcome == "valid":
                        self.assertEqual(label, vote["label"])
                        self.assertEqual("evidence absent", vote["reason_code"])
                        self.assertIsNone(vote["evidence_start"])


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

    def add_votes(
        self,
        candidate_id: str,
        labels: Mapping[str, str],
        *,
        confidence_band: str = "high",
    ) -> None:
        for route_id, label in labels.items():
            self.runner._raw_vote_log.append(
                {
                    "event": "raw-vote",
                    "candidate_id": candidate_id,
                    "requested_route_id": route_id,
                    "outcome": "valid",
                    "label": label,
                    "confidence_band": confidence_band,
                    "reason_code": "favorable evidence",
                }
            )

    def add_development_votes(
        self, *, noisy_routes: int = 0, confidence_band: str = "high"
    ) -> None:
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
                confidence_band=confidence_band,
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

    def test_the_confidence_band_is_not_an_aggregation_weight(self) -> None:
        # A self-reported band is not calibrated, so it must not change the result.
        results = []
        for band in VOTE_CONFIDENCE_BANDS:
            with tempfile.TemporaryDirectory() as state_dir:
                self.runner = StageRun(
                    Path(state_dir), clock=lambda: "2026-09-12T00:00:00Z"
                )
                self.add_development_votes(confidence_band=band)
                self.add_votes(
                    "silver-1",
                    dict.fromkeys(ROUTE_IDS, "positive"),
                    confidence_band=band,
                )
                results.append(self.aggregate(["silver-1"]))

        self.assertEqual("complete", results[0]["aggregation"])
        self.assertEqual(
            1, len({str(result["aggregation_sha256"]) for result in results})
        )

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


def gpt_response(
    *,
    content: str = '{"label":"positive"}',
    model: str = "gpt-5.6-sol-medium",
    status_code: int = 200,
    refusal: str | None = None,
) -> OmniRouteResponse:
    message: dict[str, object] = {"content": content}
    if refusal is not None:
        message["refusal"] = refusal
    body = {
        "model": model,
        "choices": [{"message": message}],
        "usage": {
            "prompt_tokens": 1180,
            "completion_tokens": 540,
            "total_tokens": 1720,
        },
    }
    return OmniRouteResponse(
        status_code=status_code,
        headers={
            "x-omniroute-response-cost": "0.0043000000",
            "x-omniroute-model": model,
            "x-omniroute-provider": "cx",
            "x-omniroute-latency-ms": "2400",
            "x-omniroute-cache-hit": "false",
            "x-omniroute-fallback-attempts": "0",
            "x-omniroute-decision": "strategy=single; provider=cx; latency_ms=2400",
            "x-omniroute-request-id": "gpt-request",
            "x-omniroute-version": "3.8.49",
        },
        body=body,
        raw_body=json.dumps(body, indent=1).encode("utf-8"),
    )


class GptTransport:
    """Return the declared failures first, then one valid GPT answer."""

    def __init__(
        self, failures: list[OmniRouteResponse | BaseException] | None = None
    ) -> None:
        self.requests: list[tuple[dict[str, object], float]] = []
        self.failures = list(failures or [])

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        self.requests.append((copy.deepcopy(dict(request)), timeout_seconds))
        if self.failures:
            failure = self.failures.pop(0)
            if isinstance(failure, BaseException):
                raise failure
            return failure
        return gpt_response()



class GptBlindPredictionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name)
        self.runner = StageRun(
            self.state_dir,
            clock=lambda: "2026-09-12T00:00:00Z",
        )
        self.delays: list[float] = []

    def forecast(self, **changes: object) -> dict[str, object]:
        declared: dict[str, object] = {
            "measured_split": "development",
            "measured_candidate_ids": ["development-1"],
            "prompt_tokens_per_example": 1200,
            "completion_tokens_per_example": 600,
            "prompt_usd_per_1k_tokens": "0.0012",
            "completion_usd_per_1k_tokens": "0.0060",
            "charged_retry_reserve_attempts": 100,
        }
        declared.update(changes)
        return declared

    def gpt_inputs(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        stage_manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        candidates = candidate_manifest()
        candidates["candidates"] = [
            {
                "candidate_id": "development-1",
                "event_group_id": "event-development-1",
                "company_id": "Harbor Grid Ltd",
                "company": company_record("Harbor Grid Ltd"),
                "aspect": STAGE_1_ASPECTS[1],
                "published_at": "2026-07-10T09:00:00Z",
                "normalized_passage": "Harbor Grid won three new supply contracts.",
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "blind-1",
                "event_group_id": "event-blind-1",
                "company_id": "Harbor Grid Ltd",
                "company": company_record("Harbor Grid Ltd"),
                "aspect": STAGE_1_ASPECTS[2],
                "published_at": "2026-09-10T09:00:00Z",
                "normalized_passage": "Harbor Grid opened a new factory.",
                "near_duplicate_reviewed": True,
            },
            {
                "candidate_id": "blind-2",
                "event_group_id": "event-blind-2",
                "company_id": "Bay Rail Plc",
                "company": company_record("Bay Rail Plc"),
                "aspect": STAGE_1_ASPECTS[0],
                "published_at": "2026-09-11T09:00:00Z",
                "normalized_passage": "Bay Rail revenue decreased by four percent.",
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
            "training": [],
            "development": [{"candidate_id": "development-1"}],
            "blind": [
                {"candidate_id": "blind-1", "label": "positive"},
                {"candidate_id": "blind-2", "label": "negative"},
            ],
        }
        return stage_manifest, sealed_candidates, allocation

    def predict(
        self, transport: Any, *, forecast: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        stage_manifest, candidates, allocation = self.gpt_inputs()
        return self.runner.predict_blind_gpt(
            stage_manifest,
            candidates,
            allocation,
            transport,
            forecast=forecast if forecast is not None else self.forecast(),
            sleep=self.delays.append,
        )

    def test_the_sealed_file_uses_the_fixed_route_prompt_and_schema(self) -> None:
        transport = GptTransport()

        result = self.predict(transport)

        self.assertEqual("sealed", result["gpt_predictions"])
        self.assertIsNone(result["stop_reason"])
        self.assertEqual("cx/gpt-5.6-sol-medium", result["route_id"])
        self.assertEqual("medium", result["reasoning_effort"])
        self.assertEqual(2, result["prediction_count"])
        self.assertEqual(64, len(cast(str, result["prediction_file_sha256"])))
        self.assertEqual(
            ["blind-1", "blind-2"],
            [
                cast(Mapping[str, object], item)["candidate_id"]
                for item in cast(list[object], result["predictions"])
            ],
        )
        self.assertEqual(2, len(transport.requests))
        for request, _ in transport.requests:
            self.assertEqual("cx/gpt-5.6-sol-medium", request["model"])
            self.assertEqual("medium", request["reasoning_effort"])
            self.assertFalse(request["stream"])
            schema = cast(Any, request["response_format"])["json_schema"]
            self.assertTrue(schema["strict"])
            self.assertEqual(
                list(RESULT_LABELS), schema["schema"]["properties"]["label"]["enum"]
            )
            self.assertEqual(2, len(cast(list[Any], request["messages"])))

    def test_the_prompt_never_carries_a_blind_reference_label(self) -> None:
        transport = GptTransport()

        self.predict(transport)

        for request, _ in transport.requests:
            messages = cast(list[Mapping[str, str]], request["messages"])
            user_content = json.loads(messages[1]["content"])
            self.assertEqual({"passage", "company", "aspect"}, set(user_content))
            sent = json.dumps(request)
            for reference_label in ("positive", "negative"):
                self.assertNotIn(f'"{reference_label}"', sent.replace(
                    json.dumps(list(RESULT_LABELS))[1:-1], ""
                ))

    def test_a_candidate_manifest_label_stops_the_run(self) -> None:
        stage_manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        candidates = candidate_manifest()
        candidates["candidates"] = [
            {
                "candidate_id": "blind-1",
                "event_group_id": "event-blind-1",
                "company_id": "Harbor Grid Ltd",
                "company": company_record("Harbor Grid Ltd"),
                "aspect": STAGE_1_ASPECTS[2],
                "published_at": "2026-09-10T09:00:00Z",
                "normalized_passage": "Harbor Grid opened a new factory.",
                "near_duplicate_reviewed": True,
                "label": "positive",
            }
        ]
        sealed = seal_candidate_manifest(candidates, "fixture-owner")
        allocation = {
            "allocation": "complete",
            "stop_reason": None,
            "candidate_manifest_sha256": cast(
                Mapping[str, object], sealed["seal"]
            )["semantic_sha256"],
            "training": [],
            "development": [],
            "blind": [{"candidate_id": "blind-1", "label": "positive"}],
        }
        transport = GptTransport()

        result = self.runner.predict_blind_gpt(
            stage_manifest,
            sealed,
            allocation,
            transport,
            forecast=self.forecast(),
            sleep=self.delays.append,
        )

        self.assertEqual("invalid", result["gpt_predictions"])
        self.assertEqual("blind-label-exposed", result["stop_reason"])
        self.assertEqual(0, len(transport.requests))

    def test_a_non_blind_token_check_must_fit_the_gpt_allocation(self) -> None:
        projection = project_gpt_blind_cost(self.forecast())

        self.assertEqual("within-budget", projection["forecast"])
        self.assertEqual(2000, projection["first_attempts"])
        self.assertEqual(100, projection["reserve_attempts"])
        self.assertEqual("10.59", projection["projected_usd"])
        self.assertEqual("25.00", projection["remaining_usd"])

    def test_recorded_gpt_spend_lowers_the_projection_allowance(self) -> None:
        projection = project_gpt_blind_cost(
            self.forecast(), remaining_usd=Decimal("5.00")
        )

        self.assertEqual("stopped", projection["forecast"])
        self.assertEqual("gpt-budget-exceeded", projection["stop_reason"])
        self.assertEqual("10.59", projection["projected_usd"])
        self.assertEqual("5.00", projection["remaining_usd"])

    def test_a_sealed_file_does_not_serve_another_candidate_manifest(self) -> None:
        self.predict(GptTransport())
        stage_manifest, candidates, allocation = self.gpt_inputs()
        cast(list[Any], candidates["candidates"])[2]["normalized_passage"] = (
            "Bay Rail revenue decreased by five percent."
        )
        draft = {key: value for key, value in candidates.items() if key != "seal"}
        draft["candidates"] = [
            {
                key: value
                for key, value in cast(Mapping[str, object], item).items()
                if key not in ("content_sha256", "split")
            }
            for item in cast(list[Any], draft["candidates"])
        ]
        changed_candidates = seal_candidate_manifest(draft, "fixture-owner")
        allocation["candidate_manifest_sha256"] = cast(
            Mapping[str, object], changed_candidates["seal"]
        )["semantic_sha256"]
        transport = GptTransport()

        result = self.runner.predict_blind_gpt(
            stage_manifest,
            changed_candidates,
            allocation,
            transport,
            forecast=self.forecast(),
            sleep=self.delays.append,
        )

        self.assertEqual("frozen-gpt-run-changed", result["stop_reason"])
        self.assertEqual(0, len(transport.requests))

    def test_a_projection_above_the_gpt_allocation_stops_the_run(self) -> None:
        transport = GptTransport()

        result = self.predict(
            transport,
            forecast=self.forecast(completion_tokens_per_example=4000),
        )

        self.assertEqual("gpt-budget-exceeded", result["stop_reason"])
        self.assertEqual(0, len(transport.requests))

    def test_a_blind_measured_token_check_stops_the_run(self) -> None:
        transport = GptTransport()

        result = self.predict(
            transport, forecast=self.forecast(measured_split="blind")
        )

        self.assertEqual("gpt-forecast-blind-exposure", result["stop_reason"])
        self.assertEqual(0, len(transport.requests))

    def test_an_incomplete_token_check_stops_the_run(self) -> None:
        forecast = self.forecast()
        del forecast["charged_retry_reserve_attempts"]
        transport = GptTransport()

        result = self.predict(transport, forecast=forecast)

        self.assertEqual("gpt-forecast-incomplete", result["stop_reason"])
        self.assertEqual(0, len(transport.requests))

    def test_transport_failures_get_three_identical_attempts(self) -> None:
        for failure in (
            TimeoutError("timed out"),
            OSError("connection reset"),
            gpt_response(status_code=429),
            gpt_response(status_code=503),
        ):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as state_dir:
                    self.runner = StageRun(
                        state_dir, clock=lambda: "2026-09-12T00:00:00Z"
                    )
                    self.delays = []
                    transport = GptTransport(failures=[failure])

                    result = self.predict(transport)

                    self.assertEqual("sealed", result["gpt_predictions"])
                    self.assertEqual(3, len(transport.requests))
                    self.assertEqual([5.0], self.delays)
                    first, second = transport.requests[0][0], transport.requests[1][0]
                    self.assertEqual(first, second)
                    attempts = [
                        record
                        for record in self.runner.gpt_blind_records()
                        if record.get("event") == "gpt-blind-attempt"
                    ]
                    self.assertEqual(3, len(attempts))
                    self.assertEqual("transport-failure", attempts[0]["outcome"])
                    self.assertIsNone(attempts[0]["label"])

    def test_three_failed_transport_attempts_invalidate_the_run(self) -> None:
        failure = gpt_response(status_code=500)
        transport = GptTransport(failures=[failure, failure, failure])

        result = self.predict(transport)

        self.assertEqual("invalid", result["gpt_predictions"])
        self.assertEqual("gpt-transport-failed", result["stop_reason"])
        self.assertEqual(3, len(transport.requests))
        self.assertEqual([5.0, 20.0], self.delays)
        self.assertEqual(0, result["prediction_count"])

    def test_a_refusal_or_malformed_answer_is_not_retried(self) -> None:
        cases = {
            "refusal": gpt_response(refusal="I cannot classify this passage."),
            "malformed-answer": gpt_response(content="positive"),
            "malformed-answer-label": gpt_response(content='{"label":"bullish"}'),
        }
        for expected, response in cases.items():
            with self.subTest(case=expected):
                with tempfile.TemporaryDirectory() as state_dir:
                    self.runner = StageRun(
                        state_dir, clock=lambda: "2026-09-12T00:00:00Z"
                    )
                    transport = GptTransport(failures=[response])

                    result = self.predict(transport)

                    self.assertEqual("invalid", result["gpt_predictions"])
                    self.assertEqual(
                        expected.replace("-label", ""), result["stop_reason"]
                    )
                    self.assertEqual(1, len(transport.requests))
                    self.assertEqual([], self.delays)
                    self.assertEqual([], result["predictions"])

    def test_a_route_mismatch_invalidates_the_run(self) -> None:
        for header, value in (
            ("x-omniroute-model", "gpt-5.6-sol-high"),
            ("x-omniroute-fallback-attempts", "1"),
            ("x-omniroute-cache-hit", "true"),
            ("x-omniroute-decision", "strategy=fusion; provider=cx"),
        ):
            with self.subTest(header=header):
                with tempfile.TemporaryDirectory() as state_dir:
                    self.runner = StageRun(
                        state_dir, clock=lambda: "2026-09-12T00:00:00Z"
                    )
                    response = gpt_response()
                    headers = dict(response.headers)
                    headers[header] = value
                    transport = GptTransport(
                        failures=[response._replace(headers=headers)]
                    )

                    result = self.predict(transport)

                    self.assertEqual("route-mismatch", result["stop_reason"])
                    self.assertEqual(1, len(transport.requests))

    def test_a_changed_request_stops_the_run(self) -> None:
        failure = gpt_response(status_code=500)
        self.predict(GptTransport(failures=[failure, failure, failure]))

        with unittest.mock.patch(
            "nlp_wayfinder.stage_run.GPT_BLIND_SYSTEM_PROMPT", "Other instructions."
        ):
            changed = self.predict(GptTransport())

        self.assertEqual("frozen-gpt-run-changed", changed["stop_reason"])
        freeze = self.runner.gpt_blind_records()[0]
        self.assertEqual("cx/gpt-5.6-sol-medium", freeze["route_id"])
        self.assertEqual("medium", freeze["reasoning_effort"])

    def test_the_sealed_file_is_reused_without_a_new_gpt_call(self) -> None:
        first = self.predict(GptTransport())
        transport = GptTransport()

        again = self.predict(transport)

        self.assertEqual(first, again)
        self.assertEqual(0, len(transport.requests))

    def test_a_blind_candidate_outside_the_manifest_stops_the_run(self) -> None:
        stage_manifest, candidates, allocation = self.gpt_inputs()
        cast(list[Any], allocation["blind"]).append({"candidate_id": "blind-9"})
        transport = GptTransport()

        result = self.runner.predict_blind_gpt(
            stage_manifest,
            candidates,
            allocation,
            transport,
            forecast=self.forecast(),
            sleep=self.delays.append,
        )

        self.assertEqual("gpt-candidate-invalid", result["stop_reason"])
        self.assertEqual(0, len(transport.requests))

    def test_the_cli_seals_one_prediction_file(self) -> None:
        stage_manifest, candidates, allocation = self.gpt_inputs()
        paths = {}
        for name, value in (
            ("stage.json", stage_manifest),
            ("candidates.json", candidates),
            ("allocation.json", allocation),
            ("forecast.json", self.forecast()),
        ):
            path = self.state_dir / name
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = str(path)
        output = self.state_dir / "gpt-predictions.json"

        with unittest.mock.patch(
            "nlp_wayfinder.stage_run.OmniRouteHttpTransport",
            lambda *args, **kwargs: GptTransport(),
        ):
            code = stage_run_main(
                [
                    "predict-blind-gpt",
                    paths["stage.json"],
                    paths["candidates.json"],
                    paths["allocation.json"],
                    paths["forecast.json"],
                    "--output",
                    str(output),
                    "--state-dir",
                    str(self.state_dir / "cli-state"),
                ]
            )

        self.assertEqual(0, code)
        sealed = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("sealed", sealed["gpt_predictions"])
        self.assertEqual(2, sealed["prediction_count"])


class FakeTrainingBackend:
    """Train one checkpoint for each seed and predict on the local device."""

    def __init__(
        self,
        *,
        development_labels: Mapping[int, Mapping[str, str]] | None = None,
        blind_labels: Mapping[str, str] | None = None,
        device_id: str = "m3-fixture",
        train_result: Mapping[str, object] | None = None,
    ) -> None:
        self.trainings: list[dict[str, object]] = []
        self.inferences: list[tuple[str, list[dict[str, object]]]] = []
        self.development_labels = development_labels
        self.blind_labels = blind_labels
        self.device_id = device_id
        self.train_result = train_result

    def train(self, config: Mapping[str, object]) -> Mapping[str, object]:
        self.trainings.append(copy.deepcopy(dict(config)))
        seed = int(cast(int, config["seed"]))
        development = cast(list[Mapping[str, object]], config["development"])
        if self.development_labels is not None:
            predictions = dict(self.development_labels[seed])
        else:
            predictions = {
                str(item["candidate_id"]): "positive" for item in development
            }
        result = {
            "checkpoint_id": f"checkpoint-seed-{seed}",
            "model_id": MODERNBERT_MODEL_ID,
            "revision": MODERNBERT_REVISION,
            "max_sequence_tokens": MAX_EXAMPLE_TOKENS,
            "head_labels": list(RESULT_LABELS),
            "development_predictions": predictions,
        }
        if self.train_result is not None:
            result.update(self.train_result)
        return result

    def predict(
        self, checkpoint_id: str, examples: Sequence[Mapping[str, object]]
    ) -> Mapping[str, object]:
        self.inferences.append(
            (checkpoint_id, [copy.deepcopy(dict(item)) for item in examples])
        )
        labels = self.blind_labels
        return {
            "device_id": self.device_id,
            "predictions": {
                str(item["candidate_id"]): (
                    labels[str(item["candidate_id"])]
                    if labels is not None
                    else "positive"
                )
                for item in examples
                if labels is None or str(item["candidate_id"]) in labels
            },
        }


class SpecialistTrainingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runner = StageRun(
            Path(self.temp_dir.name), clock=lambda: "2026-09-12T00:00:00Z"
        )

    def m3_check(self, **changes: object) -> dict[str, object]:
        declared: dict[str, object] = {
            "device_id": "m3-fixture",
            "unified_memory_gb": 8,
            "max_sequence_tokens": 512,
            "compatibility_verified": True,
            "local_inference_verified": True,
            "evidence": "fixture device record",
        }
        declared.update(changes)
        return declared

    def pilot(self, **changes: object) -> dict[str, object]:
        declared: dict[str, object] = {
            "gpu_model": "A40",
            "gpu_architecture": "Ampere",
            "gpu_memory_gb": 48,
            "peak_memory_gb": 31.5,
            "max_sequence_tokens": MAX_EXAMPLE_TOKENS,
            "pilot_usd": "4.20",
            "initial_loss": 1.39,
            "final_loss": 0.62,
            "examples_per_second": 8.0,
            "training_examples_per_seed": 12_000,
            "hourly_usd": "0.80",
            "storage_gb": 30,
            "storage_usd_per_gb_month": "0.02",
            "storage_months": 1,
            "tax_rate": "0.00",
        }
        declared.update(changes)
        return declared

    def specialist_inputs(
        self, **changes: object
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
        stage_manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        candidates = candidate_manifest()
        rows: list[dict[str, object]] = []
        for index in range(2):
            rows.append(
                {
                    "candidate_id": f"training-{index}",
                    "event_group_id": f"event-training-{index}",
                    "company_id": "Harbor Grid Ltd",
                    "company": company_record("Harbor Grid Ltd"),
                    "aspect": STAGE_1_ASPECTS[index % 4],
                    "published_at": "2026-03-10T09:00:00Z",
                    "normalized_passage": f"Harbor Grid training passage {index}.",
                    "near_duplicate_reviewed": True,
                }
            )
        for index in range(4):
            rows.append(
                {
                    "candidate_id": f"development-{index}",
                    "event_group_id": f"event-development-{index}",
                    "company_id": "Bay Rail Plc",
                    "company": company_record("Bay Rail Plc"),
                    "aspect": STAGE_1_ASPECTS[index % 4],
                    "published_at": "2026-07-10T09:00:00Z",
                    "normalized_passage": f"Bay Rail development passage {index}.",
                    "near_duplicate_reviewed": True,
                }
            )
        for index in range(2):
            rows.append(
                {
                    "candidate_id": f"blind-{index}",
                    "event_group_id": f"event-blind-{index}",
                    "company_id": "Coast Metal Plc",
                    "company": company_record("Coast Metal Plc"),
                    "aspect": STAGE_1_ASPECTS[index % 4],
                    "published_at": "2026-09-10T09:00:00Z",
                    "normalized_passage": f"Coast Metal blind passage {index}.",
                    "near_duplicate_reviewed": True,
                }
            )
        candidates["candidates"] = cast(list[dict[str, object]], rows)
        sealed = seal_candidate_manifest(candidates, "fixture-owner")
        manifest_sha256 = str(
            cast(Mapping[str, object], sealed["seal"])["semantic_sha256"]
        )
        allocation: dict[str, object] = {
            "allocation": "complete",
            "stop_reason": None,
            "candidate_manifest_sha256": manifest_sha256,
            "training": [{"candidate_id": "training-0"}, {"candidate_id": "training-1"}],
            "development": [
                {"candidate_id": f"development-{index}", "label": RESULT_LABELS[index]}
                for index in range(4)
            ],
            "blind": [
                {"candidate_id": "blind-0", "label": "positive"},
                {"candidate_id": "blind-1", "label": "negative"},
            ],
        }
        aggregation: dict[str, object] = {
            "aggregation": "complete",
            "stop_reason": None,
            "candidate_manifest_sha256": manifest_sha256,
            "accepted_silver_count": 2,
            "accepted_silver": [
                {
                    "candidate_id": "training-0",
                    "label": "positive",
                    "probability": 0.91,
                },
                {
                    "candidate_id": "training-1",
                    "label": "negative",
                    "probability": 0.86,
                },
            ],
        }
        aggregation.update(changes)
        return stage_manifest, sealed, allocation, aggregation

    def train(
        self,
        backend: Any,
        *,
        m3: Mapping[str, object] | None = None,
        pilot: Mapping[str, object] | None = None,
        inputs: tuple[Any, Any, Any, Any] | None = None,
    ) -> dict[str, object]:
        stage_manifest, candidates, allocation, aggregation = (
            inputs if inputs is not None else self.specialist_inputs()
        )
        return self.runner.train_specialist(
            stage_manifest,
            [
                {
                    "candidate_manifest": candidates,
                    "allocation": allocation,
                    "aggregation": aggregation,
                }
            ],
            backend,
            device_checks={
                "m3": self.m3_check() if m3 is None else m3,
                "gpu_pilot": self.pilot() if pilot is None else pilot,
            },
        )

    def development_labels(self) -> dict[int, dict[str, str]]:
        reference = {
            f"development-{index}": RESULT_LABELS[index] for index in range(4)
        }
        wrong = dict(reference)
        wrong["development-0"] = "negative"
        return {1: wrong, 2: dict(reference), 3: wrong}

    def test_the_sealed_file_uses_the_pinned_initialization(self) -> None:
        backend = FakeTrainingBackend(development_labels=self.development_labels())

        result = self.train(backend)

        self.assertEqual("sealed", result["specialist_predictions"])
        self.assertIsNone(result["stop_reason"])
        self.assertEqual(MODERNBERT_MODEL_ID, result["model_id"])
        self.assertEqual(MODERNBERT_REVISION, result["revision"])
        self.assertEqual("checkpoint-seed-2", result["checkpoint_id"])
        self.assertEqual(2, result["prediction_count"])
        self.assertEqual(64, len(cast(str, result["prediction_file_sha256"])))
        self.assertEqual(
            ["blind-0", "blind-1"],
            [
                cast(Mapping[str, object], item)["candidate_id"]
                for item in cast(list[object], result["predictions"])
            ],
        )
        self.assertEqual(3, len(backend.trainings))
        for config in backend.trainings:
            self.assertEqual(MODERNBERT_MODEL_ID, config["model_id"])
            self.assertEqual(MODERNBERT_REVISION, config["revision"])
            self.assertEqual(MAX_EXAMPLE_TOKENS, config["max_sequence_tokens"])
            self.assertEqual(list(RESULT_LABELS), config["head_labels"])
            training = cast(list[Mapping[str, object]], config["training"])
            self.assertEqual(2, len(training))
            self.assertEqual(
                {"candidate_id", "passage", "target", "aspect", "label"},
                set(training[0]),
            )
            self.assertEqual("positive", training[0]["label"])

    def test_the_development_input_never_carries_a_human_label(self) -> None:
        backend = FakeTrainingBackend(development_labels=self.development_labels())

        self.train(backend)

        for config in backend.trainings:
            development = cast(list[Mapping[str, object]], config["development"])
            self.assertEqual(4, len(development))
            for item in development:
                self.assertEqual(
                    {"candidate_id", "passage", "target", "aspect"}, set(item)
                )

    def test_the_blind_inference_runs_on_the_checked_m3_device(self) -> None:
        backend = FakeTrainingBackend(development_labels=self.development_labels())

        result = self.train(backend)

        self.assertEqual("m3-fixture", result["inference_device_id"])
        checkpoint_id, examples = backend.inferences[0]
        self.assertEqual("checkpoint-seed-2", checkpoint_id)
        for item in examples:
            self.assertEqual(
                {"candidate_id", "passage", "target", "aspect"}, set(item)
            )

    def test_another_inference_device_stops_the_run(self) -> None:
        backend = FakeTrainingBackend(device_id="rented-gpu")

        result = self.train(backend)

        self.assertEqual("invalid", result["specialist_predictions"])
        self.assertEqual("local-inference-device-mismatch", result["stop_reason"])

    def test_an_incomplete_m3_check_stops_the_run(self) -> None:
        check = self.m3_check()
        del check["local_inference_verified"]

        result = self.train(FakeTrainingBackend(), m3=check)

        self.assertEqual("m3-check-incomplete", result["stop_reason"])

    def test_a_failed_m3_check_stops_the_run(self) -> None:
        result = self.train(
            FakeTrainingBackend(), m3=self.m3_check(max_sequence_tokens=1_024)
        )

        self.assertEqual("m3-check-failed", result["stop_reason"])

    def test_a_pilot_above_five_dollars_stops_the_run(self) -> None:
        result = self.train(FakeTrainingBackend(), pilot=self.pilot(pilot_usd="5.01"))

        self.assertEqual("specialist-pilot-cost-exceeded", result["stop_reason"])

    def test_an_older_gpu_architecture_stops_the_run(self) -> None:
        result = self.train(
            FakeTrainingBackend(), pilot=self.pilot(gpu_architecture="Turing")
        )

        self.assertEqual("specialist-pilot-architecture", result["stop_reason"])

    def test_a_short_pilot_input_stops_the_run(self) -> None:
        result = self.train(
            FakeTrainingBackend(), pilot=self.pilot(max_sequence_tokens=512)
        )

        self.assertEqual("specialist-pilot-token-limit", result["stop_reason"])

    def test_memory_above_the_gpu_stops_the_run(self) -> None:
        result = self.train(FakeTrainingBackend(), pilot=self.pilot(peak_memory_gb=64))

        self.assertEqual("specialist-pilot-memory", result["stop_reason"])

    def test_a_loss_that_does_not_decrease_stops_the_run(self) -> None:
        result = self.train(FakeTrainingBackend(), pilot=self.pilot(final_loss=1.39))

        self.assertEqual("specialist-pilot-loss", result["stop_reason"])

    def test_the_projection_covers_seeds_storage_tax_and_one_repeat(self) -> None:
        projection = project_specialist_training_cost(self.pilot())

        self.assertEqual("within-budget", projection["forecast"])
        self.assertEqual(4, projection["training_runs"])
        self.assertEqual(1, projection["operational_repeats"])
        self.assertEqual([1, 2, 3], projection["seeds"])
        # 12,000 examples at 8.0 per second is 0.416667 hours for each run.
        # Four runs at USD 0.80 and 30 GB at USD 0.02 gives USD 1.94.
        self.assertEqual("1.94", projection["projected_usd"])
        self.assertEqual("35.00", projection["remaining_usd"])

    def test_the_projection_adds_the_declared_tax(self) -> None:
        projection = project_specialist_training_cost(self.pilot(tax_rate="0.10"))

        self.assertEqual("2.13", projection["projected_usd"])

    def test_a_projection_above_the_balance_stops_the_run(self) -> None:
        projection = project_specialist_training_cost(
            self.pilot(), remaining_usd=Decimal("1.00")
        )

        self.assertEqual("specialist-budget-exceeded", projection["stop_reason"])
        self.assertEqual("1.94", projection["projected_usd"])

    def test_a_projection_above_the_remaining_allocation_stops_training(self) -> None:
        self.runner.record_cost(
            action_id="gpu-pilot",
            kind="commitment",
            category="specialist",
            amount_usd="5.00",
            evidence="fixture pilot commitment",
        )
        # USD 30.25 fits the USD 35 allocation but not the USD 30 balance.
        pilot = self.pilot(hourly_usd="17.79")

        result = self.train(FakeTrainingBackend(), pilot=pilot)

        self.assertEqual("specialist-budget-exceeded", result["stop_reason"])
        self.assertEqual(
            "within-budget",
            project_specialist_training_cost(pilot)["forecast"],
        )

    def test_the_pilot_cost_lowers_the_specialist_balance(self) -> None:
        # USD 35 less the USD 5 pilot leaves USD 30 for the three seed runs.
        pilot = self.pilot(pilot_usd="5.00", hourly_usd="17.79")

        result = self.train(FakeTrainingBackend(), pilot=pilot)

        self.assertEqual("specialist-budget-exceeded", result["stop_reason"])

    def test_a_passage_that_mentions_gpt_does_not_stop_the_run(self) -> None:
        inputs = list(self.specialist_inputs())
        candidates = cast(dict[str, object], inputs[1])
        draft = {key: value for key, value in candidates.items() if key != "seal"}
        draft["candidates"] = [
            {
                key: value
                for key, value in cast(Mapping[str, object], item).items()
                if key not in ("content_sha256", "split")
            }
            for item in cast(list[Any], draft["candidates"])
        ]
        cast(list[dict[str, object]], draft["candidates"])[0]["normalized_passage"] = (
            "Harbor Grid sells GPT servers to three customers."
        )
        changed = seal_candidate_manifest(draft, "fixture-owner")
        manifest_sha256 = cast(Mapping[str, object], changed["seal"])["semantic_sha256"]
        inputs[1] = changed
        cast(dict[str, object], inputs[2])["candidate_manifest_sha256"] = manifest_sha256
        cast(dict[str, object], inputs[3])["candidate_manifest_sha256"] = manifest_sha256

        result = self.train(
            FakeTrainingBackend(development_labels=self.development_labels()),
            inputs=cast(Any, tuple(inputs)),
        )

        self.assertEqual("sealed", result["specialist_predictions"])

    def test_a_blind_label_in_the_manifest_stops_the_run(self) -> None:
        inputs = list(self.specialist_inputs())
        candidates = cast(dict[str, object], inputs[1])
        draft = {key: value for key, value in candidates.items() if key != "seal"}
        draft["candidates"] = [
            {
                key: value
                for key, value in cast(Mapping[str, object], item).items()
                if key not in ("content_sha256", "split")
            }
            for item in cast(list[Any], draft["candidates"])
        ]
        cast(list[dict[str, object]], draft["candidates"])[-1]["label"] = "positive"
        changed = seal_candidate_manifest(draft, "fixture-owner")
        manifest_sha256 = cast(Mapping[str, object], changed["seal"])["semantic_sha256"]
        inputs[1] = changed
        cast(dict[str, object], inputs[2])["candidate_manifest_sha256"] = manifest_sha256
        cast(dict[str, object], inputs[3])["candidate_manifest_sha256"] = manifest_sha256

        result = self.train(
            FakeTrainingBackend(), inputs=cast(Any, tuple(inputs))
        )

        self.assertEqual("blind-label-exposed", result["stop_reason"])

    def test_a_gpt_artifact_stops_the_run(self) -> None:
        inputs = self.specialist_inputs()
        aggregation = cast(dict[str, object], inputs[3])
        aggregation["label_source"] = "cx/gpt-5.6-sol-medium"

        result = self.train(FakeTrainingBackend(), inputs=inputs)

        self.assertEqual("gpt-artifact-present", result["stop_reason"])

    def test_unaccepted_silver_labels_stop_the_run(self) -> None:
        inputs = self.specialist_inputs(aggregation="stopped")

        result = self.train(FakeTrainingBackend(), inputs=inputs)

        self.assertEqual("silver-labels-not-accepted", result["stop_reason"])

    def test_a_missing_blind_prediction_stops_the_run(self) -> None:
        backend = FakeTrainingBackend(blind_labels={"blind-0": "positive"})

        result = self.train(backend)

        self.assertEqual("missing-prediction", result["stop_reason"])

    def test_another_initialization_stops_the_run(self) -> None:
        backend = FakeTrainingBackend(train_result={"revision": "other-revision"})

        result = self.train(backend)

        self.assertEqual("specialist-training-invalid", result["stop_reason"])

    def test_the_sealed_file_is_reused_without_new_training(self) -> None:
        backend = FakeTrainingBackend(development_labels=self.development_labels())
        first = self.train(backend)
        second_backend = FakeTrainingBackend(
            development_labels=self.development_labels()
        )

        second = self.train(second_backend)

        self.assertEqual(first, second)
        self.assertEqual([], second_backend.trainings)
        self.assertEqual([], second_backend.inferences)

    def test_a_changed_candidate_manifest_stops_a_sealed_run(self) -> None:
        self.train(FakeTrainingBackend(development_labels=self.development_labels()))
        stage_manifest, candidates, allocation, aggregation = self.specialist_inputs()
        draft = {key: value for key, value in candidates.items() if key != "seal"}
        draft["candidates"] = [
            {
                key: value
                for key, value in cast(Mapping[str, object], item).items()
                if key not in ("content_sha256", "split")
            }
            for item in cast(list[Any], draft["candidates"])
        ]
        cast(list[dict[str, object]], draft["candidates"])[0][
            "normalized_passage"
        ] = "Harbor Grid changed its training passage."
        changed = seal_candidate_manifest(draft, "fixture-owner")
        manifest_sha256 = cast(Mapping[str, object], changed["seal"])["semantic_sha256"]
        allocation["candidate_manifest_sha256"] = manifest_sha256
        aggregation["candidate_manifest_sha256"] = manifest_sha256

        result = self.runner.train_specialist(
            stage_manifest,
            [
                {
                    "candidate_manifest": changed,
                    "allocation": allocation,
                    "aggregation": aggregation,
                }
            ],
            FakeTrainingBackend(),
            device_checks={"m3": self.m3_check(), "gpu_pilot": self.pilot()},
        )

        self.assertEqual("frozen-specialist-run-changed", result["stop_reason"])


class LabelledGptTransport:
    """Answer each blind example with the label that the passage selects."""

    def __init__(self, labels: Mapping[str, str]) -> None:
        self.labels = labels
        self.requests: list[dict[str, object]] = []

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        self.requests.append(copy.deepcopy(dict(request)))
        messages = cast(list[Mapping[str, str]], request["messages"])
        passage = json.loads(messages[1]["content"])["passage"]
        return gpt_response(content=json.dumps({"label": self.labels[passage]}))


BLIND_REPORT_SIZE = 64


def blind_passage(index: int, source: str = "financial-news") -> str:
    return f"{source} Coast Metal blind passage {index}."


def report_source_fixture(
    reference: Mapping[str, str],
    *,
    stage: int = 1,
    source: str = "financial-news",
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Build one sealed manifest, allocation, and aggregation of one source."""
    prefix = "" if source == "financial-news" else f"{source}-"
    candidates = candidate_manifest(stage, source)
    rows: list[dict[str, object]] = [
        {
            "candidate_id": f"{prefix}training-{index}",
            "event_group_id": f"{prefix}event-training-{index}",
            "company_id": f"{prefix}Harbor Grid Ltd",
            "company": company_record(f"{prefix}Harbor Grid Ltd"),
            "aspect": STAGE_1_ASPECTS[index % 4],
            "published_at": "2026-03-10T09:00:00Z",
            "normalized_passage": f"{prefix}Harbor Grid training passage {index}.",
            "near_duplicate_reviewed": True,
        }
        for index in range(2)
    ]
    rows.extend(
        {
            "candidate_id": f"{prefix}development-{index}",
            "event_group_id": f"{prefix}event-development-{index}",
            "company_id": f"{prefix}Bay Rail Plc",
            "company": company_record(f"{prefix}Bay Rail Plc"),
            "aspect": STAGE_1_ASPECTS[index % 4],
            "published_at": "2026-07-10T09:00:00Z",
            "normalized_passage": f"{prefix}Bay Rail development passage {index}.",
            "near_duplicate_reviewed": True,
        }
        for index in range(4)
    )
    rows.extend(
        {
            "candidate_id": f"{prefix}blind-{index:02d}",
            # Two blind examples share one event group, so the bootstrap
            # resamples fewer units than examples.
            "event_group_id": f"{prefix}event-blind-{index // 2:02d}",
            "company_id": f"{prefix}Coast Metal {index // 8} Plc",
            "company": company_record(f"{prefix}Coast Metal {index // 8} Plc"),
            "aspect": STAGE_1_ASPECTS[index % 4],
            "published_at": "2026-09-10T09:00:00Z",
            "normalized_passage": blind_passage(index, source),
            "near_duplicate_reviewed": True,
        }
        for index in range(BLIND_REPORT_SIZE)
    )
    candidates["candidates"] = rows
    sealed = seal_candidate_manifest(candidates, "fixture-owner")
    manifest_sha256 = str(
        cast(Mapping[str, object], sealed["seal"])["semantic_sha256"]
    )
    blind = [
        {
            "candidate_id": candidate_id,
            "event_group_id": f"{prefix}event-blind-{index // 2:02d}",
            "company_id": f"{prefix}Coast Metal {index // 8} Plc",
            "company": company_record(f"{prefix}Coast Metal {index // 8} Plc"),
            "aspect": STAGE_1_ASPECTS[index % 4],
            "label": label,
            "labeled_at": "2026-09-11T00:00:00Z",
            "unseen_issuer": True,
        }
        for index, (candidate_id, label) in enumerate(reference.items())
    ]
    allocation: dict[str, object] = {
        "allocation": "complete",
        "stop_reason": None,
        "candidate_manifest_sha256": manifest_sha256,
        "silver_candidates_inspected": 70,
        "training": [
            {"candidate_id": f"{prefix}training-0"},
            {"candidate_id": f"{prefix}training-1"},
        ],
        "development": [
            {"candidate_id": f"{prefix}development-{index}", "label": RESULT_LABELS[index]}
            for index in range(4)
        ],
        "blind": blind,
        "blind_relabel_seed": BLIND_RELABEL_SEED,
        "blind_relabel_sample": [
            {
                "candidate_id": item["candidate_id"],
                "aspect": item["aspect"],
                "label": item["label"],
                "relabel_not_before": "2026-09-25T00:00:00Z",
            }
            for item in blind[:BLIND_RELABEL_TARGET]
        ],
        "allocation_sha256": "fixture-allocation-sha256",
    }
    aggregation: dict[str, object] = {
        "aggregation": "complete",
        "stop_reason": None,
        "candidate_manifest_sha256": manifest_sha256,
        "accepted_silver_count": 2,
        "accepted_silver": [
            {"candidate_id": f"{prefix}training-0", "label": "positive", "probability": 0.91},
            {"candidate_id": f"{prefix}training-1", "label": "negative", "probability": 0.86},
        ],
    }
    return sealed, allocation, aggregation


class Stage1ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name)
        self.runner = StageRun(self.state_dir, clock=lambda: "2026-09-12T00:00:00Z")
        self.delays: list[float] = []
        self.reference = {
            f"blind-{index:02d}": RESULT_LABELS[index % 4]
            for index in range(BLIND_REPORT_SIZE)
        }
        self._inputs: (
            tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]
            | None
        ) = None

    def report_inputs(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
        # One test can read the inputs more than one time. Build them one time,
        # because a new confirmation carries a new wall-clock time, and the
        # control then stops the run with `confirmation-evidence-changed`.
        if self._inputs is None:
            self._inputs = self.build_report_inputs()
        return copy.deepcopy(self._inputs)

    def build_report_inputs(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
        stage_manifest = confirm_manifest(draft_manifest(), "fixture-owner")
        sealed, allocation, aggregation = report_source_fixture(self.reference)
        return stage_manifest, sealed, allocation, aggregation


    def source_metrics(
        self, result: Mapping[str, object], source: str = "financial-news"
    ) -> Mapping[str, Any]:
        metrics = cast(Mapping[str, Any], result["metrics"])
        return cast(Mapping[str, Any], metrics["by_source"][source])

    def report_sources(
        self,
        candidates: Mapping[str, object],
        allocation: Mapping[str, object],
        relabels: Sequence[Mapping[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "candidate_manifest": candidates,
                "allocation": allocation,
                "relabels": self.relabels() if relabels is None else relabels,
            }
        ]

    def wrong(self, label: str) -> str:
        return RESULT_LABELS[(RESULT_LABELS.index(label) + 1) % 4]

    def labels(self, wrong_count: int) -> dict[str, str]:
        """Give one label for each blind example, with the first ones wrong."""
        return {
            candidate_id: (
                self.wrong(label) if index < wrong_count else label
            )
            for index, (candidate_id, label) in enumerate(self.reference.items())
        }

    def relabels(self, changed_count: int = 0) -> list[dict[str, object]]:
        sample = list(self.reference.items())[:BLIND_RELABEL_TARGET]
        return [
            {
                "candidate_id": candidate_id,
                "label": self.wrong(label) if index < changed_count else label,
                "labeled_at": "2026-09-26T00:00:00Z",
            }
            for index, (candidate_id, label) in enumerate(sample)
        ]

    def report(
        self,
        *,
        specialist_wrong: int = 0,
        gpt_wrong: int = 0,
        changed_relabels: int = 0,
        relabels: Sequence[Mapping[str, object]] | None = None,
    ) -> dict[str, object]:
        stage_manifest, candidates, allocation, aggregation = self.report_inputs()
        backend = FakeTrainingBackend(blind_labels=self.labels(specialist_wrong))
        self.runner.train_specialist(
            stage_manifest,
            [
                {
                    "candidate_manifest": candidates,
                    "allocation": allocation,
                    "aggregation": aggregation,
                }
            ],
            backend,
            device_checks={
                "m3": {
                    "device_id": "m3-fixture",
                    "unified_memory_gb": 8,
                    "max_sequence_tokens": 512,
                    "compatibility_verified": True,
                    "local_inference_verified": True,
                    "evidence": "fixture device record",
                },
                "gpu_pilot": {
                    "gpu_model": "A40",
                    "gpu_architecture": "Ampere",
                    "gpu_memory_gb": 48,
                    "peak_memory_gb": 31.5,
                    "max_sequence_tokens": MAX_EXAMPLE_TOKENS,
                    "pilot_usd": "4.20",
                    "initial_loss": 1.39,
                    "final_loss": 0.62,
                    "examples_per_second": 8.0,
                    "training_examples_per_seed": 12_000,
                    "hourly_usd": "0.80",
                    "storage_gb": 30,
                    "storage_usd_per_gb_month": "0.02",
                    "storage_months": 1,
                    "tax_rate": "0.00",
                },
            },
        )
        gpt_labels = self.labels(gpt_wrong)
        transport = LabelledGptTransport(
            {
                blind_passage(index): gpt_labels[candidate_id]
                for index, candidate_id in enumerate(self.reference)
            }
        )
        self.runner.predict_blind_gpt(
            stage_manifest,
            candidates,
            allocation,
            transport,
            forecast={
                "measured_split": "development",
                "measured_candidate_ids": ["development-0"],
                "prompt_tokens_per_example": 1200,
                "completion_tokens_per_example": 600,
                "prompt_usd_per_1k_tokens": "0.0012",
                "completion_usd_per_1k_tokens": "0.0060",
                "charged_retry_reserve_attempts": 100,
            },
            sleep=self.delays.append,
        )
        return self.runner.report_stage(
            stage_manifest,
            [
                {
                    "candidate_manifest": candidates,
                    "allocation": allocation,
                    "relabels": (
                        self.relabels(changed_relabels)
                        if relabels is None
                        else relabels
                    ),
                }
            ],
        )

    def test_the_report_scores_the_sealed_paired_predictions(self) -> None:
        result = self.report()

        self.assertEqual("complete", result["report"])
        self.assertIsNone(result["stop_reason"])
        metrics = self.source_metrics(result)
        self.assertEqual(1.0, metrics["specialist"]["macro_f1"])
        self.assertEqual(1.0, metrics["gpt"]["macro_f1"])
        self.assertEqual(0.0, metrics["macro_f1_difference"])
        self.assertEqual(
            {label: 1.0 for label in RESULT_LABELS},
            metrics["specialist"]["class_f1"],
        )
        pooled = cast(Mapping[str, Any], result["metrics"])["pooled"]
        self.assertTrue(pooled["diagnostic_only"])
        self.assertEqual(0.0, pooled["macro_f1_difference"])

    def test_the_paired_bootstrap_uses_the_fixed_seed_and_interval(self) -> None:
        result = self.report()

        bootstrap = self.source_metrics(result)["bootstrap"]
        self.assertEqual("20260905", bootstrap["seed"])
        self.assertEqual(10_000, bootstrap["samples"])
        self.assertEqual(0.95, bootstrap["interval"])
        self.assertEqual("event-group", bootstrap["resampling_unit"])
        self.assertEqual(BLIND_REPORT_SIZE // 2, bootstrap["event_group_count"])
        self.assertEqual(0.0, bootstrap["lower_limit"])
        self.assertEqual(0.0, bootstrap["upper_limit"])

    def test_an_equal_result_passes_the_guardrail_without_superiority(self) -> None:
        decision = cast(Mapping[str, Any], self.report()["decision"])

        self.assertEqual(
            {"financial-news": "pass"}, decision["source_guardrail"]
        )
        self.assertEqual("pass", decision["stage_guardrail"])
        self.assertEqual(-0.03, decision["non_inferiority_margin"])
        self.assertEqual({"financial-news": False}, decision["superiority"])
        self.assertEqual("first-human-label", decision["reference_label"])

    def test_a_positive_lower_limit_records_superiority(self) -> None:
        result = self.report(gpt_wrong=24)

        decision = cast(Mapping[str, Any], result["decision"])
        metrics = self.source_metrics(result)
        self.assertEqual("pass", decision["source_guardrail"]["financial-news"])
        self.assertTrue(decision["superiority"]["financial-news"])
        self.assertGreater(metrics["bootstrap"]["lower_limit"], 0.0)
        self.assertGreater(metrics["macro_f1_difference"], 0.0)
        self.assertLess(metrics["gpt"]["macro_f1"], 1.0)

    def test_a_lower_limit_below_the_margin_fails_the_guardrail(self) -> None:
        result = self.report(specialist_wrong=32)

        decision = cast(Mapping[str, Any], result["decision"])
        metrics = self.source_metrics(result)
        self.assertEqual("fail", decision["source_guardrail"]["financial-news"])
        self.assertEqual("fail", decision["stage_guardrail"])
        self.assertFalse(decision["superiority"]["financial-news"])
        self.assertLess(metrics["bootstrap"]["lower_limit"], -0.03)

    def test_the_relabel_measures_repeatability_and_keeps_the_first_label(self) -> None:
        result = self.report(changed_relabels=6)

        metrics = self.source_metrics(result)
        self_consistency = metrics["self_consistency"]
        self.assertEqual(BLIND_RELABEL_TARGET, self_consistency["example_count"])
        self.assertEqual(54, self_consistency["agreed_count"])
        self.assertEqual(0.9, self_consistency["raw_agreement"])
        self.assertAlmostEqual(0.866667, self_consistency["cohen_kappa"], places=6)
        self.assertEqual("first-human-label", self_consistency["reference_label"])
        self.assertEqual(BLIND_RELABEL_SEED, self_consistency["seed"])
        # The second label does not move the benchmark result.
        self.assertEqual(1.0, metrics["specialist"]["macro_f1"])

    def test_a_relabel_inside_the_washout_stops_the_report(self) -> None:
        early = self.relabels()
        cast(dict[str, object], early[0])["labeled_at"] = "2026-09-20T00:00:00Z"

        result = self.report(relabels=early)

        self.assertEqual("invalid", result["report"])
        self.assertEqual("relabel-washout-not-met", result["stop_reason"])

    def test_an_incomplete_relabel_sample_stops_the_report(self) -> None:
        result = self.report(relabels=self.relabels()[:-1])

        self.assertEqual("invalid", result["report"])
        self.assertEqual("relabel-sample-mismatch", result["stop_reason"])

    def test_a_missing_prediction_file_stops_the_report(self) -> None:
        stage_manifest, candidates, allocation, _ = self.report_inputs()

        result = self.runner.report_stage(
            stage_manifest, self.report_sources(candidates, allocation)
        )

        self.assertEqual("invalid", result["report"])
        self.assertEqual("specialist-predictions-missing", result["stop_reason"])

    def test_an_unpaired_blind_example_stops_the_report(self) -> None:
        self.report()
        stage_manifest, candidates, allocation, _ = self.report_inputs()
        cast(list[Any], allocation["blind"]).pop()

        result = self.runner.report_stage(
            stage_manifest, self.report_sources(candidates, allocation)
        )

        self.assertEqual("invalid", result["report"])
        self.assertEqual("incomplete-paired-predictions", result["stop_reason"])

    def test_the_report_holds_the_complete_audit_record(self) -> None:
        result = self.report()

        counts = cast(Mapping[str, Any], result["counts"])
        identities = cast(Mapping[str, Any], result["identities"])
        hashes = cast(Mapping[str, Any], result["hashes"])
        attempts = cast(Mapping[str, Any], result["attempts"])
        source_metrics = self.source_metrics(result)
        self.assertEqual(BLIND_REPORT_SIZE, counts["blind_examples"])
        self.assertEqual(BLIND_REPORT_SIZE // 2, source_metrics["blind_event_groups"])
        self.assertEqual(BLIND_REPORT_SIZE, source_metrics["unseen_issuers"])
        self.assertEqual(2, counts["training_examples"])
        self.assertEqual(4, counts["development_examples"])
        self.assertEqual(
            {"financial-news": 70}, counts["silver_candidates_inspected"]
        )
        self.assertEqual(
            BLIND_RELABEL_TARGET,
            source_metrics["self_consistency"]["example_count"],
        )
        self.assertEqual(BLIND_REPORT_SIZE, counts["gpt_attempts"])
        self.assertEqual(MODERNBERT_MODEL_ID, identities["specialist_model_id"])
        self.assertEqual(MODERNBERT_REVISION, identities["specialist_revision"])
        self.assertEqual(
            {"financial-news": "cx/gpt-5.6-sol-medium"}, identities["gpt_route_id"]
        )
        self.assertEqual(
            {"financial-news": "medium"}, identities["gpt_reasoning_effort"]
        )
        self.assertEqual(list(ROUTE_IDS), identities["labeling_route_ids"])
        self.assertEqual(
            {"financial-news": "fixture-allocation-sha256"},
            hashes["allocation_sha256"],
        )
        for name in ("stage_manifest_sha256", "specialist_prediction_file_sha256",
                     "training_config_sha256"):
            self.assertEqual(64, len(cast(str, hashes[name])), name)
        for name in ("candidate_manifest_sha256", "gpt_prediction_file_sha256",
                     "gpt_prompt_sha256"):
            self.assertEqual(
                64, len(cast(str, hashes[name]["financial-news"])), name
            )
        self.assertEqual({"valid": BLIND_REPORT_SIZE}, attempts["gpt_by_outcome"])
        self.assertEqual(0, attempts["gpt_retried_examples"])
        self.assertEqual(3, len(cast(list[Any], attempts["specialist_training_runs"])))
        self.assertEqual(
            {"specialist", "gpt"}, set(cast(Mapping[str, Any], result["versions"])) - {"report"}
        )
        self.assertEqual(
            {"specialist", "gpt"}, set(cast(Mapping[str, Any], result["prediction_files"]))
        )
        self.assertIsInstance(result["decision_records"], list)
        self.assertIsInstance(result["ledger_entries"], list)
        self.assertEqual(64, len(cast(str, result["report_sha256"])))
        self.assertIn(
            "stage-report",
            [record["event"] for record in self.runner.decision_records()],
        )

    def test_the_cli_writes_the_stage_report(self) -> None:
        stage_manifest, candidates, allocation, _ = self.report_inputs()
        self.report()
        paths = {}
        for name, value in (
            ("stage.json", stage_manifest),
            ("candidates.json", candidates),
            ("allocation.json", allocation),
            ("relabels.json", self.relabels()),
        ):
            path = self.state_dir / name
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = str(path)
        sources_path = self.state_dir / "sources.json"
        sources_path.write_text(
            json.dumps(
                [
                    {
                        "candidate_manifest": paths["candidates.json"],
                        "allocation": paths["allocation.json"],
                        "relabels": paths["relabels.json"],
                    }
                ]
            ),
            encoding="utf-8",
        )
        output = self.state_dir / "stage-1-report.json"

        code = stage_run_main(
            [
                "report-stage",
                paths["stage.json"],
                str(sources_path),
                "--output",
                str(output),
                "--state-dir",
                str(self.state_dir),
            ]
        )

        self.assertEqual(0, code)
        written = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("complete", written["report"])
        self.assertEqual(
            "pass", written["decision"]["source_guardrail"]["financial-news"]
        )


STAGE_2_RIGHTS = {field: True for field in RIGHTS_FIELDS}


def stage_source(source_type: str) -> dict[str, object]:
    """Give the complete gate record of one later-stage source."""
    return {
        "source_id": f"{source_type}-fixture",
        "source_type": source_type,
        **STAGE_2_RIGHTS,
        "evidence": {
            "checked_at": "2026-09-28T00:00:00Z",
            "terms_url": f"https://example.test/{source_type}-terms",
            "reviewer": "fixture-reviewer",
        },
        "data_plan": {
            "silver_candidate_limit": SOURCE_SILVER_CANDIDATE_LIMITS[source_type],
            **SOURCE_ALLOCATION_TARGETS[source_type],
        },
        "route_requests": {route_id: 3_400 for route_id in ROUTE_IDS},
        "schedule": {
            "starts_on": "2026-10-01",
            "must_finish_by": "2026-10-07",
            "evidence": f"fixture {source_type} schedule review",
        },
        "planned_commitments_usd": {
            "paid-silver-labels": "0.00",
            "specialist": "2.00",
            "gpt": "5.00",
            "data-and-storage": "5.00",
            "contingency": "0.00",
        },
    }


def draft_stage_manifest(stage: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": f"stage-{stage}-fixture",
        "stage": stage,
        "sources": [stage_source(name) for name in STAGE_SOURCES[stage]],
        "route_panel": {
            "inspection_complete": True,
            "routes": [route(route_id) for route_id in ROUTE_IDS],
        },
        "budget": {"evidence": f"fixture Stage {stage} cost projection"},
    }


def draft_stage_2_manifest() -> dict[str, object]:
    return draft_stage_manifest(2)


class StageTwoGateTests(unittest.TestCase):
    """Stage 2 starts only after each new source passes its own gate."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runner = StageRun(
            Path(self.temp_dir.name), clock=lambda: "2026-09-28T00:00:00Z"
        )

    def evaluate(self, manifest: Mapping[str, object]) -> dict[str, object]:
        return self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

    def test_both_new_sources_pass_their_own_gate(self) -> None:
        decision = self.evaluate(draft_stage_2_manifest())

        self.assertEqual("build-eligible", decision["decision"])
        self.assertEqual(2, decision["stage"])
        self.assertEqual(["stage-2-build"], decision["permitted_external_actions"])
        evidence = cast(dict[str, Any], decision["evidence"])
        self.assertEqual(set(STAGE_SOURCES[2]), set(evidence["sources"]))
        self.assertEqual(
            "company-announcements-fixture",
            evidence["sources"]["company-announcements"]["source_id"],
        )
        self.assertEqual(
            4, evidence["schedule"]["regulatory-filings"]["required_days"]
        )
        self.assertEqual("10.00", evidence["budget"]["planned_commitments_usd"]["gpt"])

    def test_a_failed_right_of_one_source_stops_the_stage(self) -> None:
        manifest = draft_stage_2_manifest()
        cast(list[dict[str, object]], manifest["sources"])[1][
            "training_permitted"
        ] = False

        decision = self.evaluate(manifest)

        self.assertEqual("no-build", decision["decision"])
        self.assertEqual("source-rights-failed", decision["stop_reason"])

    def test_one_new_source_alone_cannot_start_the_stage(self) -> None:
        manifest = draft_stage_2_manifest()
        manifest["sources"] = cast(list[object], manifest["sources"])[:1]

        decision = self.evaluate(manifest)

        self.assertEqual("stage-source-incomplete", decision["stop_reason"])

    def test_a_stage_1_source_cannot_enter_the_stage_2_gate(self) -> None:
        manifest = draft_stage_2_manifest()
        cast(list[dict[str, object]], manifest["sources"])[0][
            "source_type"
        ] = "financial-news"

        decision = self.evaluate(manifest)

        self.assertEqual("source-rights-failed", decision["stop_reason"])

    def test_a_wrong_data_plan_stops_the_stage(self) -> None:
        manifest = draft_stage_2_manifest()
        cast(list[dict[str, Any]], manifest["sources"])[0]["data_plan"][
            "training"
        ] = 4_000

        decision = self.evaluate(manifest)

        self.assertEqual("source-data-plan-invalid", decision["stop_reason"])

    def test_a_short_schedule_of_one_source_stops_the_stage(self) -> None:
        manifest = draft_stage_2_manifest()
        cast(list[dict[str, Any]], manifest["sources"])[1]["schedule"][
            "must_finish_by"
        ] = "2026-10-03"

        decision = self.evaluate(manifest)

        self.assertEqual("route-schedule-infeasible", decision["stop_reason"])

    def test_a_route_demand_above_the_daily_rate_stops_the_stage(self) -> None:
        manifest = draft_stage_2_manifest()
        cast(list[dict[str, Any]], manifest["sources"])[0]["route_requests"][
            ROUTE_IDS[0]
        ] = 9_000

        decision = self.evaluate(manifest)

        self.assertEqual("route-schedule-infeasible", decision["stop_reason"])

    def test_the_two_source_budgets_add_against_one_category_limit(self) -> None:
        manifest = draft_stage_2_manifest()
        for source in cast(list[dict[str, Any]], manifest["sources"]):
            source["planned_commitments_usd"]["gpt"] = "20.00"

        decision = self.evaluate(manifest)

        self.assertEqual("category-budget-exceeded", decision["stop_reason"])


class StageTwoSourceDataTests(unittest.TestCase):
    """Each Stage 2 source has its own smaller sealed annex and quota."""

    def test_the_annex_uses_the_smaller_stage_2_limits(self) -> None:
        sealed = seal_candidate_manifest(
            candidate_manifest(2, "regulatory-filings"), "fixture-owner"
        )

        limits = cast(Mapping[str, Any], sealed["annex"])["limits"]
        self.assertEqual(3_333, limits["silver_candidate_limit"])
        self.assertEqual("regulatory-filings", sealed["source"])

    def test_a_stage_1_limit_cannot_seal_a_stage_2_annex(self) -> None:
        draft = candidate_manifest(2, "company-announcements")
        cast(Mapping[str, Any], draft["annex"])["limits"][
            "silver_candidate_limit"
        ] = 6_668

        with self.assertRaises(ValueError) as error:
            seal_candidate_manifest(draft, "fixture-owner")

        self.assertEqual("source-annex-incomplete", str(error.exception))

    def test_a_source_outside_the_stage_cannot_seal(self) -> None:
        with self.assertRaises(ValueError):
            seal_candidate_manifest(
                candidate_manifest(2, "financial-news"), "fixture-owner"
            )

    def test_the_source_adds_two_thousand_accepted_silver_examples(self) -> None:
        manifest, reviews = allocation_manifest(2, "company-announcements")
        sealed = seal_candidate_manifest(manifest, "fixture-owner")

        result = allocate_source(sealed, reviews, inspection_records(sealed, reviews))

        self.assertEqual("complete", result["allocation"])
        self.assertEqual(
            {"training": 2_000, "development": 200, "blind": 400},
            result["selected_counts"],
        )
        self.assertEqual("company-announcements", result["source"])
        self.assertEqual(3_333, result["silver_candidate_limit"])


M3_CHECK: dict[str, object] = {
    "device_id": "m3-fixture",
    "unified_memory_gb": 8,
    "max_sequence_tokens": 512,
    "compatibility_verified": True,
    "local_inference_verified": True,
    "evidence": "fixture device record",
}
GPU_PILOT: dict[str, object] = {
    "gpu_model": "A40",
    "gpu_architecture": "Ampere",
    "gpu_memory_gb": 48,
    "peak_memory_gb": 31.5,
    "max_sequence_tokens": MAX_EXAMPLE_TOKENS,
    "pilot_usd": "4.20",
    "initial_loss": 1.39,
    "final_loss": 0.62,
    "examples_per_second": 8.0,
    "training_examples_per_seed": 12_000,
    "hourly_usd": "0.80",
    "storage_gb": 30,
    "storage_usd_per_gb_month": "0.02",
    "storage_months": 1,
    "tax_rate": "0.00",
}
GPT_FORECAST: dict[str, object] = {
    "measured_split": "development",
    "measured_candidate_ids": ["development-0"],
    "prompt_tokens_per_example": 1200,
    "completion_tokens_per_example": 600,
    "prompt_usd_per_1k_tokens": "0.0012",
    "completion_usd_per_1k_tokens": "0.0060",
    "charged_retry_reserve_attempts": 100,
}


class StageTwoCumulativeTests(unittest.TestCase):
    """One cumulative checkpoint, one decision for each source, one pooled view."""

    stage = 2

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name)
        self.runner = StageRun(self.state_dir, clock=lambda: "2026-10-02T00:00:00Z")
        self.delays: list[float] = []
        self.stage_manifests = {
            1: confirm_manifest(draft_manifest(), "fixture-owner"),
            **{
                stage: confirm_manifest(
                    draft_stage_manifest(stage), "fixture-owner"
                )
                for stage in range(2, self.stage + 1)
            },
        }
        self.sources = list(cumulative_sources(self.stage))
        self.reference: dict[str, dict[str, str]] = {}
        self.fixtures: dict[str, tuple[dict[str, object], ...]] = {}
        for source in self.sources:
            prefix = "" if source == "financial-news" else f"{source}-"
            self.reference[source] = {
                f"{prefix}blind-{index:02d}": RESULT_LABELS[index % 4]
                for index in range(BLIND_REPORT_SIZE)
            }
            self.fixtures[source] = report_source_fixture(
                self.reference[source],
                stage=self.stage_of(source),
                source=source,
            )
        self.gpt_requests: dict[str, int] = {}

    def stage_of(self, source: str) -> int:
        return next(
            stage for stage, names in STAGE_SOURCES.items() if source in names
        )

    def relabels(self, source: str) -> list[dict[str, object]]:
        return [
            {
                "candidate_id": candidate_id,
                "label": label,
                "labeled_at": "2026-10-02T00:00:00Z",
            }
            for candidate_id, label in list(self.reference[source].items())[
                :BLIND_RELABEL_TARGET
            ]
        ]

    def seal_gpt(self, source: str, *, wrong: int = 0) -> dict[str, object]:
        """Seal the GPT blind file of one source under its own stage manifest."""
        sealed, allocation, _ = self.fixtures[source]
        labels = {
            candidate_id: (
                RESULT_LABELS[(RESULT_LABELS.index(label) + 1) % 4]
                if index < wrong
                else label
            )
            for index, (candidate_id, label) in enumerate(
                self.reference[source].items()
            )
        }
        transport = LabelledGptTransport(
            {
                blind_passage(index, source): labels[candidate_id]
                for index, candidate_id in enumerate(self.reference[source])
            }
        )
        result = self.runner.predict_blind_gpt(
            self.stage_manifests[self.stage_of(source)],
            sealed,
            allocation,
            transport,
            forecast=GPT_FORECAST,
            sleep=self.delays.append,
        )
        self.gpt_requests[source] = (
            self.gpt_requests.get(source, 0) + len(transport.requests)
        )
        return result

    def train(self, *, wrong: int = 0) -> dict[str, object]:
        labels = {
            candidate_id: (
                RESULT_LABELS[(RESULT_LABELS.index(label) + 1) % 4]
                if index < wrong
                else label
            )
            for source in self.sources
            for index, (candidate_id, label) in enumerate(
                self.reference[source].items()
            )
        }
        self.backend = FakeTrainingBackend(blind_labels=labels)
        return self.runner.train_specialist(
            self.stage_manifests[self.stage],
            [
                {
                    "candidate_manifest": self.fixtures[source][0],
                    "allocation": self.fixtures[source][1],
                    "aggregation": self.fixtures[source][2],
                }
                for source in self.sources
            ],
            self.backend,
            device_checks={"m3": M3_CHECK, "gpu_pilot": GPU_PILOT},
        )

    def report(self) -> dict[str, object]:
        return self.runner.report_stage(
            self.stage_manifests[self.stage],
            [
                {
                    "candidate_manifest": self.fixtures[source][0],
                    "allocation": self.fixtures[source][1],
                    "relabels": self.relabels(source),
                }
                for source in self.sources
            ],
        )

    def complete_run(self, *, wrong: int = 0) -> dict[str, object]:
        for source in self.sources:
            self.seal_gpt(source)
        self.train(wrong=wrong)
        return self.report()

    def test_one_cumulative_checkpoint_trains_on_every_source(self) -> None:
        for source in self.sources:
            self.seal_gpt(source)

        prediction_file = self.train()

        count = len(self.sources)
        self.assertEqual("sealed", prediction_file["specialist_predictions"])
        self.assertEqual(self.stage, prediction_file["stage"])
        self.assertEqual(self.sources, prediction_file["sources"])
        self.assertEqual(
            BLIND_REPORT_SIZE * count, prediction_file["prediction_count"]
        )
        config = self.backend.trainings[0]
        self.assertEqual(2 * count, len(cast(list[Any], config["training"])))
        self.assertEqual(4 * count, len(cast(list[Any], config["development"])))
        self.assertEqual(3, len(self.backend.trainings))

    def test_a_missing_earlier_source_stops_the_cumulative_run(self) -> None:
        result = self.runner.train_specialist(
            self.stage_manifests[self.stage],
            [
                {
                    "candidate_manifest": self.fixtures[source][0],
                    "allocation": self.fixtures[source][1],
                    "aggregation": self.fixtures[source][2],
                }
                for source in STAGE_SOURCES[self.stage]
            ],
            FakeTrainingBackend(),
            device_checks={"m3": M3_CHECK, "gpu_pilot": GPU_PILOT},
        )

        self.assertEqual("cumulative-sources-incomplete", result["stop_reason"])

    def test_each_source_receives_its_own_decision(self) -> None:
        report = self.complete_run()

        decision = cast(Mapping[str, Any], report["decision"])
        self.assertEqual("complete", report["report"])
        self.assertEqual(self.stage, report["stage"])
        self.assertEqual(self.sources, report["sources"])
        self.assertEqual(
            [
                source
                for source in self.sources
                if source not in STAGE_SOURCES[self.stage]
            ],
            report["regression_sources"],
        )
        self.assertEqual(
            {source: "pass" for source in self.sources},
            decision["source_guardrail"],
        )
        self.assertEqual("pass", decision["stage_guardrail"])
        by_source = cast(Mapping[str, Any], report["metrics"])["by_source"]
        self.assertEqual(set(self.sources), set(by_source))
        for source in self.sources:
            self.assertEqual(1.0, by_source[source]["specialist"]["macro_f1"])
            self.assertEqual(
                BLIND_RELABEL_TARGET,
                by_source[source]["self_consistency"]["example_count"],
            )

    def test_the_pooled_score_cannot_hide_a_failed_source(self) -> None:
        for source in self.sources:
            # Only the answers of the last new source are wrong.
            self.seal_gpt(source)
        labels = {}
        for source in self.sources:
            for index, (candidate_id, label) in enumerate(
                self.reference[source].items()
            ):
                labels[candidate_id] = (
                    RESULT_LABELS[(RESULT_LABELS.index(label) + 1) % 4]
                    if source == self.sources[-1] and index < 32
                    else label
                )
        self.runner.train_specialist(
            self.stage_manifests[self.stage],
            [
                {
                    "candidate_manifest": self.fixtures[source][0],
                    "allocation": self.fixtures[source][1],
                    "aggregation": self.fixtures[source][2],
                }
                for source in self.sources
            ],
            FakeTrainingBackend(blind_labels=labels),
            device_checks={"m3": M3_CHECK, "gpu_pilot": GPU_PILOT},
        )

        report = self.report()

        decision = cast(Mapping[str, Any], report["decision"])
        pooled = cast(Mapping[str, Any], report["metrics"])["pooled"]
        self.assertEqual("fail", decision["source_guardrail"][self.sources[-1]])
        self.assertEqual("pass", decision["source_guardrail"]["financial-news"])
        self.assertEqual("fail", decision["stage_guardrail"])
        self.assertTrue(pooled["diagnostic_only"])
        # The pooled number looks better than the source that failed, and it
        # still cannot make the stage pass.
        by_source = cast(Mapping[str, Any], report["metrics"])["by_source"]
        self.assertGreater(
            pooled["macro_f1_difference"],
            by_source[self.sources[-1]]["macro_f1_difference"],
        )

    def test_the_regression_source_reuses_its_sealed_gpt_file(self) -> None:
        first = self.seal_gpt("financial-news")
        self.assertEqual(BLIND_REPORT_SIZE, self.gpt_requests["financial-news"])

        # The Stage 2 run asks again under the Stage 2 manifest.
        again = self.seal_gpt("financial-news")

        self.assertEqual(first, again)
        self.assertEqual(BLIND_REPORT_SIZE, self.gpt_requests["financial-news"])
        self.assertEqual(
            1,
            sum(
                1
                for record in self.runner.gpt_blind_records()
                if record.get("event") == "gpt-blind-predictions-sealed"
                and record.get("source") == "financial-news"
            ),
        )

    def bundle(self, source: str, field: str = "aggregation") -> dict[str, object]:
        return {
            "candidate_manifest": self.fixtures[source][0],
            "allocation": self.fixtures[source][1],
            field: self.fixtures[source][2],
        }

    def test_a_repeated_candidate_id_stops_the_cumulative_training(self) -> None:
        bundles = [self.bundle(source) for source in self.sources]
        # The second source repeats the manifest and allocation of the first.
        bundles[1] = {
            **bundles[1],
            "candidate_manifest": self.fixtures["financial-news"][0],
            "allocation": self.fixtures["financial-news"][1],
        }

        result = self.runner.train_specialist(
            self.stage_manifests[self.stage],
            bundles,
            FakeTrainingBackend(),
            device_checks={"m3": M3_CHECK, "gpu_pilot": GPU_PILOT},
        )

        self.assertEqual("cumulative-sources-incomplete", result["stop_reason"])

    def test_a_repeated_blind_candidate_id_stops_the_report(self) -> None:
        self.complete_run()
        sources = [
            {
                "candidate_manifest": self.fixtures[source][0],
                "allocation": self.fixtures[source][1],
                "relabels": self.relabels(source),
            }
            for source in self.sources
        ]
        # The last source allocation now names a financial-news example.
        allocation = cast(Mapping[str, Any], sources[-1]["allocation"])
        allocation["blind"][0]["candidate_id"] = "blind-00"

        result = self.runner.report_stage(self.stage_manifests[self.stage], sources)

        self.assertEqual("duplicate-candidate-id", result["stop_reason"])

    def test_the_report_marks_only_the_last_stage_as_final(self) -> None:
        report = self.complete_run()

        claim = cast(Mapping[str, Any], report["claim"])
        self.assertEqual(self.stage == 3, claim["final_staged_decision"])
        self.assertIn("company-only", cast(str, claim["scope"]))

    def test_the_checkpoint_record_keeps_each_source_development_result(self) -> None:
        for source in self.sources:
            self.seal_gpt(source)

        prediction_file = self.train()

        checkpoint = cast(list[Mapping[str, Any]], prediction_file["checkpoints"])[0]
        self.assertEqual(
            set(self.sources), set(checkpoint["development_macro_f1_by_source"])
        )


class StageThreeGateTests(unittest.TestCase):
    """Stage 3 starts only after both final sources pass their own gate."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.runner = StageRun(
            Path(self.temp_dir.name), clock=lambda: "2026-09-28T00:00:00Z"
        )

    def evaluate(self, manifest: Mapping[str, object]) -> dict[str, object]:
        return self.runner.evaluate(confirm_manifest(manifest, "fixture-owner"))

    def test_both_final_sources_pass_their_own_gate(self) -> None:
        decision = self.evaluate(draft_stage_manifest(3))

        self.assertEqual("build-eligible", decision["decision"])
        self.assertEqual(3, decision["stage"])
        self.assertEqual(["stage-3-build"], decision["permitted_external_actions"])
        evidence = cast(dict[str, Any], decision["evidence"])
        self.assertEqual(set(STAGE_SOURCES[3]), set(evidence["sources"]))

    def test_one_final_source_alone_cannot_start_the_stage(self) -> None:
        manifest = draft_stage_manifest(3)
        manifest["sources"] = cast(list[object], manifest["sources"])[:1]

        decision = self.evaluate(manifest)

        self.assertEqual("stage-source-incomplete", decision["stop_reason"])

    def test_a_stage_2_source_cannot_enter_the_stage_3_gate(self) -> None:
        manifest = draft_stage_manifest(3)
        cast(list[dict[str, object]], manifest["sources"])[0][
            "source_type"
        ] = "regulatory-filings"

        decision = self.evaluate(manifest)

        self.assertEqual("source-rights-failed", decision["stop_reason"])

    def test_a_failed_right_of_one_final_source_stops_the_stage(self) -> None:
        manifest = draft_stage_manifest(3)
        cast(list[dict[str, object]], manifest["sources"])[1][
            "weight_release_permitted"
        ] = False

        decision = self.evaluate(manifest)

        self.assertEqual("source-rights-failed", decision["stop_reason"])

    def test_each_final_source_keeps_the_smaller_allocation(self) -> None:
        for source in STAGE_SOURCES[3]:
            sealed = seal_candidate_manifest(
                candidate_manifest(3, source), "fixture-owner"
            )
            limits = cast(Mapping[str, Any], sealed["annex"])["limits"]
            self.assertEqual(3_333, limits["silver_candidate_limit"])
            self.assertEqual(
                {"training": 2_000, "development": 200, "blind": 400},
                SOURCE_ALLOCATION_TARGETS[source],
            )
        self.assertEqual(20_000, sum(SOURCE_SILVER_CANDIDATE_LIMITS.values()))


class StageThreeCumulativeTests(StageTwoCumulativeTests):
    """Stage 3 trains one final checkpoint and decides all five sources."""

    stage = 3

    def test_all_five_sources_receive_a_separate_final_decision(self) -> None:
        report = self.complete_run()

        decision = cast(Mapping[str, Any], report["decision"])
        claim = cast(Mapping[str, Any], report["claim"])
        self.assertEqual(5, len(self.sources))
        self.assertEqual(
            {source: "pass" for source in self.sources},
            decision["source_guardrail"],
        )
        self.assertEqual(
            ["financial-news", "company-announcements", "regulatory-filings"],
            report["regression_sources"],
        )
        self.assertTrue(claim["final_staged_decision"])
        self.assertEqual(self.sources, claim["tested_sources"])
        for phrase in ("natural-distribution", "general-parity", "trading"):
            self.assertIn(phrase, cast(str, claim["scope"]))

    def test_an_earlier_source_reuses_its_sealed_gpt_file(self) -> None:
        self.complete_run()

        for source in ("financial-news", "company-announcements"):
            self.assertEqual(BLIND_REPORT_SIZE, self.gpt_requests[source])
