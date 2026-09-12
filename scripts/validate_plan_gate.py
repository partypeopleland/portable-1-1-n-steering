#!/usr/bin/env python3
"""Validate a plan, one frontier review or an independent fallback pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SHA = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
KNOWN_REVIEW_MODELS = frozenset({"gpt-6-astra", "gpt-5.6-sol"})
RISK_TIERS = frozenset({"low", "medium", "high", "unknown"})
REVIEW_MODES = frozenset({"frontier-single", "dual-fallback", "owner-choice"})
FRONTIER_PROVIDER = "openai"
FRONTIER_CAPABILITY = "frontier-plan-review"
# These are explicit, portable labels for host adapters, not claims that every
# installation exposes either adapter. Add a new adapter only through a reviewed
# allowlist change.
FALLBACK_REVIEWERS = {
    ("agy", "gemini-3.8-flash-high"): "agy-high-plan-review",
    ("devin", "swe-2-high"): "SWE-2 high",
}
PLAN_TASK = re.compile(r"(?m)^- task_id: `([^`]+)`$")
PLAN_REVISION = re.compile(r"(?m)^- revision: `([^`]+)`$")
PLAN_RISK = re.compile(r"(?m)^- risk_tier: `([^`]+)`$")
PLAN_MODE = re.compile(r"(?m)^- review_mode: `([^`]+)`$")
PLAN_RATIONALE = re.compile(r"(?m)^- review_rationale: (.+)$")

REVIEW_FIELDS = frozenset(
    {
        "task",
        "plan_revision",
        "plan_sha256",
        "reviewer_id",
        "reviewer_model",
        "review_mode",
        "provider",
        "capability",
        "scope",
        "blockers",
        "high_findings",
        "findings",
        "required_changes",
        "conclusion",
        "marker",
    }
)
DISPATCH_FIELDS = frozenset(
    {
        "task",
        "plan_revision",
        "plan_sha256",
        "reviewer_id",
        "provider",
        "model",
        "capability",
        "review_mode",
        "scope",
    }
)


class GateError(ValueError):
    """Raised when the execution gate is not satisfied."""


def _fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in REVIEW_FIELDS:
            if key in fields:
                raise GateError(f"duplicate review field: {key}")
            # The single space after the colon is syntax, not part of the value;
            # any additional or trailing whitespace remains visible and fails the
            # exact identity/capability checks below.
            fields[key] = value[1:] if value.startswith(" ") else value
    return fields


def _model_meets_floor(value: Any) -> bool:
    return isinstance(value, str) and value in KNOWN_REVIEW_MODELS


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(
        character in value for character in ("\x00", "\r", "\n")
    ):
        raise GateError(f"{label} must be a non-empty single-line string")
    if value != value.strip():
        raise GateError(f"{label} must not have surrounding whitespace")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _nonempty(value, label)
    if not IDENTIFIER.fullmatch(value):
        raise GateError(f"{label} must be a portable identifier")
    return value


def _load_dispatch(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GateError(f"duplicate dispatch field: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise GateError("dispatch evidence must be a JSON object")
    return value


def _as_list(value: Any, label: str) -> list[Any]:
    if isinstance(value, (str, bytes, dict)):
        return [value]
    if not isinstance(value, list) or not value:
        raise GateError(f"{label} must contain at least one artifact")
    return value


def _plan_metadata(plan_text: str) -> dict[str, str]:
    patterns = {
        "task": PLAN_TASK,
        "revision": PLAN_REVISION,
        "risk_tier": PLAN_RISK,
        "review_mode": PLAN_MODE,
        "review_rationale": PLAN_RATIONALE,
    }
    result: dict[str, str] = {}
    for key, pattern in patterns.items():
        matches = pattern.findall(plan_text)
        if len(matches) != 1:
            raise GateError(f"plan must contain exactly one {key} identity")
        result[key] = matches[0].strip()
    if result["risk_tier"] not in RISK_TIERS:
        raise GateError("plan risk_tier is not recognized")
    if result["review_mode"] not in REVIEW_MODES:
        raise GateError("plan review_mode is not recognized")
    return result


def _validate_dispatch(
    dispatch: Any, plan: dict[str, str], digest: str, index: int
) -> dict[str, str]:
    if not isinstance(dispatch, dict):
        raise GateError(f"dispatch {index} must be a JSON object")
    unknown = sorted(set(dispatch) - DISPATCH_FIELDS)
    missing = sorted(DISPATCH_FIELDS - set(dispatch))
    if unknown:
        raise GateError(f"dispatch {index} has unknown fields: {', '.join(unknown)}")
    if missing:
        raise GateError(f"dispatch {index} missing fields: {', '.join(missing)}")
    values = {key: _nonempty(dispatch[key], f"dispatch {index} {key}") for key in DISPATCH_FIELDS}
    values["reviewer_id"] = _identifier(dispatch["reviewer_id"], f"dispatch {index} reviewer_id")
    if values["task"] != plan["task"] or values["plan_revision"] != plan["revision"]:
        raise GateError(f"dispatch {index} plan identity does not match")
    if values["plan_sha256"] != digest or not SHA.fullmatch(values["plan_sha256"]):
        raise GateError(f"dispatch {index} plan_sha256 does not match the plan")
    if values["review_mode"] != plan["review_mode"]:
        raise GateError(f"dispatch {index} review_mode does not match the plan")
    if values["scope"] != "read-only":
        raise GateError(f"dispatch {index} scope must be read-only")
    if plan["review_mode"] == "frontier-single":
        if not _model_meets_floor(values["model"]):
            raise GateError("reviewer model does not meet the capability floor")
        if values["provider"] != FRONTIER_PROVIDER or values["capability"] != FRONTIER_CAPABILITY:
            raise GateError("frontier dispatch provider/capability is not recognized")
    elif (values["provider"], values["model"]) not in FALLBACK_REVIEWERS:
        raise GateError(f"dispatch {index} is not an approved fallback reviewer")
    expected_capability = (
        FRONTIER_CAPABILITY
        if plan["review_mode"] == "frontier-single"
        else FALLBACK_REVIEWERS[(values["provider"], values["model"])]
    )
    if values["capability"] != expected_capability:
        raise GateError(f"dispatch {index} capability does not match its model/provider")
    return values


def _validate_review(
    review_text: str, plan: dict[str, str], digest: str, dispatch: dict[str, str], index: int
) -> dict[str, str]:
    fields = _fields(review_text)
    missing = sorted(REVIEW_FIELDS - fields.keys())
    if missing:
        raise GateError(f"review {index} missing required fields: {', '.join(missing)}")
    if fields["task"] != plan["task"]:
        raise GateError(f"review {index} task does not match the plan")
    if fields["plan_revision"] != plan["revision"]:
        raise GateError(f"review {index} revision does not match the plan")
    if fields["plan_sha256"] != digest or not SHA.fullmatch(fields["plan_sha256"]):
        raise GateError(f"review {index} plan_sha256 does not match the plan")
    if fields["review_mode"] != plan["review_mode"]:
        raise GateError(f"review {index} review_mode does not match the plan")
    if fields["scope"] != "read-only":
        raise GateError(f"review {index} scope must be read-only")
    if fields["reviewer_id"] != dispatch["reviewer_id"]:
        raise GateError(f"review {index} reviewer_id does not match dispatch")
    if fields["reviewer_model"] != dispatch["model"]:
        raise GateError(f"review {index} model does not match dispatch")
    if fields["provider"] != dispatch["provider"] or fields["capability"] != dispatch["capability"]:
        raise GateError(f"review {index} provider/capability does not match dispatch")
    _nonempty(fields["findings"], f"review {index} findings")
    if fields["blockers"] != "0" or fields["high_findings"] != "0":
        raise GateError(f"review {index} blocker/high findings must be 0")
    if fields["conclusion"] != "LGTM" or fields["marker"] != "LGTM":
        raise GateError(f"review {index} must conclude with LGTM")
    if fields["required_changes"].lower() != "none":
        raise GateError(f"review {index} LGTM must have required_changes: none")
    if plan["review_mode"] == "frontier-single" and not _model_meets_floor(fields["reviewer_model"]):
        raise GateError("reviewer model does not meet the capability floor")
    return fields


def validate_gate(plan: bytes, reviews: Any, dispatches: Any) -> str:
    digest = hashlib.sha256(plan).hexdigest()
    try:
        plan_text = plan.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GateError("plan must be UTF-8") from error
    plan_meta = _plan_metadata(plan_text)
    if plan_meta["review_mode"] == "owner-choice":
        raise GateError("owner-choice requires an Owner decision before review dispatch")
    review_values = _as_list(reviews, "reviews")
    dispatch_values = _as_list(dispatches, "dispatches")
    if len(review_values) != len(dispatch_values):
        raise GateError("review and dispatch artifact counts must match")
    if plan_meta["review_mode"] == "frontier-single" and len(review_values) != 1:
        raise GateError("frontier-single requires exactly one reviewer")
    if plan_meta["review_mode"] == "dual-fallback":
        if len(review_values) < 2:
            raise GateError("dual-fallback requires at least two independent reviewers")
        if plan_meta["risk_tier"] in {"high", "unknown"}:
            raise GateError("high or unknown risk requires frontier review or Owner choice")
    dispatches_checked = [
        _validate_dispatch(dispatch, plan_meta, digest, index)
        for index, dispatch in enumerate(dispatch_values, start=1)
    ]
    if plan_meta["review_mode"] == "dual-fallback":
        reviewer_ids = [item["reviewer_id"] for item in dispatches_checked]
        providers = [item["provider"] for item in dispatches_checked]
        if len(set(reviewer_ids)) != len(reviewer_ids):
            raise GateError("dual-fallback reviewer identities must be distinct")
        if len(set(providers)) != len(providers):
            raise GateError("dual-fallback providers must be independent")
    for index, (review, dispatch) in enumerate(
        zip(review_values, dispatches_checked), start=1
    ):
        if not isinstance(review, str):
            raise GateError(f"review {index} must be text")
        _validate_review(review, plan_meta, digest, dispatch, index)
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--dispatch", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    try:
        reviews = [path.read_text(encoding="utf-8") for path in args.review]
        dispatches = [_load_dispatch(path) for path in args.dispatch]
        digest = validate_gate(args.plan.read_bytes(), reviews, dispatches)
    except (OSError, json.JSONDecodeError, GateError) as error:
        parser.error(str(error))
    print(f"PLAN_GATE_LGTM plan_sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
