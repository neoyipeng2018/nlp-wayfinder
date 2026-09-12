"""Safe Stage 1 feasibility gate and append-only audit records."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as metadata_version
from pathlib import Path
from typing import Any, NamedTuple, Protocol, cast


EXPECTED_ROUTE_IDS = (
    "mistral/mistral-medium-3-5",
    "cf/@cf/zai-org/glm-4.7-flash",
    "groq/qwen/qwen3.6-27b",
)

MODERNBERT_MODEL_ID = "answerdotai/ModernBERT-base"
MODERNBERT_REVISION = "8949b909ec900327062f0ebf497f51aef5e6f0c8"
MAX_EXAMPLE_TOKENS = 1_024
STAGE_1_ASPECTS = (
    "financial performance",
    "demand and commercial traction",
    "operations, supply, and capacity",
    "outlook and expectations",
)
RESULT_LABELS = (
    "positive",
    "neutral",
    "negative",
    "insufficient evidence",
)
EXAMPLE_CONSUMERS = (
    "human",
    "labeling-route",
    "specialist",
    "gpt",
)
CANDIDATE_ORDER_SALT = "20260905"
CANDIDATE_SPLITS = ("training", "development", "blind")
STAGE_1_ALLOCATION_TARGETS = {
    "training": 4_000,
    "development": 200,
    "blind": 400,
}
BLIND_CELL_TARGET = 25
BLIND_RELABEL_SEED = "20260905"
BLIND_RELABEL_TARGET = 60
BLIND_WASHOUT_DAYS = 14
SOURCE_ANNEX_FIELDS = (
    "acquisition",
    "rights",
    "extraction",
    "normalization",
    "target_and_aspect_expansion",
    "grouping",
    "duplicate_review",
    "split_rules",
    "limits",
    "software_versions",
)
SPLIT_BOUNDARY_FIELDS = tuple(
    f"{split}_{boundary}_on"
    for split in CANDIDATE_SPLITS
    for boundary in ("starts", "ends")
)

BUDGET_LIMITS = {
    "paid-silver-labels": Decimal("0.00"),
    "specialist": Decimal("35.00"),
    "gpt": Decimal("25.00"),
    "data-and-storage": Decimal("20.00"),
    "contingency": Decimal("20.00"),
}
TOTAL_BUDGET_LIMIT = Decimal("100.00")

CROWD_KIT_VERSION = "1.4.2"
SILVER_DS_ITERATIONS = 100
SILVER_DS_TOLERANCE = 1e-8
SILVER_PROBABILITY_FLOOR = 1e-10
SILVER_CALIBRATION_SEED = "20260905"
SILVER_CALIBRATION_FOLDS = 5
SILVER_CALIBRATION_RANGE = (0.05, 10.0)
SILVER_CALIBRATION_STEPS = 80
SILVER_MIN_VALID_VOTES = 2
SILVER_MIN_PROBABILITY = 0.70
SILVER_TIE_TOLERANCE = 1e-12
SILVER_MIN_DEVELOPMENT_CLASS = 25

GPT_ROUTE_ID = "cx/gpt-5.6-sol-medium"
GPT_REASONING_EFFORT = "medium"
GPT_RETRY_DELAYS_SECONDS = (5.0, 20.0)
GPT_MAX_ATTEMPTS = len(GPT_RETRY_DELAYS_SECONDS) + 1
GPT_MAX_OUTPUT_TOKENS = 2_048
GPT_BLIND_FIRST_ATTEMPTS = 2_000
GPT_FORECAST_FIELDS = (
    "measured_split",
    "measured_candidate_ids",
    "prompt_tokens_per_example",
    "completion_tokens_per_example",
    "prompt_usd_per_1k_tokens",
    "completion_usd_per_1k_tokens",
    "charged_retry_reserve_attempts",
)
BLIND_LABEL_FIELDS = ("label", "reference_label", "silver_label", "labeled_at")

SPECIALIST_SEEDS = (1, 2, 3)
SPECIALIST_OPERATIONAL_REPEATS = 1
SPECIALIST_PILOT_LIMIT_USD = Decimal("5.00")
SPECIALIST_COMPATIBILITY_TOKENS = 512
SPECIALIST_MINIMUM_DEVICE_MEMORY_GB = 8
SPECIALIST_GPU_ARCHITECTURES = (
    "ampere",
    "ada lovelace",
    "hopper",
    "blackwell",
)
SPECIALIST_M3_FIELDS = (
    "device_id",
    "unified_memory_gb",
    "max_sequence_tokens",
    "compatibility_verified",
    "local_inference_verified",
    "evidence",
)
SPECIALIST_PILOT_FIELDS = (
    "gpu_model",
    "gpu_architecture",
    "gpu_memory_gb",
    "peak_memory_gb",
    "max_sequence_tokens",
    "pilot_usd",
    "initial_loss",
    "final_loss",
    "examples_per_second",
    "training_examples_per_seed",
    "hourly_usd",
    "storage_gb",
    "storage_usd_per_gb_month",
    "storage_months",
    "tax_rate",
)
SPECIALIST_TRAIN_RESULT_FIELDS = (
    "checkpoint_id",
    "model_id",
    "revision",
    "max_sequence_tokens",
    "head_labels",
    "development_predictions",
)

RIGHTS_FIELDS = (
    "access_permitted",
    "private_evaluation_permitted",
    "training_permitted",
    "weight_release_permitted",
    "text_redistribution_permitted",
)

ROUTE_ELIGIBILITY_FIELDS = (
    "model_identity_verified",
    "non_gpt_verified",
    "account_free_limit_verified",
    "training_use_permitted",
    "audit_fields_supported",
    "no_paid_overflow",
)

FORBIDDEN_ROUTE_PARTS = {"auto", "free", "fusion", "fallback", "latest"}


class AuditLogError(ValueError):
    """Raised when an append-only record is invalid or was changed."""


class CostLimitError(ValueError):
    """Raised before a cost record could exceed a fixed limit."""


class Tokenizer(Protocol):
    """The tokenizer operation that example admission needs."""

    def __call__(self, text: str, **kwargs: object) -> Mapping[str, object]: ...


class OmniRouteResponse(NamedTuple):
    """One non-streaming OmniRoute transport response."""

    status_code: int
    headers: Mapping[str, str]
    body: Mapping[str, object]


class VoteTransport(Protocol):
    """The fixed-route transport operation that vote collection needs."""

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse: ...


class TrainingBackend(Protocol):
    """Train one specialist checkpoint and predict on the local device."""

    def train(self, config: Mapping[str, object]) -> Mapping[str, object]: ...

    def predict(
        self, checkpoint_id: str, examples: Sequence[Mapping[str, object]]
    ) -> Mapping[str, object]: ...


class OmniRouteHttpTransport:
    """Send fixed-route requests to the OmniRoute chat endpoint."""

    def __init__(self, base_url: str, *, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def complete(
        self, request: Mapping[str, object], timeout_seconds: float
    ) -> OmniRouteResponse:
        # The dedicated provider endpoint validates the model against one
        # provider. The shared endpoint can resolve a combo of the same name.
        provider, model = str(request["model"]).split("/", 1)
        request_body = {**request, "model": model}
        headers = {
            "Content-Type": "application/json",
            "X-OmniRoute-No-Cache": "true",
            "X-OmniRoute-No-Memory": "true",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = urllib.request.Request(
            f"{self.base_url}/v1/providers/{provider}/chat/completions",
            data=_canonical_json(request_body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                http_request, timeout=timeout_seconds
            ) as http_response:
                status_code = http_response.status
                response_headers = dict(http_response.headers.items())
                raw_body = http_response.read()
        except urllib.error.HTTPError as error:
            status_code = error.code
            response_headers = dict(error.headers.items())
            raw_body = error.read()
        except (TimeoutError, socket.timeout) as error:
            raise TimeoutError("The OmniRoute request timed out.") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise TimeoutError("The OmniRoute request timed out.") from error
            raise OSError("The OmniRoute request failed.") from error
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"raw_response_sha256": hashlib.sha256(raw_body).hexdigest()}
        if not isinstance(body, Mapping):
            body = {"value": body}
        return OmniRouteResponse(status_code, response_headers, body)


LABELING_SYSTEM_PROMPT = (
    "Classify the supplied company and aspect from only the supplied financial "
    "passage. Use one label: positive, neutral, negative, or insufficient "
    "evidence. Return only a JSON object with one label field. Do not add an "
    "explanation."
)


GPT_BLIND_SYSTEM_PROMPT = (
    "Classify the supplied company and aspect from only the supplied financial "
    "passage. Use the evidence about the supplied company. Use the most specific "
    "aspect that the evidence supports and do not copy one claim to another "
    "aspect. Treat a clearly attributed claim as evidence, but do not change its "
    "weight for the role of the speaker. An explicit statement of no material "
    "effect supports neutral for that aspect. Use insufficient evidence when the "
    "evidence is absent, unclear, about another aspect, or conflicting without a "
    "resolution. Use one label: positive, neutral, negative, or insufficient "
    "evidence. Return only a JSON object with one label field. Do not add an "
    "explanation."
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _is_fixed_route_id(value: object) -> bool:
    if not isinstance(value, str) or value.count("/") < 1:
        return False
    parts = {part.lower() for part in value.split("/") if part}
    return bool(parts) and parts.isdisjoint(FORBIDDEN_ROUTE_PARTS)


def semantic_manifest_sha256(manifest: Mapping[str, object]) -> str:
    """Return the hash of all semantic fields, except confirmation evidence."""
    semantic = copy.deepcopy(dict(manifest))
    semantic.pop("confirmation", None)
    return hashlib.sha256(_canonical_json(semantic).encode("utf-8")).hexdigest()


def confirm_manifest(
    manifest: Mapping[str, object],
    confirmed_by: str,
    *,
    confirmed_at: str | None = None,
) -> dict[str, object]:
    """Return a copy with evidence that confirms its current semantic content."""
    if not confirmed_by.strip():
        raise ValueError("The confirmed-by value must contain text.")
    confirmed = copy.deepcopy(dict(manifest))
    confirmed["confirmation"] = {
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at or _now(),
        "semantic_sha256": semantic_manifest_sha256(confirmed),
    }
    return confirmed


def candidate_order_sha256(
    stage: int,
    source: str,
    split: str,
    candidate_id: str,
) -> str:
    """Return the frozen candidate-order value."""
    expression = (
        f"nlp-wayfinder{stage}{source}{split}{candidate_id}{CANDIDATE_ORDER_SALT}"
    )
    return hashlib.sha256(expression.encode("utf-8")).hexdigest()


def _candidate_manifest_sha256(manifest: Mapping[str, object]) -> str:
    semantic = copy.deepcopy(dict(manifest))
    semantic.pop("seal", None)
    return hashlib.sha256(_canonical_json(semantic).encode("utf-8")).hexdigest()


def _annex_record(
    annex: Mapping[str, object],
    name: str,
    required_fields: tuple[str, ...],
) -> Mapping[str, object]:
    record = annex.get(name)
    if not isinstance(record, Mapping) or any(
        not record.get(field) for field in required_fields
    ):
        raise ValueError("source-annex-incomplete")
    return record


def _split_periods(annex: Mapping[str, object]) -> dict[str, tuple[date, date]]:
    split_rules = _annex_record(annex, "split_rules", SPLIT_BOUNDARY_FIELDS)
    try:
        periods = {
            split: (
                date.fromisoformat(str(split_rules[f"{split}_starts_on"])),
                date.fromisoformat(str(split_rules[f"{split}_ends_on"])),
            )
            for split in CANDIDATE_SPLITS
        }
    except ValueError as error:
        raise ValueError("source-annex-incomplete") from error
    prior_end: date | None = None
    for starts_on, ends_on in periods.values():
        if starts_on > ends_on or (prior_end is not None and starts_on <= prior_end):
            raise ValueError("split-periods-overlap")
        prior_end = ends_on
    return periods


def _candidate_split(
    published_at: object,
    periods: Mapping[str, tuple[date, date]],
) -> str:
    if not isinstance(published_at, str):
        raise ValueError("A candidate publication time is not valid.")
    try:
        published_on = date.fromisoformat(published_at[:10])
    except ValueError as error:
        raise ValueError("A candidate publication time is not valid.") from error
    for split, (starts_on, ends_on) in periods.items():
        if starts_on <= published_on <= ends_on:
            return split
    raise ValueError("candidate-outside-split-periods")


def seal_candidate_manifest(
    manifest: Mapping[str, object],
    sealed_by: str,
    *,
    sealed_at: str | None = None,
) -> dict[str, object]:
    """Validate, order, and seal one Stage 1 candidate manifest."""
    if not sealed_by.strip():
        raise ValueError("The sealed-by value must contain text.")
    sealed = copy.deepcopy(dict(manifest))
    stage = sealed.get("stage")
    source = sealed.get("source")
    candidates = sealed.get("candidates")
    if (
        sealed.get("schema_version") != 1
        or stage != 1
        or source != "financial-news"
        or not isinstance(candidates, list)
        or not candidates
    ):
        raise ValueError("The candidate manifest is not valid for Stage 1.")
    annex = sealed.get("annex")
    if not isinstance(annex, Mapping) or any(
        field not in annex for field in SOURCE_ANNEX_FIELDS
    ):
        raise ValueError("source-annex-incomplete")
    _annex_record(annex, "acquisition", ("method", "evidence"))
    rights = _annex_record(annex, "rights", (*RIGHTS_FIELDS, "evidence"))
    if any(rights[field] is not True for field in RIGHTS_FIELDS):
        raise ValueError("source-annex-incomplete")
    for name in (
        "extraction",
        "normalization",
        "target_and_aspect_expansion",
        "grouping",
    ):
        _annex_record(annex, name, ("method",))
    _annex_record(
        annex,
        "duplicate_review",
        ("exact_method", "near_method", "completed_at"),
    )
    limits = _annex_record(
        annex,
        "limits",
        ("silver_candidate_limit", "development_target", "blind_target"),
    )
    if (
        limits["silver_candidate_limit"] != 6_668
        or limits["development_target"] != 200
        or limits["blind_target"] != 400
    ):
        raise ValueError("source-annex-incomplete")
    software_versions = annex.get("software_versions")
    if not isinstance(software_versions, Mapping) or not software_versions:
        raise ValueError("source-annex-incomplete")
    periods = _split_periods(annex)

    ordered: list[dict[str, object]] = []
    candidate_ids: set[str] = set()
    content_hashes: set[str] = set()
    near_duplicate_groups: set[str] = set()
    event_group_splits: dict[str, str] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("A candidate record is not valid.")
        candidate_copy = copy.deepcopy(dict(candidate))
        candidate_id = candidate_copy.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError("A candidate ID must contain text.")
        split = _candidate_split(candidate_copy.get("published_at"), periods)
        supplied_split = candidate_copy.get("split")
        if supplied_split is not None and supplied_split != split:
            raise ValueError("candidate-in-wrong-split-period")
        candidate_copy["split"] = split
        if candidate_id in candidate_ids:
            raise ValueError("A candidate ID occurs more than once.")
        candidate_ids.add(candidate_id)
        event_group_id = candidate_copy.get("event_group_id")
        if not isinstance(event_group_id, str) or not event_group_id.strip():
            raise ValueError("An event group ID must contain text.")
        prior_split = event_group_splits.setdefault(event_group_id, str(split))
        if prior_split != split:
            raise ValueError("event-group-crosses-splits")
        normalized_passage = candidate_copy.get("normalized_passage")
        if not isinstance(normalized_passage, str) or not normalized_passage.strip():
            raise ValueError("A normalized passage must contain text.")
        content_sha256 = hashlib.sha256(
            normalized_passage.encode("utf-8")
        ).hexdigest()
        supplied_content_sha256 = candidate_copy.get("content_sha256")
        if (
            supplied_content_sha256 is not None
            and supplied_content_sha256 != content_sha256
        ):
            raise ValueError("candidate-content-hash-mismatch")
        candidate_copy["content_sha256"] = content_sha256
        if content_sha256 in content_hashes:
            raise ValueError("exact-duplicate-unresolved")
        content_hashes.add(content_sha256)
        if candidate_copy.get("near_duplicate_reviewed") is not True:
            raise ValueError("near-duplicate-review-incomplete")
        near_group = candidate_copy.get("near_duplicate_group_id")
        if near_group is not None:
            if not isinstance(near_group, str) or not near_group.strip():
                raise ValueError("A near-duplicate group ID is not valid.")
            if near_group in near_duplicate_groups:
                raise ValueError("near-duplicate-unresolved")
            near_duplicate_groups.add(near_group)
        candidate_copy["order_sha256"] = candidate_order_sha256(
            stage, source, str(split), candidate_id
        )
        ordered.append(candidate_copy)
    ordered.sort(key=lambda candidate: str(candidate["order_sha256"]))
    sealed["candidates"] = ordered
    sealed["seal"] = {
        "sealed_by": sealed_by,
        "sealed_at": sealed_at or _now(),
        "semantic_sha256": _candidate_manifest_sha256(sealed),
    }
    return sealed


def _is_valid_sealed_candidate_manifest(manifest: Mapping[str, object]) -> bool:
    seal = manifest.get("seal")
    if not isinstance(seal, Mapping) or not all(
        seal.get(field) for field in ("sealed_by", "sealed_at", "semantic_sha256")
    ):
        return False
    if seal["semantic_sha256"] != _candidate_manifest_sha256(manifest):
        return False
    try:
        rebuilt = seal_candidate_manifest(
            manifest,
            str(seal["sealed_by"]),
            sealed_at=str(seal["sealed_at"]),
        )
    except ValueError:
        return False
    return _canonical_json(rebuilt.get("candidates")) == _canonical_json(
        manifest.get("candidates")
    )


def _allocation_stop(
    reason: str,
    *,
    inspected_silver: int = 0,
    selected: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
) -> dict[str, object]:
    selected = selected or {}
    return {
        "allocation": "stopped",
        "stop_reason": reason,
        "silver_candidates_inspected": inspected_silver,
        "selected_counts": {
            split: len(selected.get(split, ())) for split in CANDIDATE_SPLITS
        },
    }


def _parse_utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("allocation-review-invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("allocation-review-invalid") from error
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("allocation-review-invalid")
    return parsed


def _selected_record(
    candidate: Mapping[str, object], review: Mapping[str, object]
) -> dict[str, object]:
    return {
        "candidate_id": candidate["candidate_id"],
        "event_group_id": candidate["event_group_id"],
        "company_id": candidate["company_id"],
        "aspect": candidate["aspect"],
        "label": review["label"],
        "labeled_at": review["labeled_at"],
    }


def _relabel_sample(blind: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    cells = [(aspect, label) for aspect in STAGE_1_ASPECTS for label in RESULT_LABELS]

    def rank(item: Mapping[str, object]) -> str:
        rank_input = (
            "nlp-wayfinder1financial-newsblind-relabel"
            f"{item['candidate_id']}{BLIND_RELABEL_SEED}"
        )
        return hashlib.sha256(rank_input.encode("utf-8")).hexdigest()

    ranked_cells = {
        cell: sorted(
            (
                item
                for item in blind
                if (item["aspect"], item["label"]) == cell
            ),
            key=rank,
        )
        for cell in cells
    }
    chosen: list[Mapping[str, object]] = []
    fourth_candidates: list[Mapping[str, object]] = []
    for cell in cells:
        chosen.extend(ranked_cells[cell][:3])
        fourth_candidates.append(ranked_cells[cell][3])
    chosen.extend(
        sorted(fourth_candidates, key=rank)[: BLIND_RELABEL_TARGET - len(chosen)]
    )
    chosen.sort(key=rank)

    sample: list[dict[str, object]] = []
    for item in chosen:
        relabel_not_before = _parse_utc_timestamp(item["labeled_at"]) + timedelta(
            days=BLIND_WASHOUT_DAYS
        )
        sample.append(
            {
                "candidate_id": item["candidate_id"],
                "aspect": item["aspect"],
                "label": item["label"],
                "relabel_not_before": relabel_not_before.isoformat().replace(
                    "+00:00", "Z"
                ),
            }
        )
    return sample


def _select_ordered_split(
    candidates: Sequence[Mapping[str, object]],
    review_by_id: Mapping[str, Mapping[str, object]],
    inspected_ids: set[str],
    split: str,
    target: int,
) -> tuple[list[dict[str, object]], int]:
    inspected = [
        candidate
        for candidate in candidates
        if candidate["split"] == split
        and str(candidate["candidate_id"]) in inspected_ids
    ]
    selected: list[dict[str, object]] = []
    reached_target_at: int | None = None
    for index, candidate in enumerate(inspected):
        review = review_by_id.get(str(candidate["candidate_id"]))
        if review is not None and review["disposition"] == "accepted":
            selected.append(_selected_record(candidate, review))
            if len(selected) == target:
                reached_target_at = index
                break
    if reached_target_at is not None and reached_target_at + 1 < len(inspected):
        raise ValueError("allocation-inspection-after-quota")
    return selected, len(inspected)


class _BlindBalanceScore(NamedTuple):
    event_excess: int
    company_excess: int
    unseen_issuer_deficit: int
    event_group_deficit: int


class _BlindVisitFrame(NamedTuple):
    cell_index: int
    position: int
    cell_count: int


class _BlindUndoFrame(NamedTuple):
    candidate: dict[str, object]


def _blind_balance_score(
    selected: Sequence[Mapping[str, object]], seen_issuers: set[object]
) -> _BlindBalanceScore:
    event_counts = Counter(item["event_group_id"] for item in selected)
    company_counts = Counter(item["company_id"] for item in selected)
    unseen_issuers = {
        item["company_id"]
        for item in selected
        if item["company_id"] not in seen_issuers
    }
    return _BlindBalanceScore(
        event_excess=sum(max(0, count - 2) for count in event_counts.values()),
        company_excess=sum(max(0, count - 5) for count in company_counts.values()),
        unseen_issuer_deficit=max(0, 100 - len(unseen_issuers)),
        event_group_deficit=max(0, 320 - len(event_counts)),
    )


def _select_balanced_blind(
    candidates: Sequence[Mapping[str, object]],
    review_by_id: Mapping[str, Mapping[str, object]],
    inspected_ids: set[str],
    seen_issuers: set[object],
) -> tuple[list[dict[str, object]], str | None]:
    cells = [(aspect, label) for aspect in STAGE_1_ASPECTS for label in RESULT_LABELS]
    pools: dict[tuple[str, str], list[dict[str, object]]] = {}
    for cell in cells:
        pool = [
            _selected_record(candidate, review_by_id[str(candidate["candidate_id"])])
            for candidate in candidates
            if candidate["split"] == "blind"
            and str(candidate["candidate_id"]) in inspected_ids
            and candidate["aspect"] == cell[0]
            and (review := review_by_id.get(str(candidate["candidate_id"])))
            is not None
            and review["label"] == cell[1]
            and review["disposition"] == "accepted"
        ]
        pools[cell] = pool
        if len(pool) < BLIND_CELL_TARGET:
            return [], "blind-cell-quota-unfilled"

    selected: list[dict[str, object]] = []
    event_counts: Counter[object] = Counter()
    company_counts: Counter[object] = Counter()
    unseen_counts: Counter[object] = Counter()

    def remaining_candidates(cell_index: int, position: int) -> list[dict[str, object]]:
        current_cell = cells[cell_index]
        return [
            *pools[current_cell][position:],
            *(
                candidate
                for later_cell in cells[cell_index + 1 :]
                for candidate in pools[later_cell]
            ),
        ]

    def can_still_meet_coverage(cell_index: int, position: int) -> bool:
        remaining = remaining_candidates(cell_index, position)
        possible_events = set(event_counts) | {
            candidate["event_group_id"] for candidate in remaining
        }
        possible_unseen = set(unseen_counts) | {
            candidate["company_id"]
            for candidate in remaining
            if candidate["company_id"] not in seen_issuers
        }
        return len(possible_events) >= 320 and len(possible_unseen) >= 100

    def cell_capacity(pool: Sequence[Mapping[str, object]], position: int) -> int:
        remaining_events = Counter(
            candidate["event_group_id"] for candidate in pool[position:]
        )
        remaining_companies = Counter(
            candidate["company_id"] for candidate in pool[position:]
        )
        event_capacity = sum(
            min(count, max(0, 2 - event_counts[event_group_id]))
            for event_group_id, count in remaining_events.items()
        )
        company_capacity = sum(
            min(count, max(0, 5 - company_counts[company_id]))
            for company_id, count in remaining_companies.items()
        )
        return min(event_capacity, company_capacity)

    frames: list[_BlindVisitFrame | _BlindUndoFrame] = [_BlindVisitFrame(0, 0, 0)]
    solution: list[dict[str, object]] | None = None
    while frames:
        frame = frames.pop()
        if isinstance(frame, _BlindUndoFrame):
            frame_candidate = frame.candidate
            selected.pop()
            event_group_id = frame_candidate["event_group_id"]
            company_id = frame_candidate["company_id"]
            event_counts[event_group_id] -= 1
            company_counts[company_id] -= 1
            if not event_counts[event_group_id]:
                del event_counts[event_group_id]
            if not company_counts[company_id]:
                del company_counts[company_id]
            if company_id not in seen_issuers:
                unseen_counts[company_id] -= 1
                if not unseen_counts[company_id]:
                    del unseen_counts[company_id]
            continue
        cell_index, position, cell_count = frame
        if cell_index == len(cells):
            if len(event_counts) >= 320 and len(unseen_counts) >= 100:
                solution = list(selected)
                break
            continue
        pool = pools[cells[cell_index]]
        if cell_count == BLIND_CELL_TARGET:
            frames.append(_BlindVisitFrame(cell_index + 1, 0, 0))
            continue
        needed = BLIND_CELL_TARGET - cell_count
        if (
            len(pool) - position < needed
            or cell_capacity(pool, position) < needed
            or not can_still_meet_coverage(cell_index, position)
        ):
            continue

        candidate = pool[position]
        if len(pool) - (position + 1) >= needed:
            frames.append(_BlindVisitFrame(cell_index, position + 1, cell_count))
        event_group_id = candidate["event_group_id"]
        company_id = candidate["company_id"]
        if event_counts[event_group_id] < 2 and company_counts[company_id] < 5:
            selected.append(candidate)
            event_counts[event_group_id] += 1
            company_counts[company_id] += 1
            if company_id not in seen_issuers:
                unseen_counts[company_id] += 1
            frames.append(_BlindUndoFrame(candidate))
            frames.append(
                _BlindVisitFrame(cell_index, position + 1, cell_count + 1)
            )

    if solution is not None:
        return solution, None

    first_candidates = [
        candidate
        for cell in cells
        for candidate in pools[cell][:BLIND_CELL_TARGET]
    ]
    score = _blind_balance_score(first_candidates, seen_issuers)
    if score.event_excess or score.event_group_deficit:
        reason = "blind-event-group-balance-failed"
    elif score.company_excess:
        reason = "blind-company-balance-failed"
    else:
        reason = "blind-unseen-issuer-balance-failed"
    return first_candidates, reason


def allocate_stage_1(
    manifest: Mapping[str, object],
    reviews: Sequence[Mapping[str, object]],
    inspection_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Select the complete deterministic Stage 1 data allocation."""
    if not _is_valid_sealed_candidate_manifest(manifest):
        return _allocation_stop("unsealed-annex")
    candidates_value = manifest.get("candidates")
    annex = manifest.get("annex")
    assert isinstance(candidates_value, list)
    assert isinstance(annex, Mapping)
    limits = annex.get("limits")
    assert isinstance(limits, Mapping)

    candidates: list[Mapping[str, object]] = []
    candidate_by_id: dict[str, Mapping[str, object]] = {}
    for candidate in candidates_value:
        if not isinstance(candidate, Mapping):
            raise ValueError("allocation-candidate-invalid")
        candidate_id = candidate.get("candidate_id")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(candidate.get("company_id"), str)
            or not str(candidate["company_id"]).strip()
            or candidate.get("aspect") not in STAGE_1_ASPECTS
        ):
            raise ValueError("allocation-candidate-invalid")
        candidates.append(candidate)
        candidate_by_id[candidate_id] = candidate

    seal = manifest["seal"]
    assert isinstance(seal, Mapping)
    manifest_sha256 = str(seal["semantic_sha256"])
    matching_inspections = [
        record
        for record in inspection_records
        if record.get("manifest_sha256") == manifest_sha256
    ]
    inspected_candidate_ids: list[str] = []
    for record in matching_inspections:
        candidate_id = record.get("candidate_id")
        if (
            record.get("event") != "candidate-inspected"
            or not isinstance(candidate_id, str)
            or candidate_id not in candidate_by_id
            or candidate_id in inspected_candidate_ids
        ):
            raise ValueError("allocation-inspection-invalid")
        inspected_candidate_ids.append(candidate_id)
    expected_inspection_ids = [
        str(candidate["candidate_id"])
        for candidate in candidates[: len(inspected_candidate_ids)]
    ]
    if inspected_candidate_ids != expected_inspection_ids:
        raise ValueError("out-of-order-allocation-inspection")
    inspected_ids = set(inspected_candidate_ids)

    review_by_id: dict[str, Mapping[str, object]] = {}
    for review in reviews:
        if not isinstance(review, Mapping):
            raise ValueError("allocation-review-invalid")
        candidate_id = review.get("candidate_id")
        if (
            not isinstance(candidate_id, str)
            or candidate_id not in candidate_by_id
            or candidate_id in review_by_id
            or review.get("disposition") not in {"accepted", "excluded"}
            or review.get("label") not in RESULT_LABELS
        ):
            raise ValueError("allocation-review-invalid")
        _parse_utc_timestamp(review.get("labeled_at"))
        if candidate_id not in inspected_ids:
            raise ValueError("allocation-review-not-inspected")
        review_by_id[candidate_id] = review

    selected: dict[str, list[dict[str, object]]] = {
        split: [] for split in CANDIDATE_SPLITS
    }

    selected["training"], silver_inspected = _select_ordered_split(
        candidates,
        review_by_id,
        inspected_ids,
        "training",
        STAGE_1_ALLOCATION_TARGETS["training"],
    )
    silver_limit = int(limits["silver_candidate_limit"])
    if silver_inspected > silver_limit:
        return _allocation_stop(
            "silver-candidate-limit-exceeded",
            inspected_silver=silver_inspected,
            selected=selected,
        )
    if len(selected["training"]) < STAGE_1_ALLOCATION_TARGETS["training"]:
        reason = (
            "silver-candidate-limit-exhausted"
            if silver_inspected == silver_limit
            else "silver-quota-unfilled"
        )
        return _allocation_stop(
            reason, inspected_silver=silver_inspected, selected=selected
        )

    selected["development"], _ = _select_ordered_split(
        candidates,
        review_by_id,
        inspected_ids,
        "development",
        STAGE_1_ALLOCATION_TARGETS["development"],
    )
    if len(selected["development"]) < STAGE_1_ALLOCATION_TARGETS["development"]:
        return _allocation_stop(
            "development-quota-unfilled",
            inspected_silver=silver_inspected,
            selected=selected,
        )

    seen_issuers = {
        item["company_id"]
        for split in ("training", "development")
        for item in selected[split]
    }
    selected["blind"], blind_stop_reason = _select_balanced_blind(
        candidates, review_by_id, inspected_ids, seen_issuers
    )
    if blind_stop_reason is not None:
        return _allocation_stop(
            blind_stop_reason,
            inspected_silver=silver_inspected,
            selected=selected,
        )
    unseen_issuers = {
        item["company_id"]
        for item in selected["blind"]
        if item["company_id"] not in seen_issuers
    }
    for item in selected["blind"]:
        item["unseen_issuer"] = item["company_id"] in unseen_issuers

    result: dict[str, object] = {
        "allocation": "complete",
        "stop_reason": None,
        "candidate_manifest_sha256": manifest["seal"]["semantic_sha256"],  # type: ignore[index]
        "silver_candidates_inspected": silver_inspected,
        "silver_candidate_limit": silver_limit,
        "selected_counts": {
            split: len(selected[split]) for split in CANDIDATE_SPLITS
        },
        **selected,
        "blind_relabel_seed": BLIND_RELABEL_SEED,
        "blind_relabel_sample": _relabel_sample(selected["blind"]),
    }
    result["allocation_sha256"] = hashlib.sha256(
        _canonical_json(result).encode("utf-8")
    ).hexdigest()
    return result


