"""Safe Stage 1 feasibility gate and append-only audit records."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
import sys
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol


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


class AuditLogError(ValueError):
    """Raised when an append-only record is invalid or was changed."""


class CostLimitError(ValueError):
    """Raised before a cost record could exceed a fixed limit."""


class Tokenizer(Protocol):
    """The tokenizer operation that example admission needs."""

    def __call__(self, text: str, **kwargs: object) -> Mapping[str, object]: ...


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
    if limits["silver_candidate_limit"] != 6_668:
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


class StageRun:
    """Evaluate Stage 1 gates and own its append-only audit logs."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        clock: Callable[[], str] = _now,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.spend_ledger_path = self.state_dir / "spend-ledger.jsonl"
        self.decision_log_path = self.state_dir / "decision-log.jsonl"
        self.candidate_inspection_log_path = (
            self.state_dir / "candidate-inspection-log.jsonl"
        )
        self._spend_ledger = _AppendOnlyJsonl(self.spend_ledger_path, clock)
        self._decision_log = _AppendOnlyJsonl(self.decision_log_path, clock)
        self._candidate_inspection_log = _AppendOnlyJsonl(
            self.candidate_inspection_log_path, clock
        )

    def cost_records(self) -> list[dict[str, Any]]:
        return self._spend_ledger.read()

    def decision_records(self) -> list[dict[str, Any]]:
        return self._decision_log.read()

    def candidate_inspection_records(self) -> list[dict[str, Any]]:
        return self._candidate_inspection_log.read()

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
        if len(route_ids) != len(set(route_ids)) or not set(EXPECTED_ROUTE_IDS).issubset(
            route_ids
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
