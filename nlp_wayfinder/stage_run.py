"""Safe Stage 1 preflight and append-only audit records."""

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
from typing import Any


EXPECTED_ROUTE_IDS = (
    "mistral/mistral-medium-3-5",
    "cf/@cf/zai-org/glm-4.7-flash",
    "groq/qwen/qwen3.6-27b",
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
    "account_free_limit_verified",
    "training_use_permitted",
    "audit_fields_supported",
    "no_paid_overflow",
)


class AuditLogError(ValueError):
    """Raised when an append-only record is invalid or was changed."""


class CostLimitError(ValueError):
    """Raised before a cost record could exceed a fixed limit."""


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
        raise ValueError("confirmed_by must not be empty")
    confirmed = copy.deepcopy(dict(manifest))
    confirmed["confirmation"] = {
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at or _now(),
        "semantic_sha256": semantic_manifest_sha256(confirmed),
    }
    return confirmed


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
                raise AuditLogError(f"blank append-only record at line {index}")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise AuditLogError(
                    f"invalid append-only record at line {index}"
                ) from error
            if not isinstance(record, dict):
                raise AuditLogError(f"invalid append-only record at line {index}")
            if record.get("sequence") != index:
                raise AuditLogError(f"invalid sequence at line {index}")
            if record.get("previous_record_sha256") != previous_hash:
                raise AuditLogError(f"broken hash chain at line {index}")
            expected_hash = self._record_hash(record)
            if record.get("record_sha256") != expected_hash:
                raise AuditLogError(f"changed append-only record at line {index}")
            previous_hash = expected_hash
            records.append(record)
        return records

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return self._parse(self.path.read_text(encoding="utf-8"))

    def append(self, payload: Mapping[str, object]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.seek(0)
            records = self._parse(stream.read())
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
        raise ValueError("invalid USD amount") from error
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("USD amounts must be non-negative and have at most two decimals")
    return amount


def _usd(value: Decimal) -> str:
    return f"{value:.2f}"


class StageRun:
    """Evaluate Stage 1 gates and own the two append-only audit logs."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        clock: Callable[[], str] = _now,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.spend_ledger_path = self.state_dir / "spend-ledger.jsonl"
        self.decision_log_path = self.state_dir / "decision-log.jsonl"
        self._spend_ledger = _AppendOnlyJsonl(self.spend_ledger_path, clock)
        self._decision_log = _AppendOnlyJsonl(self.decision_log_path, clock)

    def cost_records(self) -> list[dict[str, Any]]:
        return self._spend_ledger.read()

    def decision_records(self) -> list[dict[str, Any]]:
        return self._decision_log.read()

    def budget_exposure(self) -> dict[str, Decimal]:
        exposure = {category: Decimal("0.00") for category in BUDGET_LIMITS}
        actions: dict[str, dict[str, Any]] = {}
        for record in self.cost_records():
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
            raise ValueError("action_id and evidence must not be empty")
        if category not in BUDGET_LIMITS:
            raise ValueError("unknown budget category")
        if kind not in {"commitment", "actual"}:
            raise ValueError("cost kind must be commitment or actual")
        amount = _money(amount_usd)
        if category == "contingency":
            raise CostLimitError("contingency-not-authorized")

        records = self.cost_records()
        matching = [record for record in records if record["action_id"] == action_id]
        if kind == "commitment":
            if matching:
                raise ValueError("an action_id can have only one commitment")
        else:
            commitments = [record for record in matching if record["kind"] == "commitment"]
            actuals = [record for record in matching if record["kind"] == "actual"]
            if len(commitments) != 1 or actuals:
                raise ValueError("an actual cost needs one unsettled commitment")
            commitment = commitments[0]
            if commitment["category"] != category:
                raise ValueError("actual cost category must match its commitment")
            if amount > _money(commitment["amount_usd"]):
                raise CostLimitError("actual-cost-exceeds-commitment")

        exposure = self.budget_exposure()
        current_action_amount = Decimal("0.00")
        if kind == "actual":
            current_action_amount = _money(matching[0]["amount_usd"])
        proposed_category = exposure[category] - current_action_amount + amount
        proposed_total = sum(exposure.values()) - current_action_amount + amount
        if proposed_category > BUDGET_LIMITS[category]:
            raise CostLimitError("category-budget-exceeded")
        if proposed_total > TOTAL_BUDGET_LIMIT:
            raise CostLimitError("total-budget-exceeded")

        return self._spend_ledger.append(
            {
                "action_id": action_id,
                "kind": kind,
                "category": category,
                "amount_usd": _usd(amount),
                "evidence": evidence,
            }
        )

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
                remaining = int(route["remaining_experiment_requests"])
                free = int(route["free_requests_remaining"])
                current = int(route["current_stage_requests"])
                daily = int(route["requests_per_day"])
                available_days = int(route["available_days"])
                if min(remaining, free, current, daily, available_days) < 0 or daily == 0:
                    raise ValueError
                if free < remaining:
                    return self._stop(run_id, "route-demand-exceeds-free-capacity")
                route_days = math.ceil(current / daily)
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
        raise ValueError("manifest must be a JSON object")
    return value


def _write_json(value: object) -> None:
    json.dump(value, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control a safe Stage 1 run.")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="Run all Stage 1 preflight gates.")
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

    args = parser.parse_args(argv)
    try:
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
    except (AuditLogError, CostLimitError, OSError, ValueError) as error:
        _write_json({"error": type(error).__name__, "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
