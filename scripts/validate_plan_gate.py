#!/usr/bin/env python3
"""Validate the plan/review/dispatch gate without executing the plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SHA = re.compile(r"^[0-9a-f]{64}$")
KNOWN_REVIEW_MODELS = frozenset({"gpt-6-astra", "gpt-5.6-sol"})
PLAN_TASK = re.compile(r"(?m)^- task_id: `([^`]+)`$")
PLAN_REVISION = re.compile(r"(?m)^- revision: `([^`]+)`$")


class GateError(ValueError):
    """Raised when the execution gate is not satisfied."""


def _fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in {
            "task",
            "plan_revision",
            "plan_sha256",
            "reviewer_model",
            "scope",
            "blockers",
            "high_findings",
            "findings",
            "required_changes",
            "conclusion",
            "marker",
        }:
            if key in fields:
                raise GateError(f"duplicate review field: {key}")
            fields[key] = value.strip()
    return fields


def _model_meets_floor(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value in KNOWN_REVIEW_MODELS


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


def _nonnegative_zero(fields: dict[str, str], key: str) -> None:
    if fields.get(key) != "0":
        raise GateError(f"{key} must be 0")


def validate_gate(plan: bytes, review_text: str, dispatch: Any) -> str:
    digest = hashlib.sha256(plan).hexdigest()
    if not isinstance(dispatch, dict):
        raise GateError("dispatch evidence must be a JSON object")
    if "model" not in dispatch or "reviewer_model" in dispatch:
        raise GateError("dispatch must contain exactly one model field")
    model = dispatch.get("model")
    if not _model_meets_floor(model):
        raise GateError("reviewer model does not meet the capability floor")
    fields = _fields(review_text)
    required = {
        "task",
        "plan_revision",
        "plan_sha256",
        "reviewer_model",
        "scope",
        "blockers",
        "high_findings",
        "findings",
        "required_changes",
        "conclusion",
        "marker",
    }
    missing = sorted(required - fields.keys())
    if missing:
        raise GateError(f"review missing required fields: {', '.join(missing)}")
    reviewer_model = fields.get("reviewer_model")
    if not _model_meets_floor(reviewer_model):
        raise GateError("review artifact model does not meet the capability floor")
    if reviewer_model != model:
        raise GateError("dispatch model and review model do not match")
    if fields.get("plan_sha256") != digest or not SHA.fullmatch(fields.get("plan_sha256", "")):
        raise GateError("review plan_sha256 does not match the plan")
    if fields.get("scope") != "read-only":
        raise GateError("review scope must be read-only")
    _nonnegative_zero(fields, "blockers")
    _nonnegative_zero(fields, "high_findings")
    if fields.get("conclusion") != "LGTM" or fields.get("marker") != "LGTM":
        raise GateError("review must conclude with LGTM")
    if fields.get("required_changes", "").lower() != "none":
        raise GateError("LGTM review must have required_changes: none")
    plan_text = plan.decode("utf-8")
    plan_tasks = PLAN_TASK.findall(plan_text)
    if len(plan_tasks) != 1:
        raise GateError("plan must contain exactly one task identity")
    if fields["task"] != plan_tasks[0]:
        raise GateError("review task does not match the plan")
    plan_revisions = PLAN_REVISION.findall(plan_text)
    if len(plan_revisions) != 1:
        raise GateError("plan must contain exactly one revision identity")
    if fields["plan_revision"] != plan_revisions[0]:
        raise GateError("review revision does not match the plan")
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--dispatch", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        digest = validate_gate(
            args.plan.read_bytes(),
            args.review.read_text(encoding="utf-8"),
            _load_dispatch(args.dispatch),
        )
    except (OSError, json.JSONDecodeError, GateError) as error:
        parser.error(str(error))
    print(f"PLAN_GATE_LGTM plan_sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