class _AppendOnlyJsonl:
    def __init__(self, path: Path, clock: Callable[[], str]) -> None:
        self.path = path
        self.clock = clock

    @staticmethod
    def _record_hash(record: Mapping[str, object]) -> str:
        unhashed = dict(record)
        unhashed.pop("record_sha256", None)
        return hashlib.sha256(_canonical_json(unhashed).encode("utf-8")).hexdigest()

    def _parse(self, text: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        previous_hash: str | None = None
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                raise AuditLogError(
                    f"The append-only record at line {index} is blank."
                )
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise AuditLogError(
                    f"The append-only record at line {index} is not valid."
                ) from error
            if not isinstance(record, dict):
                raise AuditLogError(
                    f"The append-only record at line {index} is not valid."
                )
            if record.get("sequence") != index:
                raise AuditLogError(f"The sequence at line {index} is not valid.")
            if record.get("previous_record_sha256") != previous_hash:
                raise AuditLogError(f"The hash chain breaks at line {index}.")
            expected_hash = self._record_hash(record)
            if record.get("record_sha256") != expected_hash:
                raise AuditLogError(
                    f"The append-only record at line {index} changed."
                )
            previous_hash = expected_hash
            records.append(record)
        return records

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            text = stream.read()
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        return self._parse(text)

    def append(self, payload: Mapping[str, object]) -> dict[str, Any]:
        return self.append_checked(lambda _records: payload)

    def append_checked(
        self,
        payload_factory: Callable[
            [list[dict[str, Any]]], Mapping[str, object]
        ],
    ) -> dict[str, Any]:
        """Check current records and append while one exclusive lock is held."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.seek(0)
            records = self._parse(stream.read())
            payload = payload_factory(records)
            record: dict[str, Any] = {
                "sequence": len(records) + 1,
                "recorded_at": self.clock(),
                "previous_record_sha256": (
                    records[-1]["record_sha256"] if records else None
                ),
                **copy.deepcopy(dict(payload)),
            }
            record["record_sha256"] = self._record_hash(record)
            stream.seek(0, os.SEEK_END)
            stream.write(_canonical_json(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        return record


def _money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("The USD amount is not valid.") from error
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError(
            "The USD amount must be zero or more and have at most two decimals."
        )
    return amount


def _usd(value: Decimal) -> str:
    return f"{value:.2f}"


def _invalid_example(reason: str) -> dict[str, object]:
    return {
        "admission": "rejected",
        "schema_result": "Invalid",
        "stop_reason": reason,
        "allowed_result_labels": list(RESULT_LABELS),
    }


def _is_complete_sentence(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    while stripped and stripped[-1] in {'"', "'", "”", "’"}:
        stripped = stripped[:-1].rstrip()
    return bool(stripped) and stripped[-1] in ".!?"


def _token_count(tokenizer: Tokenizer, text: str) -> int:
    encoded = tokenizer(
        text,
        add_special_tokens=True,
        truncation=False,
        return_attention_mask=False,
        return_token_type_ids=False,
    )
    input_ids = encoded.get("input_ids")
    if (
        not isinstance(input_ids, list)
        or not input_ids
        or isinstance(input_ids[0], list)
    ):
        raise ValueError("The tokenizer did not return one token sequence.")
    return len(input_ids)


def serialize_example(passage: str, company: str, aspect: str) -> str:
    """Serialize the one shared input for all people and systems."""
    return (
        f"Passage:\n{passage}\n\n"
        f"Company:\n{company}\n\n"
        f"Aspect:\n{aspect}"
    )


def admit_example(
    example: Mapping[str, object],
    tokenizer: Tokenizer,
) -> dict[str, object]:
    """Validate and serialize one Stage 1 target–aspect example."""
    company = example.get("company")
    if not isinstance(company, Mapping):
        return _invalid_example("invalid-company")
    if (
        not isinstance(company.get("name"), str)
        or not company["name"].strip()
        or not isinstance(company.get("ticker"), str)
        or not company["ticker"].strip()
        or not isinstance(company.get("exchange"), str)
        or not company["exchange"].strip()
        or company.get("publicly_traded") is not True
    ):
        return _invalid_example("invalid-company")

    aspect = example.get("aspect")
    if aspect not in STAGE_1_ASPECTS:
        return _invalid_example("invalid-aspect")

    label = example.get("label")
    if label is not None and label not in RESULT_LABELS:
        return _invalid_example("invalid-label")

    sentences = example.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        return _invalid_example("invalid-sentence-span")
    positions: list[int] = []
    texts: list[str] = []
    for sentence in sentences:
        if not isinstance(sentence, Mapping):
            return _invalid_example("invalid-sentence-span")
        position = sentence.get("position")
        text = sentence.get("text")
        if (
            not isinstance(position, int)
            or isinstance(position, bool)
            or position < 0
            or not isinstance(text, str)
            or not _is_complete_sentence(text)
        ):
            return _invalid_example("invalid-sentence-span")
        positions.append(position)
        texts.append(text.strip())
    if positions != list(range(positions[0], positions[0] + len(positions))):
        return _invalid_example("nonconsecutive-sentences")

    included_positions = set(positions)
    for key, reason in (
        ("target_evidence_positions", "target-evidence-missing"),
        ("required_evidence_positions", "required-evidence-missing"),
    ):
        evidence_positions = example.get(key)
        if (
            not isinstance(evidence_positions, list)
            or not evidence_positions
            or any(
                not isinstance(position, int)
                or isinstance(position, bool)
                or position not in included_positions
                for position in evidence_positions
            )
        ):
            return _invalid_example(reason)

    passage = " ".join(texts)
    serialized = serialize_example(passage, str(company["name"]).strip(), str(aspect))
    token_count = _token_count(tokenizer, serialized)
    if token_count > MAX_EXAMPLE_TOKENS:
        return _invalid_example("evidence-does-not-fit")

    return {
        "admission": "accepted",
        "schema_result": None,
        "stop_reason": None,
        "allowed_result_labels": list(RESULT_LABELS),
        "label": label,
        "serialized_input": serialized,
        "serialized_input_sha256": hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest(),
        "token_count": token_count,
        "token_limit": MAX_EXAMPLE_TOKENS,
        "consumers": list(EXAMPLE_CONSUMERS),
    }


def load_modernbert_tokenizer() -> Tokenizer:
    """Load the only tokenizer that can admit experiment examples."""
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "Install transformers to use the example admission command."
        ) from error
    return AutoTokenizer.from_pretrained(
        MODERNBERT_MODEL_ID,
        revision=MODERNBERT_REVISION,
    )


def _vote_prompt(candidate: Mapping[str, object]) -> list[dict[str, str]]:
    user_prompt = _canonical_json(
        {
            "passage": candidate["normalized_passage"],
            "company": candidate["company_id"],
            "aspect": candidate["aspect"],
        }
    )
    return [
        {"role": "system", "content": LABELING_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _vote_request(
    route_id: str, candidate: Mapping[str, object]
) -> dict[str, object]:
    return {
        "model": route_id,
        "messages": _vote_prompt(candidate),
        "stream": False,
        "temperature": 0,
        "max_tokens": 20,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "independent_model_vote",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"label": {"enum": list(RESULT_LABELS)}},
                    "required": ["label"],
                    "additionalProperties": False,
                },
            },
        },
        "user": candidate["candidate_id"],
    }


def _gpt_prompt(candidate: Mapping[str, object]) -> list[dict[str, str]]:
    """Build the one zero-shot GPT prompt. It carries no blind label."""
    user_prompt = _canonical_json(
        {
            "passage": candidate["normalized_passage"],
            "company": candidate["company_id"],
            "aspect": candidate["aspect"],
        }
    )
    return [
        {"role": "system", "content": GPT_BLIND_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _gpt_request(candidate: Mapping[str, object]) -> dict[str, object]:
    return {
        "model": GPT_ROUTE_ID,
        "messages": _gpt_prompt(candidate),
        "stream": False,
        "reasoning_effort": GPT_REASONING_EFFORT,
        "max_tokens": GPT_MAX_OUTPUT_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "gpt_blind_prediction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"label": {"enum": list(RESULT_LABELS)}},
                    "required": ["label"],
                    "additionalProperties": False,
                },
            },
        },
        "user": candidate["candidate_id"],
    }


def _is_label_free_prompt(request: Mapping[str, object]) -> bool:
    """Report a prompt that holds only the passage, company, and aspect."""
    messages = request.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        return False
    try:
        user_content = json.loads(str(cast(Mapping[str, object], messages[1])["content"]))
    except (json.JSONDecodeError, KeyError, TypeError):
        return False
    return set(user_content) == {"passage", "company", "aspect"}


def _software_versions() -> dict[str, str]:
    try:
        package_version = metadata_version("nlp-wayfinder")
    except PackageNotFoundError:
        package_version = "unpackaged"
    return {
        "python": sys.version.split()[0],
        "nlp-wayfinder": package_version,
    }


def _gpt_error_response(reason: str, error: BaseException) -> OmniRouteResponse:
    return OmniRouteResponse(
        status_code=0,
        headers={},
        body={"error": {"type": reason, "message": str(error)}},
    )


def _decimal_rate(value: object) -> Decimal:
    rate = Decimal(str(value))
    if not rate.is_finite() or rate < 0:
        raise ValueError("The token price must be zero or more.")
    return rate


def project_gpt_blind_cost(
    forecast: Mapping[str, object],
    *,
    remaining_usd: Decimal = BUDGET_LIMITS["gpt"],
) -> dict[str, object]:
    """Project all first attempts and the declared reserve from non-blind text."""

    def stop(reason: str) -> dict[str, object]:
        return {
            "forecast": "stopped",
            "stop_reason": reason,
            "first_attempts": GPT_BLIND_FIRST_ATTEMPTS,
            "reserve_attempts": None,
            "projected_usd": None,
            "remaining_usd": _usd(remaining_usd),
        }

    if any(field not in forecast for field in GPT_FORECAST_FIELDS):
        return stop("gpt-forecast-incomplete")
    if forecast["measured_split"] not in ("training", "development"):
        return stop("gpt-forecast-blind-exposure")
    measured_ids = forecast["measured_candidate_ids"]
    if not isinstance(measured_ids, list) or not measured_ids:
        return stop("gpt-forecast-incomplete")
    try:
        prompt_tokens = int(cast(int, forecast["prompt_tokens_per_example"]))
        completion_tokens = int(cast(int, forecast["completion_tokens_per_example"]))
        reserve = int(cast(int, forecast["charged_retry_reserve_attempts"]))
        prompt_rate = _decimal_rate(forecast["prompt_usd_per_1k_tokens"])
        completion_rate = _decimal_rate(forecast["completion_usd_per_1k_tokens"])
    except (InvalidOperation, TypeError, ValueError):
        return stop("gpt-forecast-incomplete")
    if prompt_tokens <= 0 or completion_tokens <= 0 or reserve < 0:
        return stop("gpt-forecast-incomplete")

    attempts = GPT_BLIND_FIRST_ATTEMPTS + reserve
    per_attempt = (
        prompt_tokens * prompt_rate + completion_tokens * completion_rate
    ) / 1000
    projected = (per_attempt * attempts).quantize(
        Decimal("0.01"), rounding=ROUND_CEILING
    )
    result: dict[str, object] = {
        "forecast": "within-budget",
        "stop_reason": None,
        "first_attempts": GPT_BLIND_FIRST_ATTEMPTS,
        "reserve_attempts": reserve,
        "projected_usd": _usd(projected),
        "remaining_usd": _usd(remaining_usd),
        "measured_split": forecast["measured_split"],
        "measured_example_count": len(measured_ids),
    }
    if projected > remaining_usd:
        return {**stop("gpt-budget-exceeded"), "projected_usd": _usd(projected)}
    return result


def check_m3_compatibility(check: Mapping[str, object]) -> str | None:
    """Return one stop reason for the 8 GB M3 device check, or None."""
    if any(field not in check for field in SPECIALIST_M3_FIELDS):
        return "m3-check-incomplete"
    if not str(check["device_id"]).strip() or not str(check["evidence"]).strip():
        return "m3-check-incomplete"
    try:
        memory = float(cast(float, check["unified_memory_gb"]))
        tokens = int(cast(int, check["max_sequence_tokens"]))
    except (TypeError, ValueError):
        return "m3-check-incomplete"
    if (
        memory < SPECIALIST_MINIMUM_DEVICE_MEMORY_GB
        or tokens != SPECIALIST_COMPATIBILITY_TOKENS
        or check["compatibility_verified"] is not True
        or check["local_inference_verified"] is not True
    ):
        return "m3-check-failed"
    return None


def project_specialist_training_cost(
    pilot: Mapping[str, object],
    *,
    remaining_usd: Decimal = BUDGET_LIMITS["specialist"],
) -> dict[str, object]:
    """Project three-seed training and one repeat from measured pilot evidence."""
    runs = len(SPECIALIST_SEEDS) + SPECIALIST_OPERATIONAL_REPEATS

    def stop(reason: str, projected: str | None = None) -> dict[str, object]:
        return {
            "forecast": "stopped",
            "stop_reason": reason,
            "seeds": list(SPECIALIST_SEEDS),
            "operational_repeats": SPECIALIST_OPERATIONAL_REPEATS,
            "training_runs": runs,
            "projected_usd": projected,
            "pilot_usd": None,
            "remaining_usd": _usd(remaining_usd),
        }

    if any(field not in pilot for field in SPECIALIST_PILOT_FIELDS):
        return stop("specialist-pilot-incomplete")
    try:
        pilot_usd = _money(pilot["pilot_usd"])
        hourly_usd = _decimal_rate(pilot["hourly_usd"])
        storage_gb = _decimal_rate(pilot["storage_gb"])
        storage_rate = _decimal_rate(pilot["storage_usd_per_gb_month"])
        storage_months = _decimal_rate(pilot["storage_months"])
        tax_rate = _decimal_rate(pilot["tax_rate"])
        gpu_memory_gb = float(cast(float, pilot["gpu_memory_gb"]))
        peak_memory_gb = float(cast(float, pilot["peak_memory_gb"]))
        initial_loss = float(cast(float, pilot["initial_loss"]))
        final_loss = float(cast(float, pilot["final_loss"]))
        examples_per_second = float(cast(float, pilot["examples_per_second"]))
        examples = int(cast(int, pilot["training_examples_per_seed"]))
        tokens = int(cast(int, pilot["max_sequence_tokens"]))
    except (InvalidOperation, TypeError, ValueError):
        return stop("specialist-pilot-incomplete")
    if (
        examples_per_second <= 0
        or examples <= 0
        or gpu_memory_gb <= 0
        or peak_memory_gb <= 0
        or storage_gb <= 0
        or storage_months <= 0
        or not str(pilot["gpu_model"]).strip()
    ):
        return stop("specialist-pilot-incomplete")
    if str(pilot["gpu_architecture"]).strip().lower() not in SPECIALIST_GPU_ARCHITECTURES:
        return stop("specialist-pilot-architecture")
    if tokens != MAX_EXAMPLE_TOKENS:
        return stop("specialist-pilot-token-limit")
    if peak_memory_gb > gpu_memory_gb:
        return stop("specialist-pilot-memory")
    if not final_loss < initial_loss:
        return stop("specialist-pilot-loss")
    if pilot_usd > SPECIALIST_PILOT_LIMIT_USD:
        return stop("specialist-pilot-cost-exceeded")

    hours_per_run = Decimal(str(examples / examples_per_second)) / 3600
    compute_usd = hourly_usd * hours_per_run * runs
    storage_usd = storage_gb * storage_rate * storage_months
    projected = ((compute_usd + storage_usd) * (1 + tax_rate)).quantize(
        Decimal("0.01"), rounding=ROUND_CEILING
    )
    if projected > remaining_usd:
        return {
            **stop("specialist-budget-exceeded", _usd(projected)),
            "pilot_usd": _usd(pilot_usd),
        }
    return {
        "forecast": "within-budget",
        "stop_reason": None,
        "seeds": list(SPECIALIST_SEEDS),
        "operational_repeats": SPECIALIST_OPERATIONAL_REPEATS,
        "training_runs": runs,
        "projected_usd": _usd(projected),
        "pilot_usd": _usd(pilot_usd),
        "remaining_usd": _usd(remaining_usd),
        "hours_per_run": float(hours_per_run),
        "gpu_model": pilot["gpu_model"],
        "peak_memory_gb": peak_memory_gb,
        "final_loss": final_loss,
    }


def _macro_f1(
    predictions: Mapping[str, str], reference: Mapping[str, str]
) -> float:
    """Give each of the four classes equal weight. Use zero for an empty class."""
    total = 0.0
    for label in RESULT_LABELS:
        true_positive = sum(
            1
            for candidate_id, truth in reference.items()
            if truth == label and predictions.get(candidate_id) == label
        )
        false_positive = sum(
            1
            for candidate_id, predicted in predictions.items()
            if predicted == label and reference.get(candidate_id) != label
        )
        false_negative = sum(
            1
            for candidate_id, truth in reference.items()
            if truth == label and predictions.get(candidate_id) != label
        )
        denominator = 2 * true_positive + false_positive + false_negative
        total += (2 * true_positive / denominator) if denominator else 0.0
    return total / len(RESULT_LABELS)


def _contains_gpt_artifact(value: object) -> bool:
    """Find a GPT route or a GPT field in a training or selection input.

    The check reads field names and route identifiers only. Passage text that
    mentions GPT is source material, not GPT output.
    """
    if isinstance(value, Mapping):
        return any(
            "gpt" in str(key).lower() or _contains_gpt_artifact(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_gpt_artifact(item) for item in value)
    return isinstance(value, str) and GPT_ROUTE_ID in value


def _specialist_input(candidate: Mapping[str, object]) -> dict[str, object]:
    return {
        "candidate_id": candidate["candidate_id"],
        "passage": candidate["normalized_passage"],
        "target": candidate["company_id"],
        "aspect": candidate["aspect"],
    }


def _response_message(response: OmniRouteResponse) -> Mapping[str, object] | None:
    choices = response.body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return None
    choice = choices[0]
    if not isinstance(choice, Mapping):
        return None
    message = choice.get("message")
    return message if isinstance(message, Mapping) else None


def _response_label(response: OmniRouteResponse) -> str | None:
    message = _response_message(response)
    if message is None or message.get("refusal"):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"label"}
        or value.get("label") not in RESULT_LABELS
    ):
        return None
    return str(value["label"])


def _response_is_refusal(response: OmniRouteResponse) -> bool:
    message = _response_message(response)
    return message is not None and bool(message.get("refusal"))


def _is_free_limit(response: OmniRouteResponse) -> bool:
    """Report a spent free quota. Cloudflare does not always answer 429."""
    if response.status_code == 429:
        return True
    if response.status_code == 200:
        return False
    return any(
        word in _canonical_json(response.body).lower()
        for word in ("quota", "limit reached", "rate limit", "out of credits")
    )


def _int_header(headers: Mapping[str, str], name: str) -> int | None:
    try:
        return int(headers[name])
    except (KeyError, TypeError, ValueError):
        return None


def _calibration_fold(candidate_id: str) -> int:
    """Assign one fixed calibration fold to one candidate."""
    fold_input = (
        "nlp-wayfinder1financial-news-silver-calibration"
        f"{candidate_id}{SILVER_CALIBRATION_SEED}"
    )
    digest = hashlib.sha256(fold_input.encode("utf-8")).hexdigest()
    return int(digest, 16) % SILVER_CALIBRATION_FOLDS


def _temperature_scaled(
    posterior: Mapping[str, float], temperature: float
) -> dict[str, float]:
    """Scale one posterior by one temperature and normalize it again."""
    powered = {
        label: value ** (1.0 / temperature) for label, value in posterior.items()
    }
    total = sum(powered.values())
    return {label: value / total for label, value in powered.items()}


def _ranked_labels(calibrated: Mapping[str, float]) -> list[tuple[str, float]]:
    """Rank the labels by decreasing probability, then by name."""
    return sorted(calibrated.items(), key=lambda item: (-item[1], item[0]))


def _calibration_loss(
    items: Sequence[tuple[Mapping[str, float], str]], temperature: float
) -> float:
    return -sum(
        math.log(
            max(
                _temperature_scaled(posterior, temperature)[label],
                SILVER_PROBABILITY_FLOOR,
            )
        )
        for posterior, label in items
    )


def _fit_temperature(
    items: Sequence[tuple[Mapping[str, float], str]]
) -> float:
    """Find the temperature with the lowest loss by golden-section search."""
    if not items:
        return 1.0
    low, high = SILVER_CALIBRATION_RANGE
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    left, right = high - ratio * (high - low), low + ratio * (high - low)
    left_loss, right_loss = (
        _calibration_loss(items, left),
        _calibration_loss(items, right),
    )
    for _ in range(SILVER_CALIBRATION_STEPS):
        if left_loss <= right_loss:
            high = right
            right, right_loss = left, left_loss
            left = high - ratio * (high - low)
            left_loss = _calibration_loss(items, left)
        else:
            low = left
            left, left_loss = right, right_loss
            right = low + ratio * (high - low)
            right_loss = _calibration_loss(items, right)
    return (low + high) / 2.0


def _silver_rejection(
    vote_labels: Sequence[str], calibrated: Mapping[str, float]
) -> str | None:
    """Return the frozen reason to reject one candidate, or None to accept it."""
    ranked = _ranked_labels(calibrated)
    top_label, top_probability = ranked[0]
    if len(vote_labels) < SILVER_MIN_VALID_VOTES:
        return "insufficient-votes"
    if abs(top_probability - ranked[1][1]) <= SILVER_TIE_TOLERANCE:
        return "posterior-tie"
    counts = Counter(vote_labels).most_common()
    if counts[0][1] == 1 or (len(counts) > 1 and counts[0][1] == counts[1][1]):
        return "no-strict-majority"
    if counts[0][0] != top_label:
        return "top-class-unsupported"
    if top_probability < SILVER_MIN_PROBABILITY:
        return "low-confidence"
    return None


def _dawid_skene_fit(
    votes: Sequence[Mapping[str, str]],
    development_labels: Mapping[str, str],
    route_ids: Sequence[str],
) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, float], int]:
    """Fit gold-anchored Crowd-Kit Dawid-Skene and return full 4x4 matrices."""
    try:
        installed = metadata_version("crowd-kit")
    except PackageNotFoundError as error:
        raise RuntimeError("crowd-kit-missing") from error
    if installed != CROWD_KIT_VERSION:
        raise RuntimeError("crowd-kit-version-mismatch")
    import pandas as pd
    from crowdkit.aggregation import DawidSkene

    model = DawidSkene(n_iter=SILVER_DS_ITERATIONS, tol=SILVER_DS_TOLERANCE)
    model.fit(
        pd.DataFrame(list(votes), columns=["task", "worker", "label"]),
        true_labels=pd.Series(dict(development_labels), name="label"),
    )
    errors = model.errors_
    priors = model.priors_
    assert errors is not None and priors is not None

    # One full four-by-four matrix for each voter. Crowd-Kit returns only the
    # observed rows and columns, so absent cells take the probability floor.
    confusion: dict[str, dict[str, dict[str, float]]] = {}
    for worker in sorted(route_ids):
        matrix: dict[str, dict[str, float]] = {}
        for observed in RESULT_LABELS:
            row: dict[str, float] = {}
            for true_label in RESULT_LABELS:
                value = SILVER_PROBABILITY_FLOOR
                if (worker, observed) in errors.index and true_label in errors.columns:
                    value = max(
                        float(errors.loc[(worker, observed), true_label]),
                        SILVER_PROBABILITY_FLOOR,
                    )
                row[true_label] = value
            matrix[observed] = row
        confusion[worker] = matrix
    prior = {
        label: max(float(priors.get(label, 0.0)), SILVER_PROBABILITY_FLOOR)
        for label in RESULT_LABELS
    }
    total = sum(prior.values())
    return confusion, {k: v / total for k, v in prior.items()}, len(model.loss_history_)


def _dawid_skene_posterior(
    labels_by_worker: Mapping[str, str],
    confusion: Mapping[str, Mapping[str, Mapping[str, float]]],
    prior: Mapping[str, float],
) -> dict[str, float]:
    """Apply the fitted matrices to one example without any gold correction."""
    log_likelihood = {
        true_label: math.log(prior[true_label]) for true_label in RESULT_LABELS
    }
    for worker, observed in labels_by_worker.items():
        matrix = confusion.get(worker)
        if matrix is None:
            continue
        for true_label in RESULT_LABELS:
            log_likelihood[true_label] += math.log(matrix[observed][true_label])
    largest = max(log_likelihood.values())
    weights = {
        label: math.exp(value - largest) for label, value in log_likelihood.items()
    }
    total = sum(weights.values())
    return {label: value / total for label, value in weights.items()}


class StageRun:
    """Evaluate Stage 1 gates and own its append-only audit logs."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        clock: Callable[[], str] = _now,
    ) -> None:
        self.state_dir = Path(state_dir)
        self._clock = clock
        self.spend_ledger_path = self.state_dir / "spend-ledger.jsonl"
        self.decision_log_path = self.state_dir / "decision-log.jsonl"
        self.candidate_inspection_log_path = (
            self.state_dir / "candidate-inspection-log.jsonl"
        )
        self.vote_collection_log_path = self.state_dir / "vote-collection-log.jsonl"
        self.raw_vote_log_path = self.state_dir / "raw-votes.jsonl"
        self.silver_aggregation_log_path = (
            self.state_dir / "silver-aggregation-log.jsonl"
        )
        self.gpt_blind_log_path = self.state_dir / "gpt-blind-log.jsonl"
        self.specialist_log_path = self.state_dir / "specialist-log.jsonl"
        self._spend_ledger = _AppendOnlyJsonl(self.spend_ledger_path, clock)
        self._decision_log = _AppendOnlyJsonl(self.decision_log_path, clock)
        self._candidate_inspection_log = _AppendOnlyJsonl(
            self.candidate_inspection_log_path, clock
        )
        self._vote_collection_log = _AppendOnlyJsonl(
            self.vote_collection_log_path, clock
        )
        self._raw_vote_log = _AppendOnlyJsonl(self.raw_vote_log_path, clock)
        self._silver_aggregation_log = _AppendOnlyJsonl(
            self.silver_aggregation_log_path, clock
        )
        self._gpt_blind_log = _AppendOnlyJsonl(self.gpt_blind_log_path, clock)
        self._specialist_log = _AppendOnlyJsonl(self.specialist_log_path, clock)

    def cost_records(self) -> list[dict[str, Any]]:
        return self._spend_ledger.read()

    def decision_records(self) -> list[dict[str, Any]]:
        return self._decision_log.read()

    def candidate_inspection_records(self) -> list[dict[str, Any]]:
        return self._candidate_inspection_log.read()

    def vote_collection_records(self) -> list[dict[str, Any]]:
        return self._vote_collection_log.read()

    def raw_vote_records(self) -> list[dict[str, Any]]:
        return self._raw_vote_log.read()

    def silver_aggregation_records(self) -> list[dict[str, Any]]:
        return self._silver_aggregation_log.read()

    def gpt_blind_records(self) -> list[dict[str, Any]]:
        return self._gpt_blind_log.read()

    def specialist_records(self) -> list[dict[str, Any]]:
        return self._specialist_log.read()

    def _collection_stop(
        self, reason: str, route_ids: Sequence[str]
    ) -> dict[str, object]:
        return {
            "collection": "stopped",
            "stop_reason": reason,
            "raw_vote_count": len(self.raw_vote_records()),
            "frozen_route_ids": list(route_ids),
        }

    def collect_votes(
        self,
        stage_manifest: Mapping[str, object],
        candidate_manifest: Mapping[str, object],
        allocation: Mapping[str, object],
        transport: VoteTransport,
        *,
        timeout_seconds: float = 60,
    ) -> dict[str, object]:
        """Collect one independent vote per fixed route and non-blind example."""
        decision = self.evaluate(stage_manifest)
        if decision["decision"] != "build-eligible":
            return self._collection_stop(str(decision["stop_reason"]), [])
        if not _is_valid_sealed_candidate_manifest(candidate_manifest):
            return self._collection_stop("unsealed-annex", [])
        seal = candidate_manifest["seal"]
        assert isinstance(seal, Mapping)
        candidate_manifest_sha256 = str(seal["semantic_sha256"])
        if (
            allocation.get("allocation") != "complete"
            or allocation.get("candidate_manifest_sha256")
            != candidate_manifest_sha256
        ):
            return self._collection_stop("allocation-not-complete", [])

        evidence = decision["evidence"]
        assert isinstance(evidence, Mapping)
        route_evidence = evidence["routes"]
        assert isinstance(route_evidence, Mapping)
        route_ids_value = route_evidence["eligible_route_ids"]
        assert isinstance(route_ids_value, list)
        route_ids = [str(route_id) for route_id in route_ids_value]
        freeze = {
            "event": "vote-collection-frozen",
            "run_id": stage_manifest["run_id"],
            "stage_manifest_sha256": semantic_manifest_sha256(stage_manifest),
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "route_ids": sorted(route_ids),
            "request_template_sha256": hashlib.sha256(
                _canonical_json(
                    _vote_request(
                        "",
                        {
                            "candidate_id": "",
                            "normalized_passage": "",
                            "company_id": "",
                            "aspect": "",
                        },
                    )
                ).encode("utf-8")
            ).hexdigest(),
        }
        freeze_records = [
            record
            for record in self.vote_collection_records()
            if record.get("event") == "vote-collection-frozen"
        ]
        if freeze_records:
            prior = freeze_records[0]
            if any(prior.get(field) != freeze[field] for field in freeze):
                return self._collection_stop(
                    "frozen-vote-collection-changed",
                    cast(Sequence[str], prior.get("route_ids", [])),
                )
        else:
            self._vote_collection_log.append(freeze)

        candidates_value = candidate_manifest["candidates"]
        assert isinstance(candidates_value, list)
        candidate_by_id = {
            str(candidate["candidate_id"]): candidate
            for candidate in candidates_value
            if isinstance(candidate, Mapping)
        }
        scheduled: list[Mapping[str, object]] = []
        for split in ("training", "development"):
            selected = allocation.get(split)
            if not isinstance(selected, list):
                return self._collection_stop("allocation-not-complete", route_ids)
            for item in selected:
                candidate_id = (
                    item.get("candidate_id") if isinstance(item, Mapping) else None
                )
                candidate = candidate_by_id.get(str(candidate_id))
                if candidate is None or candidate.get("split") != split:
                    return self._collection_stop("vote-candidate-invalid", route_ids)
                scheduled.append(candidate)

        # A spent free quota resets. That attempt must not block the later vote.
        collected = {
            (record.get("candidate_id"), record.get("requested_route_id"))
            for record in self.raw_vote_records()
            if record.get("abstention_reason") != "free-limit"
        }
        for candidate in scheduled:
            for route_id in route_ids:
                key = (candidate["candidate_id"], route_id)
                if key in collected:
                    continue
                request = _vote_request(route_id, candidate)
                started_at = self._clock()
                forced_abstention_reason: str | None = None
                try:
                    response = transport.complete(request, timeout_seconds)
                except (TimeoutError, OSError) as error:
                    forced_abstention_reason = (
                        "timeout" if isinstance(error, TimeoutError) else "transport-error"
                    )
                    response = OmniRouteResponse(
                        status_code=0,
                        headers={},
                        body={
                            "error": {
                                "type": forced_abstention_reason,
                                "message": str(error),
                            }
                        },
                    )
                completed_at = self._clock()
                headers = {key.lower(): value for key, value in response.headers.items()}
                returned_provider = headers.get("x-omniroute-provider")
                returned_model = headers.get("x-omniroute-model")
                returned_route_id = (
                    f"{returned_provider}/{returned_model}"
                    if returned_provider and returned_model
                    else None
                )
                label = _response_label(response)
                fallback_attempts = _int_header(
                    headers, "x-omniroute-fallback-attempts"
                )
                outcome = "valid"
                abstention_reason: str | None = None
                if forced_abstention_reason is not None:
                    outcome, abstention_reason, label = (
                        "abstention",
                        forced_abstention_reason,
                        None,
                    )
                elif _is_free_limit(response):
                    outcome, abstention_reason, label = "abstention", "free-limit", None
                elif response.status_code != 200:
                    outcome, abstention_reason, label = "abstention", "transport-error", None
                elif (
                    returned_route_id != route_id
                    or fallback_attempts != 0
                    or "strategy=single"
                    not in str(headers.get("x-omniroute-decision", ""))
                ):
                    outcome, abstention_reason, label = "abstention", "route-substitution", None
                elif str(headers.get("x-omniroute-cache-hit", "")).lower() == "true":
                    outcome, abstention_reason, label = "abstention", "cache-hit", None
                elif _response_is_refusal(response):
                    outcome, abstention_reason, label = "abstention", "refusal", None
                elif label is None:
                    outcome, abstention_reason = "abstention", "malformed-answer"
                response_cost = headers.get("x-omniroute-response-cost")
                try:
                    paid_overflow = (
                        response_cost is not None and Decimal(response_cost) > 0
                    )
                except InvalidOperation:
                    paid_overflow = True
                if paid_overflow:
                    outcome, abstention_reason, label = (
                        "abstention",
                        "paid-overflow",
                        None,
                    )
                usage = response.body.get("usage")
                if not isinstance(usage, Mapping):
                    usage = {}
                prompt = request["messages"]
                record = {
                    "event": "raw-vote",
                    "candidate_id": candidate["candidate_id"],
                    "split": candidate["split"],
                    "requested_route_id": route_id,
                    "status_code": response.status_code,
                    "returned_route_id": returned_route_id,
                    "returned_provider": returned_provider,
                    "returned_model": returned_model,
                    "prompt": prompt,
                    "prompt_sha256": hashlib.sha256(
                        _canonical_json(prompt).encode("utf-8")
                    ).hexdigest(),
                    "request_sha256": hashlib.sha256(
                        _canonical_json(request).encode("utf-8")
                    ).hexdigest(),
                    "response_sha256": hashlib.sha256(
                        _canonical_json(response.body).encode("utf-8")
                    ).hexdigest(),
                    "outcome": outcome,
                    "abstention_reason": abstention_reason,
                    "label": label,
                    "token_use": {
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                        "omniroute_tokens_in": headers.get(
                            "x-omniroute-tokens-in"
                        ),
                        "omniroute_tokens_out": headers.get(
                            "x-omniroute-tokens-out"
                        ),
                    },
                    "time": {
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "latency_ms": headers.get("x-omniroute-latency-ms"),
                    },
                    "cost": {
                        "response_cost_usd": headers.get(
                            "x-omniroute-response-cost"
                        ),
                        "cache_hit": headers.get("x-omniroute-cache-hit"),
                    },
                    "transport": {
                        "request_id": headers.get("x-omniroute-request-id"),
                        "omniroute_version": headers.get("x-omniroute-version"),
                        "decision": headers.get("x-omniroute-decision"),
                        "fallback_attempts": fallback_attempts,
                    },
                }
                self._raw_vote_log.append(record)
                collected.add(key)
                if abstention_reason == "free-limit":
                    return self._collection_stop("free-limit-failure", route_ids)
                if abstention_reason == "paid-overflow":
                    return self._collection_stop("paid-overflow-detected", route_ids)

        return {
            "collection": "complete",
            "stop_reason": None,
            "raw_vote_count": len(self.raw_vote_records()),
            "frozen_route_ids": route_ids,
        }

    def _aggregation_stop(self, reason: str) -> dict[str, object]:
        return {
            "aggregation": "stopped",
            "stop_reason": reason,
            "accepted_silver_count": 0,
            "rejected_counts": {},
        }

    def _valid_votes(self) -> dict[str, dict[str, str]]:
        """Keep the last outcome for each example and route. Drop abstentions."""
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for record in self.raw_vote_records():
            if record.get("event") != "raw-vote":
                continue
            latest[
                (str(record.get("candidate_id")), str(record.get("requested_route_id")))
            ] = record
        votes: dict[str, dict[str, str]] = {}
        for (candidate_id, route_id), record in latest.items():
            if (
                record.get("outcome") != "valid"
                or record.get("label") not in RESULT_LABELS
            ):
                continue
            votes.setdefault(candidate_id, {})[route_id] = str(record["label"])
        return votes

    def aggregate_silver_labels(
        self,
        stage_manifest: Mapping[str, object],
        candidate_manifest: Mapping[str, object],
        allocation: Mapping[str, object],
    ) -> dict[str, object]:
        """Aggregate fixed-route votes into calibrated accepted silver labels."""
        decision = self.evaluate(stage_manifest)
        if decision["decision"] != "build-eligible":
            return self._aggregation_stop(str(decision["stop_reason"]))
        if not _is_valid_sealed_candidate_manifest(candidate_manifest):
            return self._aggregation_stop("unsealed-annex")
        seal = candidate_manifest["seal"]
        assert isinstance(seal, Mapping)
        candidate_manifest_sha256 = str(seal["semantic_sha256"])
        if (
            allocation.get("allocation") != "complete"
            or allocation.get("candidate_manifest_sha256") != candidate_manifest_sha256
        ):
            return self._aggregation_stop("allocation-not-complete")

        development = allocation.get("development")
        training = allocation.get("training")
        if not isinstance(development, list) or not isinstance(training, list):
            return self._aggregation_stop("allocation-not-complete")
        development_labels: dict[str, str] = {}
        for item in development:
            if not isinstance(item, Mapping) or item.get("label") not in RESULT_LABELS:
                return self._aggregation_stop("development-label-invalid")
            development_labels[str(item["candidate_id"])] = str(item["label"])
        class_counts = Counter(development_labels.values())
        if any(
            class_counts[label] < SILVER_MIN_DEVELOPMENT_CLASS
            for label in RESULT_LABELS
        ):
            return self._aggregation_stop("development-class-underfilled")

        evidence = decision["evidence"]
        assert isinstance(evidence, Mapping)
        route_evidence = evidence["routes"]
        assert isinstance(route_evidence, Mapping)
        route_ids = [
            str(route_id)
            for route_id in cast(list[object], route_evidence["eligible_route_ids"])
        ]

        votes = self._valid_votes()
        training_ids = [
            str(item["candidate_id"])
            for item in training
            if isinstance(item, Mapping)
        ]
        # An abstention is a missing vote, so the fit reads only the valid votes.
        fit_rows = [
            {"task": candidate_id, "worker": route_id, "label": label}
            for candidate_id in [*training_ids, *development_labels]
            for route_id, label in sorted(votes.get(candidate_id, {}).items())
        ]
        if not fit_rows:
            return self._aggregation_stop("no-valid-votes")
        try:
            confusion, prior, iterations = _dawid_skene_fit(
                fit_rows, development_labels, route_ids
            )
        except RuntimeError as error:
            return self._aggregation_stop(str(error))

        posteriors = {
            candidate_id: _dawid_skene_posterior(
                votes.get(candidate_id, {}), confusion, prior
            )
            for candidate_id in [*training_ids, *development_labels]
        }

        folds = {
            candidate_id: _calibration_fold(candidate_id)
            for candidate_id in development_labels
        }
        fold_temperatures: list[float] = []
        out_of_fold: dict[str, dict[str, float]] = {}
        for fold in range(SILVER_CALIBRATION_FOLDS):
            temperature = _fit_temperature(
                [
                    (posteriors[candidate_id], label)
                    for candidate_id, label in development_labels.items()
                    if folds[candidate_id] != fold
                ]
            )
            fold_temperatures.append(temperature)
            for candidate_id in development_labels:
                if folds[candidate_id] == fold:
                    out_of_fold[candidate_id] = _temperature_scaled(
                        posteriors[candidate_id], temperature
                    )
        temperature = sum(fold_temperatures) / SILVER_CALIBRATION_FOLDS

        accepted: list[dict[str, object]] = []
        rejected_counts: Counter[str] = Counter()
        posterior_records: list[dict[str, object]] = []
        for candidate_id in training_ids:
            candidate_votes = votes.get(candidate_id, {})
            calibrated = _temperature_scaled(posteriors[candidate_id], temperature)
            top_label = _ranked_labels(calibrated)[0][0]
            reason = _silver_rejection(sorted(candidate_votes.values()), calibrated)
            if reason is None:
                accepted.append(
                    {
                        "candidate_id": candidate_id,
                        "label": top_label,
                        "probability": calibrated[top_label],
                    }
                )
            else:
                rejected_counts[reason] += 1
            posterior_records.append(
                {
                    "candidate_id": candidate_id,
                    "valid_vote_count": len(candidate_votes),
                    "posterior": posteriors[candidate_id],
                    "calibrated": calibrated,
                    "accepted": reason is None,
                    "rejection_reason": reason,
                }
            )

        fit_artifact: dict[str, object] = {
            "event": "silver-fit-sealed",
            "run_id": stage_manifest["run_id"],
            "stage_manifest_sha256": semantic_manifest_sha256(stage_manifest),
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "crowd_kit_version": CROWD_KIT_VERSION,
            "n_iter": SILVER_DS_ITERATIONS,
            "tol": SILVER_DS_TOLERANCE,
            "iterations_used": iterations,
            "route_dependency_parameter_count": 0,
            "confusion_matrices": confusion,
            "priors": prior,
            "calibration_seed": SILVER_CALIBRATION_SEED,
            "calibration_folds": SILVER_CALIBRATION_FOLDS,
            "fold_temperatures": fold_temperatures,
            "temperature": temperature,
            "development_class_counts": dict(class_counts),
        }
        posterior_artifact: dict[str, object] = {
            "event": "silver-posteriors-sealed",
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "development_out_of_fold": out_of_fold,
            "training_posteriors": posterior_records,
        }
        artifacts = (fit_artifact, posterior_artifact)
        sealed = self.silver_aggregation_records()
        unsealed: list[dict[str, object]] = []
        for artifact in artifacts:
            prior_records = [
                record for record in sealed if record.get("event") == artifact["event"]
            ]
            if not prior_records:
                unsealed.append(artifact)
            elif any(
                prior_records[0].get(field) != artifact[field] for field in artifact
            ):
                return self._aggregation_stop("frozen-aggregation-changed")
        if unsealed and len(unsealed) != len(artifacts):
            return self._aggregation_stop("frozen-aggregation-changed")
        for artifact in unsealed:
            self._silver_aggregation_log.append(artifact)

        result: dict[str, object] = {
            "aggregation": "complete",
            "stop_reason": None,
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "accepted_silver_count": len(accepted),
            "rejected_counts": dict(sorted(rejected_counts.items())),
            "accepted_silver": accepted,
            "temperature": temperature,
            "fit_sha256": hashlib.sha256(
                _canonical_json(fit_artifact).encode("utf-8")
            ).hexdigest(),
            "posterior_sha256": hashlib.sha256(
                _canonical_json(posterior_artifact).encode("utf-8")
            ).hexdigest(),
        }
        result["aggregation_sha256"] = hashlib.sha256(
            _canonical_json(result).encode("utf-8")
        ).hexdigest()
        return result

    def _gpt_stop(self, reason: str) -> dict[str, object]:
        return {
            "gpt_predictions": "invalid",
            "stop_reason": reason,
            "route_id": GPT_ROUTE_ID,
            "prediction_count": 0,
            "predictions": [],
        }

    def predict_blind_gpt(
        self,
        stage_manifest: Mapping[str, object],
        candidate_manifest: Mapping[str, object],
        allocation: Mapping[str, object],
        transport: VoteTransport,
        *,
        forecast: Mapping[str, object],
        timeout_seconds: float = 120,
        sleep: Callable[[float], None] = time.sleep,
    ) -> dict[str, object]:
        """Produce one sealed GPT-5.6-sol prediction file for the blind set."""
        decision = self.evaluate(stage_manifest)
        if decision["decision"] != "build-eligible":
            return self._gpt_stop(str(decision["stop_reason"]))
        if not _is_valid_sealed_candidate_manifest(candidate_manifest):
            return self._gpt_stop("unsealed-annex")
        seal = candidate_manifest["seal"]
        assert isinstance(seal, Mapping)
        candidate_manifest_sha256 = str(seal["semantic_sha256"])
        if (
            allocation.get("allocation") != "complete"
            or allocation.get("candidate_manifest_sha256") != candidate_manifest_sha256
        ):
            return self._gpt_stop("allocation-not-complete")

        records = self.gpt_blind_records()
        # A sealed file serves each later regression test. Do not call GPT again.
        sealed = [
            record
            for record in records
            if record.get("event") == "gpt-blind-predictions-sealed"
        ]
        if sealed:
            prior = cast(dict[str, object], sealed[0]["prediction_file"])
            if prior.get("candidate_manifest_sha256") != candidate_manifest_sha256:
                return self._gpt_stop("frozen-gpt-run-changed")
            return prior

        projection = project_gpt_blind_cost(
            forecast,
            remaining_usd=BUDGET_LIMITS["gpt"] - self.budget_exposure()["gpt"],
        )
        if projection["forecast"] != "within-budget":
            return self._gpt_stop(str(projection["stop_reason"]))

        blind = allocation.get("blind")
        if not isinstance(blind, list) or not blind:
            return self._gpt_stop("allocation-not-complete")
        candidates_value = candidate_manifest["candidates"]
        assert isinstance(candidates_value, list)
        candidate_by_id = {
            str(candidate["candidate_id"]): candidate
            for candidate in candidates_value
            if isinstance(candidate, Mapping)
        }
        scheduled: list[Mapping[str, object]] = []
        for item in blind:
            candidate_id = item.get("candidate_id") if isinstance(item, Mapping) else None
            candidate = candidate_by_id.get(str(candidate_id))
            if candidate is None or candidate.get("split") != "blind":
                return self._gpt_stop("gpt-candidate-invalid")
            if any(field in candidate for field in BLIND_LABEL_FIELDS):
                return self._gpt_stop("blind-label-exposed")
            scheduled.append(candidate)

        freeze = {
            "event": "gpt-blind-run-frozen",
            "run_id": stage_manifest["run_id"],
            "stage_manifest_sha256": semantic_manifest_sha256(stage_manifest),
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "route_id": GPT_ROUTE_ID,
            "reasoning_effort": GPT_REASONING_EFFORT,
            "prompt_sha256": hashlib.sha256(
                GPT_BLIND_SYSTEM_PROMPT.encode("utf-8")
            ).hexdigest(),
            "request_template_sha256": hashlib.sha256(
                _canonical_json(
                    _gpt_request(
                        {
                            "candidate_id": "",
                            "normalized_passage": "",
                            "company_id": "",
                            "aspect": "",
                        }
                    )
                ).encode("utf-8")
            ).hexdigest(),
            "max_attempts": GPT_MAX_ATTEMPTS,
            "retry_delays_seconds": list(GPT_RETRY_DELAYS_SECONDS),
            "timeout_seconds": timeout_seconds,
            "projected_usd": projection["projected_usd"],
            "reserve_attempts": projection["reserve_attempts"],
        }
        freeze_records = [
            record for record in records if record.get("event") == "gpt-blind-run-frozen"
        ]
        if freeze_records:
            if any(freeze_records[0].get(field) != freeze[field] for field in freeze):
                return self._gpt_stop("frozen-gpt-run-changed")
        else:
            self._gpt_blind_log.append(freeze)

        predictions: list[dict[str, object]] = []
        for candidate in scheduled:
            request = _gpt_request(candidate)
            if not _is_label_free_prompt(request):
                return self._gpt_stop("blind-label-exposed")
            label: str | None = None
            for attempt in range(1, GPT_MAX_ATTEMPTS + 1):
                if attempt > 1:
                    sleep(GPT_RETRY_DELAYS_SECONDS[attempt - 2])
                started_at = self._clock()
                retry_reason: str | None = None
                try:
                    response = transport.complete(request, timeout_seconds)
                except TimeoutError as error:
                    retry_reason = "timeout"
                    response = _gpt_error_response(retry_reason, error)
                except OSError as error:
                    retry_reason = "connection-error"
                    response = _gpt_error_response(retry_reason, error)
                completed_at = self._clock()
                headers = {
                    key.lower(): value for key, value in response.headers.items()
                }
                returned_provider = headers.get("x-omniroute-provider")
                returned_model = headers.get("x-omniroute-model")
                returned_route_id = (
                    f"{returned_provider}/{returned_model}"
                    if returned_provider and returned_model
                    else None
                )
                fallback_attempts = _int_header(
                    headers, "x-omniroute-fallback-attempts"
                )
                if retry_reason is None and response.status_code == 429:
                    retry_reason = "http-429"
                elif retry_reason is None and 500 <= response.status_code <= 599:
                    retry_reason = "http-5xx"
                outcome = "valid"
                failure_reason: str | None = None
                if retry_reason is not None:
                    outcome, failure_reason = "transport-failure", retry_reason
                elif response.status_code != 200:
                    outcome, failure_reason = "invalid", "transport-error"
                elif (
                    returned_route_id != GPT_ROUTE_ID
                    or fallback_attempts != 0
                    or "strategy=single"
                    not in str(headers.get("x-omniroute-decision", ""))
                    or str(headers.get("x-omniroute-cache-hit", "")).lower() == "true"
                ):
                    outcome, failure_reason = "invalid", "route-mismatch"
                elif _response_is_refusal(response):
                    outcome, failure_reason = "invalid", "refusal"
                else:
                    label = _response_label(response)
                    if label is None:
                        outcome, failure_reason = "invalid", "malformed-answer"
                usage = response.body.get("usage")
                if not isinstance(usage, Mapping):
                    usage = {}
                self._gpt_blind_log.append(
                    {
                        "event": "gpt-blind-attempt",
                        "candidate_id": candidate["candidate_id"],
                        "attempt": attempt,
                        "status_code": response.status_code,
                        "returned_route_id": returned_route_id,
                        "outcome": outcome,
                        "failure_reason": failure_reason,
                        "label": label if outcome == "valid" else None,
                        "request_sha256": hashlib.sha256(
                            _canonical_json(request).encode("utf-8")
                        ).hexdigest(),
                        "response_sha256": hashlib.sha256(
                            _canonical_json(response.body).encode("utf-8")
                        ).hexdigest(),
                        "token_use": {
                            "prompt_tokens": usage.get("prompt_tokens"),
                            "completion_tokens": usage.get("completion_tokens"),
                            "total_tokens": usage.get("total_tokens"),
                        },
                        "cost": {
                            "response_cost_usd": headers.get(
                                "x-omniroute-response-cost"
                            ),
                        },
                        "time": {
                            "started_at": started_at,
                            "completed_at": completed_at,
                        },
                        "transport": {
                            "request_id": headers.get("x-omniroute-request-id"),
                            "omniroute_version": headers.get("x-omniroute-version"),
                            "decision": headers.get("x-omniroute-decision"),
                            "fallback_attempts": fallback_attempts,
                        },
                    }
                )
                if outcome == "valid":
                    predictions.append(
                        {
                            "candidate_id": candidate["candidate_id"],
                            "label": label,
                            "attempt_count": attempt,
                            "returned_route_id": returned_route_id,
                        }
                    )
                    break
                # A refusal or malformed answer has no repair and no retry.
                if outcome == "invalid":
                    return self._gpt_stop(str(failure_reason))
            else:
                return self._gpt_stop("gpt-transport-failed")

        if len(predictions) != len(scheduled):
            return self._gpt_stop("missing-prediction")

        prediction_file: dict[str, object] = {
            "gpt_predictions": "sealed",
            "stop_reason": None,
            "route_id": GPT_ROUTE_ID,
            "reasoning_effort": GPT_REASONING_EFFORT,
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "prompt_sha256": freeze["prompt_sha256"],
            "request_template_sha256": freeze["request_template_sha256"],
            "projection": projection,
            "software_versions": _software_versions(),
            "prediction_count": len(predictions),
            "predictions": predictions,
        }
        prediction_file["prediction_file_sha256"] = hashlib.sha256(
            _canonical_json(prediction_file).encode("utf-8")
        ).hexdigest()
        self._gpt_blind_log.append(
            {
                "event": "gpt-blind-predictions-sealed",
                "run_id": stage_manifest["run_id"],
                "prediction_file": prediction_file,
            }
        )
        return prediction_file

    def _specialist_stop(self, reason: str) -> dict[str, object]:
        return {
            "specialist_predictions": "invalid",
            "stop_reason": reason,
            "model_id": MODERNBERT_MODEL_ID,
            "revision": MODERNBERT_REVISION,
            "prediction_count": 0,
            "predictions": [],
        }

    def train_specialist(
        self,
        stage_manifest: Mapping[str, object],
        candidate_manifest: Mapping[str, object],
        allocation: Mapping[str, object],
        aggregation: Mapping[str, object],
        backend: TrainingBackend,
        *,
        device_checks: Mapping[str, object],
    ) -> dict[str, object]:
        """Train the pinned specialist and seal its local blind prediction file."""
        decision = self.evaluate(stage_manifest)
        if decision["decision"] != "build-eligible":
            return self._specialist_stop(str(decision["stop_reason"]))
        if not _is_valid_sealed_candidate_manifest(candidate_manifest):
            return self._specialist_stop("unsealed-annex")
        seal = candidate_manifest["seal"]
        assert isinstance(seal, Mapping)
        candidate_manifest_sha256 = str(seal["semantic_sha256"])
        if (
            allocation.get("allocation") != "complete"
            or allocation.get("candidate_manifest_sha256") != candidate_manifest_sha256
        ):
            return self._specialist_stop("allocation-not-complete")

        records = self.specialist_records()
        # A sealed file serves each later regression test. Do not train again.
        sealed = [
            record
            for record in records
            if record.get("event") == "specialist-predictions-sealed"
        ]
        if sealed:
            prior = cast(dict[str, object], sealed[0]["prediction_file"])
            if prior.get("candidate_manifest_sha256") != candidate_manifest_sha256:
                return self._specialist_stop("frozen-specialist-run-changed")
            return prior

        if (
            aggregation.get("aggregation") != "complete"
            or aggregation.get("candidate_manifest_sha256") != candidate_manifest_sha256
        ):
            return self._specialist_stop("silver-labels-not-accepted")
        accepted_silver = aggregation.get("accepted_silver")
        if not isinstance(accepted_silver, list) or not accepted_silver:
            return self._specialist_stop("silver-labels-not-accepted")
        # GPT supplies no training, development, calibration, or selection input.
        if any(
            _contains_gpt_artifact(value)
            # The stage manifest is not in this list. Its budget has one
            # permitted `gpt` category for the separate blind comparison.
            for value in (aggregation, allocation, device_checks, candidate_manifest)
        ):
            return self._specialist_stop("gpt-artifact-present")

        m3_check = device_checks.get("m3")
        if not isinstance(m3_check, Mapping):
            return self._specialist_stop("m3-check-incomplete")
        m3_stop = check_m3_compatibility(m3_check)
        if m3_stop is not None:
            return self._specialist_stop(m3_stop)

        pilot = device_checks.get("gpu_pilot")
        if not isinstance(pilot, Mapping):
            return self._specialist_stop("specialist-pilot-incomplete")
        # The pilot spends from the same allocation. Its measured cost lowers the
        # balance even before the operator records it in the ledger.
        try:
            pilot_usd = _money(pilot.get("pilot_usd"))
        except ValueError:
            pilot_usd = Decimal("0.00")
        projection = project_specialist_training_cost(
            pilot,
            remaining_usd=(
                BUDGET_LIMITS["specialist"]
                - max(self.budget_exposure()["specialist"], pilot_usd)
            ),
        )
        if projection["forecast"] != "within-budget":
            return self._specialist_stop(str(projection["stop_reason"]))

        candidates_value = candidate_manifest["candidates"]
        assert isinstance(candidates_value, list)
        candidate_by_id = {
            str(candidate["candidate_id"]): candidate
            for candidate in candidates_value
            if isinstance(candidate, Mapping)
        }

        def rows(split: str) -> list[Mapping[str, object]] | str:
            """Give the split candidates, or one stop reason."""
            items = allocation.get(split)
            if not isinstance(items, list) or not items:
                return "specialist-candidate-invalid"
            selected: list[Mapping[str, object]] = []
            for item in items:
                candidate_id = (
                    item.get("candidate_id") if isinstance(item, Mapping) else None
                )
                candidate = candidate_by_id.get(str(candidate_id))
                if candidate is None or candidate.get("split") != split:
                    return "specialist-candidate-invalid"
                if any(field in candidate for field in BLIND_LABEL_FIELDS):
                    return "blind-label-exposed"
                selected.append(candidate)
            return selected

        splits = [rows(split) for split in ("training", "development", "blind")]
        for split_rows in splits:
            if isinstance(split_rows, str):
                return self._specialist_stop(split_rows)
        training_candidates, development_candidates, blind_candidates = cast(
            list[list[Mapping[str, object]]], splits
        )

        silver_labels: dict[str, str] = {}
        for item in accepted_silver:
            if not isinstance(item, Mapping) or item.get("label") not in RESULT_LABELS:
                return self._specialist_stop("silver-labels-not-accepted")
            silver_labels[str(item["candidate_id"])] = str(item["label"])
        training_rows = [
            {
                **_specialist_input(candidate),
                "label": silver_labels[str(candidate["candidate_id"])],
            }
            for candidate in training_candidates
            if str(candidate["candidate_id"]) in silver_labels
        ]
        if not training_rows:
            return self._specialist_stop("silver-labels-not-accepted")
        # The development labels stay with the selection code. Only inputs go out.
        development_rows = [
            _specialist_input(candidate) for candidate in development_candidates
        ]
        blind_rows = [_specialist_input(candidate) for candidate in blind_candidates]

        development_labels: dict[str, str] = {}
        for item in cast(list[Mapping[str, object]], allocation["development"]):
            if item.get("label") not in RESULT_LABELS:
                return self._specialist_stop("development-label-invalid")
            development_labels[str(item["candidate_id"])] = str(item["label"])

        base_config: dict[str, object] = {
            "model_id": MODERNBERT_MODEL_ID,
            "revision": MODERNBERT_REVISION,
            "new_head": True,
            "head_labels": list(RESULT_LABELS),
            "input_fields": ["passage", "target", "aspect"],
            "max_sequence_tokens": MAX_EXAMPLE_TOKENS,
        }
        freeze = {
            "event": "specialist-run-frozen",
            "run_id": stage_manifest["run_id"],
            "stage_manifest_sha256": semantic_manifest_sha256(stage_manifest),
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "training_config_sha256": hashlib.sha256(
                _canonical_json(base_config).encode("utf-8")
            ).hexdigest(),
            "seeds": list(SPECIALIST_SEEDS),
            "training_example_count": len(training_rows),
            "development_example_count": len(development_rows),
            "blind_example_count": len(blind_rows),
            "m3_device_id": m3_check["device_id"],
            "projected_usd": projection["projected_usd"],
            "pilot_usd": projection["pilot_usd"],
        }
        freeze_records = [
            record
            for record in records
            if record.get("event") == "specialist-run-frozen"
        ]
        if freeze_records:
            if any(freeze_records[0].get(field) != freeze[field] for field in freeze):
                return self._specialist_stop("frozen-specialist-run-changed")
        else:
            self._specialist_log.append(freeze)

        checkpoints: list[dict[str, object]] = []
        for seed in SPECIALIST_SEEDS:
            config = {
                **base_config,
                "seed": seed,
                "training": training_rows,
                "development": development_rows,
            }
            result = backend.train(config)
            predictions = result.get("development_predictions")
            if (
                any(field not in result for field in SPECIALIST_TRAIN_RESULT_FIELDS)
                or result["model_id"] != MODERNBERT_MODEL_ID
                or result["revision"] != MODERNBERT_REVISION
                or result["max_sequence_tokens"] != MAX_EXAMPLE_TOKENS
                or list(cast(list[str], result["head_labels"])) != list(RESULT_LABELS)
                or not isinstance(predictions, Mapping)
                or set(predictions) != set(development_labels)
                or any(label not in RESULT_LABELS for label in predictions.values())
            ):
                return self._specialist_stop("specialist-training-invalid")
            macro_f1 = _macro_f1(
                {str(key): str(value) for key, value in predictions.items()},
                development_labels,
            )
            checkpoints.append(
                {
                    "seed": seed,
                    "checkpoint_id": str(result["checkpoint_id"]),
                    "development_macro_f1": macro_f1,
                }
            )
            self._specialist_log.append(
                {
                    "event": "specialist-training-run",
                    "seed": seed,
                    "checkpoint_id": str(result["checkpoint_id"]),
                    "development_macro_f1": macro_f1,
                    "training_example_count": len(training_rows),
                }
            )

        # The human development labels select the checkpoint. A tie takes the
        # lowest seed.
        selected = min(
            checkpoints,
            key=lambda item: (
                -cast(float, item["development_macro_f1"]),
                cast(int, item["seed"]),
            ),
        )
        inference = backend.predict(str(selected["checkpoint_id"]), blind_rows)
        device_id = inference.get("device_id") if isinstance(inference, Mapping) else None
        if device_id != m3_check["device_id"]:
            return self._specialist_stop("local-inference-device-mismatch")
        labels = inference.get("predictions")
        if not isinstance(labels, Mapping):
            return self._specialist_stop("specialist-inference-invalid")
        predictions_out: list[dict[str, object]] = []
        for row in blind_rows:
            label = labels.get(str(row["candidate_id"]))
            if label not in RESULT_LABELS:
                return self._specialist_stop("missing-prediction")
            predictions_out.append(
                {"candidate_id": row["candidate_id"], "label": label}
            )

        prediction_file: dict[str, object] = {
            "specialist_predictions": "sealed",
            "stop_reason": None,
            "model_id": MODERNBERT_MODEL_ID,
            "revision": MODERNBERT_REVISION,
            "candidate_manifest_sha256": candidate_manifest_sha256,
            "training_config_sha256": freeze["training_config_sha256"],
            "checkpoint_id": selected["checkpoint_id"],
            "selected_seed": selected["seed"],
            "checkpoints": checkpoints,
            "inference_device_id": device_id,
            "projection": projection,
            "software_versions": _software_versions(),
            "prediction_count": len(predictions_out),
            "predictions": predictions_out,
        }
        prediction_file["prediction_file_sha256"] = hashlib.sha256(
            _canonical_json(prediction_file).encode("utf-8")
        ).hexdigest()
        self._specialist_log.append(
            {
                "event": "specialist-predictions-sealed",
                "run_id": stage_manifest["run_id"],
                "prediction_file": prediction_file,
            }
        )
        return prediction_file

    def inspect_candidate(
        self,
        manifest: Mapping[str, object],
        candidate_id: str,
    ) -> dict[str, object]:
        """Inspect only the next candidate in one sealed manifest."""
        if not _is_valid_sealed_candidate_manifest(manifest):
            return {
                "inspection": "rejected",
                "stop_reason": "unsealed-annex",
                "candidate_id": candidate_id,
            }
        seal = manifest["seal"]
        candidates = manifest["candidates"]
        assert isinstance(seal, Mapping)
        assert isinstance(candidates, list)
        manifest_sha256 = str(seal["semantic_sha256"])

        def next_inspection(
            records: list[dict[str, Any]],
        ) -> Mapping[str, object]:
            prior = [
                record
                for record in records
                if record.get("manifest_sha256") == manifest_sha256
            ]
            if len(prior) >= len(candidates):
                raise ValueError("candidate-manifest-exhausted")
            if (
                sum(record.get("split") == "training" for record in prior)
                >= int(manifest["annex"]["limits"]["silver_candidate_limit"])  # type: ignore[index]
            ):
                raise ValueError("silver-candidate-limit-exhausted")
            expected = candidates[len(prior)]
            assert isinstance(expected, Mapping)
            if candidate_id != expected.get("candidate_id"):
                raise ValueError("out-of-order-inspection")
            return {
                "event": "candidate-inspected",
                "manifest_sha256": manifest_sha256,
                "candidate_id": candidate_id,
                "order_sha256": expected["order_sha256"],
                "split": expected["split"],
                "event_group_id": expected["event_group_id"],
            }

        try:
            record = self._candidate_inspection_log.append_checked(next_inspection)
        except ValueError as error:
            reason = str(error)
            if reason not in {
                "out-of-order-inspection",
                "candidate-manifest-exhausted",
                "silver-candidate-limit-exhausted",
            }:
                raise
            return {
                "inspection": "rejected",
                "stop_reason": reason,
                "candidate_id": candidate_id,
            }
        return {
            "inspection": "accepted",
            "stop_reason": None,
            "candidate_id": candidate_id,
            "record": record,
        }

    def allocate_stage_1(
        self,
        manifest: Mapping[str, object],
        reviews: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        """Allocate Stage 1 from recorded candidate inspections."""
        return allocate_stage_1(
            manifest, reviews, self.candidate_inspection_records()
        )

    def budget_exposure(self) -> dict[str, Decimal]:
        return self._budget_exposure_from(self.cost_records())

    @staticmethod
    def _budget_exposure_from(
        records: list[dict[str, Any]],
    ) -> dict[str, Decimal]:
        exposure = {category: Decimal("0.00") for category in BUDGET_LIMITS}
        actions: dict[str, dict[str, Any]] = {}
        for record in records:
            action_id = str(record["action_id"])
            if record["kind"] == "commitment":
                actions[action_id] = record
            elif record["kind"] == "actual":
                actions[action_id] = record
        for record in actions.values():
            exposure[str(record["category"])] += _money(record["amount_usd"])
        return exposure

    def record_cost(
        self,
        *,
        action_id: str,
        kind: str,
        category: str,
        amount_usd: str,
        evidence: str,
    ) -> dict[str, Any]:
        """Append one commitment or actual cost after all limits pass."""
        if not action_id.strip() or not evidence.strip():
            raise ValueError("The action ID and evidence must contain text.")
        if category not in BUDGET_LIMITS:
            raise ValueError("The budget category is not valid.")
        if kind not in {"commitment", "actual"}:
            raise ValueError("The cost kind must be commitment or actual.")
        amount = _money(amount_usd)
        if category == "contingency":
            raise CostLimitError("contingency-not-authorized")

        def checked_payload(
            records: list[dict[str, Any]],
        ) -> Mapping[str, object]:
            matching = [
                record for record in records if record["action_id"] == action_id
            ]
            if kind == "commitment":
                if matching:
                    raise ValueError("An action ID can have only one commitment.")
            else:
                commitments = [
                    record for record in matching if record["kind"] == "commitment"
                ]
                actuals = [
                    record for record in matching if record["kind"] == "actual"
                ]
                if len(commitments) != 1 or actuals:
                    raise ValueError(
                        "An actual cost must have one commitment that does not have "
                        "an actual cost record."
                    )
                commitment = commitments[0]
                if commitment["category"] != category:
                    raise ValueError(
                        "The actual cost category must agree with its commitment."
                    )
                if amount > _money(commitment["amount_usd"]):
                    raise CostLimitError("actual-cost-exceeds-commitment")

            exposure = self._budget_exposure_from(records)
            current_action_amount = Decimal("0.00")
            if kind == "actual":
                current_action_amount = _money(matching[0]["amount_usd"])
            proposed_category = exposure[category] - current_action_amount + amount
            proposed_total = (
                sum(exposure.values(), start=Decimal("0.00"))
                - current_action_amount
                + amount
            )
            if proposed_category > BUDGET_LIMITS[category]:
                raise CostLimitError("category-budget-exceeded")
            if proposed_total > TOTAL_BUDGET_LIMIT:
                raise CostLimitError("total-budget-exceeded")

            return {
                "action_id": action_id,
                "kind": kind,
                "category": category,
                "amount_usd": _usd(amount),
                "evidence": evidence,
            }

        return self._spend_ledger.append_checked(checked_payload)

    def _decision(
        self,
        run_id: str,
        decision: str,
        stop_reason: str | None,
        evidence: Mapping[str, object] | None = None,
        *,
        record: bool = True,
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "run_id": run_id,
            "stage": 1,
            "decision": decision,
            "stop_reason": stop_reason,
            "permitted_external_actions": (
                ["stage-1-build"] if decision == "build-eligible" else []
            ),
            "external_actions_started": False,
            "evidence": dict(evidence or {}),
        }
        if record:
            self._decision_log.append(
                {
                    "event": "stage-decision",
                    "run_id": run_id,
                    "decision": decision,
                    "stop_reason": stop_reason,
                }
            )
        return result

    def _stop(self, run_id: str, reason: str) -> dict[str, object]:
        return self._decision(run_id, "no-build", reason)

    def evaluate(self, manifest: Mapping[str, object]) -> dict[str, object]:
        """Return the first Stage 1 stop or a complete build decision."""
        run_id = str(manifest.get("run_id", "unknown-run"))
        if (
            manifest.get("schema_version") != 1
            or manifest.get("stage") != 1
            or not run_id.strip()
        ):
            return self._stop(run_id, "invalid-manifest")

        confirmation = manifest.get("confirmation")
        actual_hash = semantic_manifest_sha256(manifest)
        prior_confirmations = [
            record
            for record in self.decision_records()
            if record.get("event") == "manifest-confirmed"
            and record.get("run_id") == run_id
        ]
        supplied_hash = (
            confirmation.get("semantic_sha256")
            if isinstance(confirmation, Mapping)
            else None
        )
        prior_hash = (
            prior_confirmations[0].get("semantic_sha256")
            if prior_confirmations
            else None
        )
        if (confirmation is not None and supplied_hash != actual_hash) or (
            prior_hash is not None and prior_hash != actual_hash
        ):
            self._decision_log.append(
                {
                    "event": "semantic-change-attempted",
                    "run_id": run_id,
                    "confirmed_sha256": prior_hash or supplied_hash,
                    "observed_sha256": actual_hash,
                }
            )
            return self._decision(
                run_id,
                "no-build",
                "semantic-manifest-change",
                record=False,
            )

        if prior_confirmations and isinstance(confirmation, Mapping):
            prior_confirmation = prior_confirmations[0]
            confirmation_changed = any(
                confirmation.get(field) != prior_confirmation.get(field)
                for field in ("confirmed_by", "confirmed_at", "semantic_sha256")
            )
            if confirmation_changed:
                self._decision_log.append(
                    {
                        "event": "confirmation-change-attempted",
                        "run_id": run_id,
                        "semantic_sha256": actual_hash,
                    }
                )
                return self._decision(
                    run_id,
                    "no-build",
                    "confirmation-evidence-changed",
                    record=False,
                )

        if isinstance(confirmation, Mapping) and not prior_confirmations:
            if not confirmation.get("confirmed_by") or not confirmation.get("confirmed_at"):
                return self._stop(run_id, "manifest-not-confirmed")
            self._decision_log.append(
                {
                    "event": "manifest-confirmed",
                    "run_id": run_id,
                    "semantic_sha256": actual_hash,
                    "confirmed_by": confirmation["confirmed_by"],
                    "confirmed_at": confirmation["confirmed_at"],
                }
            )

        source = manifest.get("source")
        if not isinstance(source, Mapping):
            return self._stop(run_id, "source-rights-failed")
        source_evidence = source.get("evidence")
        source_passes = (
            source.get("source_type") == "financial-news"
            and bool(source.get("source_id"))
            and all(source.get(field) is True for field in RIGHTS_FIELDS)
            and isinstance(source_evidence, Mapping)
            and all(
                bool(source_evidence.get(field))
                for field in ("checked_at", "terms_url", "reviewer")
            )
        )
        if not source_passes:
            return self._stop(run_id, "source-rights-failed")

        panel = manifest.get("route_panel")
        if not isinstance(panel, Mapping) or panel.get("inspection_complete") is not True:
            return self._stop(run_id, "route-panel-incomplete")
        routes = panel.get("routes")
        if not isinstance(routes, list):
            return self._stop(run_id, "route-panel-incomplete")
        route_ids = [
            route.get("route_id") for route in routes if isinstance(route, Mapping)
        ]
        if (
            len(route_ids) != len(routes)
            or len(route_ids) != len(set(route_ids))
            or not set(EXPECTED_ROUTE_IDS).issubset(route_ids)
            or any(not _is_fixed_route_id(route_id) for route_id in route_ids)
        ):
            return self._stop(run_id, "route-panel-incomplete")
        eligible_routes = [
            route
            for route in routes
            if isinstance(route, Mapping)
            and bool(route.get("route_id"))
            and all(route.get(field) is True for field in ROUTE_ELIGIBILITY_FIELDS)
            and isinstance(route.get("evidence"), Mapping)
            and all(
                route["evidence"].get(field)
                for field in ("checked_at", "account", "terms_url")
            )
        ]
        if len(eligible_routes) < 3:
            return self._stop(run_id, "insufficient-eligible-routes")

        required_days = 0
        try:
            for route in eligible_routes:
                remaining_experiment_requests = int(
                    route["remaining_experiment_requests"]
                )
                free_requests_remaining = int(route["free_requests_remaining"])
                current_stage_requests = int(route["current_stage_requests"])
                requests_per_day = int(route["requests_per_day"])
                available_days = int(route["available_days"])
                if (
                    min(
                        remaining_experiment_requests,
                        free_requests_remaining,
                        current_stage_requests,
                        requests_per_day,
                        available_days,
                    )
                    < 0
                    or requests_per_day == 0
                ):
                    raise ValueError
                if free_requests_remaining < remaining_experiment_requests:
                    return self._stop(run_id, "route-demand-exceeds-free-capacity")
                route_days = math.ceil(current_stage_requests / requests_per_day)
                required_days = max(required_days, route_days)
                if route_days > available_days:
                    return self._stop(run_id, "route-schedule-infeasible")
        except (KeyError, TypeError, ValueError):
            return self._stop(run_id, "invalid-route-demand")

        schedule = manifest.get("schedule")
        if not isinstance(schedule, Mapping) or not all(
            schedule.get(field) for field in ("starts_on", "must_finish_by", "evidence")
        ):
            return self._stop(run_id, "route-schedule-infeasible")
        try:
            starts_on = date.fromisoformat(str(schedule["starts_on"]))
            must_finish_by = date.fromisoformat(str(schedule["must_finish_by"]))
        except (ValueError, TypeError):
            return self._stop(run_id, "route-schedule-infeasible")
        schedule_days = (must_finish_by - starts_on).days + 1
        if schedule_days < required_days:
            return self._stop(run_id, "route-schedule-infeasible")

        if not isinstance(confirmation, Mapping):
            return self._stop(run_id, "manifest-not-confirmed")

        budget = manifest.get("budget")
        if not isinstance(budget, Mapping) or not budget.get("evidence"):
            return self._stop(run_id, "invalid-budget-evidence")
        planned_input = budget.get("planned_commitments_usd")
        if not isinstance(planned_input, Mapping) or set(planned_input) != set(BUDGET_LIMITS):
            return self._stop(run_id, "invalid-budget-evidence")
        try:
            planned = {
                category: _money(planned_input[category]) for category in BUDGET_LIMITS
            }
        except ValueError:
            return self._stop(run_id, "invalid-budget-evidence")
        if planned["contingency"] != 0:
            return self._stop(run_id, "contingency-not-authorized")

        exposure = self.budget_exposure()
        combined = {
            category: exposure[category] + planned[category]
            for category in BUDGET_LIMITS
        }
        for category, amount in combined.items():
            if amount > BUDGET_LIMITS[category]:
                return self._stop(run_id, "category-budget-exceeded")
        if sum(combined.values()) > TOTAL_BUDGET_LIMIT:
            return self._stop(run_id, "total-budget-exceeded")

        evidence = {
            "source": {
                "source_id": source["source_id"],
                "rights": {field: source[field] for field in RIGHTS_FIELDS},
                "evidence": source_evidence,
            },
            "routes": {
                "inspection_complete": True,
                "eligible_route_ids": [route["route_id"] for route in eligible_routes],
                "evidence": {
                    str(route["route_id"]): route["evidence"]
                    for route in eligible_routes
                },
            },
            "schedule": {
                **dict(schedule),
                "required_days": required_days,
                "available_days": schedule_days,
            },
            "confirmation": dict(confirmation),
            "budget": {
                "category_limits_usd": {
                    category: _usd(limit) for category, limit in BUDGET_LIMITS.items()
                },
                "total_limit_usd": _usd(TOTAL_BUDGET_LIMIT),
                "ledger_exposure_usd": {
                    category: _usd(amount) for category, amount in exposure.items()
                },
                "planned_commitments_usd": {
                    category: _usd(amount) for category, amount in planned.items()
                },
                "planned_total_usd": _usd(
                    sum(planned.values(), start=Decimal("0.00"))
                ),
                "evidence": budget["evidence"],
            },
        }
        return self._decision(run_id, "build-eligible", None, evidence)


def _read_manifest(path: str) -> dict[str, object]:
    with Path(path).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("The manifest must be a JSON object.")
    return value


def _read_reviews(path: str) -> list[Mapping[str, object]]:
    with Path(path).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("The reviews file must be a JSON array of objects.")
    return value


def _write_json(value: object) -> None:
    json.dump(value, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control a safe Stage 1 run.")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check", help="Apply the Stage 1 staged feasibility gate."
    )
    check.add_argument("manifest")
    check.add_argument("--state-dir", required=True)

    confirm = commands.add_parser("confirm", help="Confirm the current manifest.")
    confirm.add_argument("manifest")
    confirm.add_argument("--confirmed-by", required=True)
    confirm.add_argument("--output", required=True)

    cost = commands.add_parser("record-cost", help="Append one checked cost record.")
    cost.add_argument("--state-dir", required=True)
    cost.add_argument("--action-id", required=True)
    cost.add_argument("--kind", choices=("commitment", "actual"), required=True)
    cost.add_argument("--category", choices=tuple(BUDGET_LIMITS), required=True)
    cost.add_argument("--amount-usd", required=True)
    cost.add_argument("--evidence", required=True)

    admit = commands.add_parser(
        "admit-example", help="Validate one Stage 1 target-aspect example."
    )
    admit.add_argument("example")

    seal_candidates = commands.add_parser(
        "seal-candidates", help="Validate and seal one candidate manifest."
    )
    seal_candidates.add_argument("manifest")
    seal_candidates.add_argument("--sealed-by", required=True)
    seal_candidates.add_argument("--output", required=True)

    inspect = commands.add_parser(
        "inspect-candidate", help="Inspect the next sealed candidate."
    )
    inspect.add_argument("manifest")
    inspect.add_argument("candidate_id", metavar="candidate-id")
    inspect.add_argument("--state-dir", required=True)

    allocate = commands.add_parser(
        "allocate-stage-1", help="Create the fixed Stage 1 data allocation."
    )
    allocate.add_argument("manifest")
    allocate.add_argument("reviews")
    allocate.add_argument("--output", required=True)
    allocate.add_argument("--state-dir", required=True)

    collect = commands.add_parser(
        "collect-votes", help="Collect fixed-route Stage 1 model votes."
    )
    collect.add_argument("stage_manifest")
    collect.add_argument("candidate_manifest")
    collect.add_argument("allocation")
    collect.add_argument("--state-dir", required=True)
    collect.add_argument(
        "--base-url",
        default=os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128"),
    )
    collect.add_argument("--timeout-seconds", type=float, default=60)

    aggregate = commands.add_parser(
        "aggregate-silver", help="Aggregate votes into accepted silver labels."
    )
    aggregate.add_argument("stage_manifest")
    aggregate.add_argument("candidate_manifest")
    aggregate.add_argument("allocation")
    aggregate.add_argument("--output", required=True)
    aggregate.add_argument("--state-dir", required=True)

    gpt = commands.add_parser(
        "predict-blind-gpt", help="Seal the GPT blind prediction file."
    )
    gpt.add_argument("stage_manifest")
    gpt.add_argument("candidate_manifest")
    gpt.add_argument("allocation")
    gpt.add_argument("forecast")
    gpt.add_argument("--output", required=True)
    gpt.add_argument("--state-dir", required=True)
    gpt.add_argument(
        "--base-url",
        default=os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128"),
    )
    gpt.add_argument("--timeout-seconds", type=float, default=120)

    args = parser.parse_args(argv)
    try:
        if args.command == "admit-example":
            result = admit_example(
                _read_manifest(args.example), load_modernbert_tokenizer()
            )
            _write_json(result)
            return 0 if result["admission"] == "accepted" else 2
        if args.command == "seal-candidates":
            sealed = seal_candidate_manifest(
                _read_manifest(args.manifest), args.sealed_by
            )
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(sealed, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_json({"sealed_candidate_manifest": str(output_path)})
            return 0
        if args.command == "allocate-stage-1":
            allocation = StageRun(args.state_dir).allocate_stage_1(
                _read_manifest(args.manifest), _read_reviews(args.reviews)
            )
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(allocation, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_json(
                {
                    "stage_1_allocation": str(output_path),
                    "allocation": allocation["allocation"],
                    "stop_reason": allocation["stop_reason"],
                }
            )
            return 0 if allocation["allocation"] == "complete" else 2
        if args.command == "collect-votes":
            if args.timeout_seconds <= 0:
                raise ValueError("The timeout must be more than zero.")
            result = StageRun(args.state_dir).collect_votes(
                _read_manifest(args.stage_manifest),
                _read_manifest(args.candidate_manifest),
                _read_manifest(args.allocation),
                OmniRouteHttpTransport(
                    args.base_url,
                    api_key=os.environ.get("OMNIROUTE_API_KEY"),
                ),
                timeout_seconds=args.timeout_seconds,
            )
            _write_json(result)
            return 0 if result["collection"] == "complete" else 2
        if args.command == "predict-blind-gpt":
            if args.timeout_seconds <= 0:
                raise ValueError("The timeout must be more than zero.")
            predictions = StageRun(args.state_dir).predict_blind_gpt(
                _read_manifest(args.stage_manifest),
                _read_manifest(args.candidate_manifest),
                _read_manifest(args.allocation),
                OmniRouteHttpTransport(
                    args.base_url,
                    api_key=os.environ.get("OMNIROUTE_API_KEY"),
                ),
                forecast=_read_manifest(args.forecast),
                timeout_seconds=args.timeout_seconds,
            )
            complete = predictions["gpt_predictions"] == "sealed"
            if complete:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(predictions, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            _write_json(
                {
                    "gpt_prediction_file": args.output if complete else None,
                    "gpt_predictions": predictions["gpt_predictions"],
                    "stop_reason": predictions["stop_reason"],
                    "prediction_count": predictions["prediction_count"],
                }
            )
            return 0 if complete else 2
        if args.command == "aggregate-silver":
            aggregated = StageRun(args.state_dir).aggregate_silver_labels(
                _read_manifest(args.stage_manifest),
                _read_manifest(args.candidate_manifest),
                _read_manifest(args.allocation),
            )
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(aggregated, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_json(
                {
                    "accepted_silver_labels": str(output_path),
                    "aggregation": aggregated["aggregation"],
                    "stop_reason": aggregated["stop_reason"],
                    "accepted_silver_count": aggregated["accepted_silver_count"],
                }
            )
            return 0 if aggregated["aggregation"] == "complete" else 2
        if args.command == "confirm":
            confirmed = confirm_manifest(_read_manifest(args.manifest), args.confirmed_by)
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(confirmed, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _write_json({"confirmed_manifest": str(output_path)})
            return 0
        runner = StageRun(args.state_dir)
        if args.command == "inspect-candidate":
            result = runner.inspect_candidate(
                _read_manifest(args.manifest), args.candidate_id
            )
            _write_json(result)
            return 0 if result["inspection"] == "accepted" else 2
        if args.command == "record-cost":
            _write_json(
                runner.record_cost(
                    action_id=args.action_id,
                    kind=args.kind,
                    category=args.category,
                    amount_usd=args.amount_usd,
                    evidence=args.evidence,
                )
            )
            return 0
        decision = runner.evaluate(_read_manifest(args.manifest))
        _write_json(decision)
        return 0 if decision["decision"] == "build-eligible" else 2
    except (AuditLogError, CostLimitError, OSError, RuntimeError, ValueError) as error:
        _write_json({"error": type(error).__name__, "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
