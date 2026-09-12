#!/usr/bin/env python3
"""Render a deterministic Plan-Gated Execution plan from JSON metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


REQUIRED = (
    "task_id",
    "revision",
    "owner_authorization",
    "objective",
    "scope",
    "exclusions",
    "sources",
    "dependencies",
    "steps",
    "risk_and_authority",
    "validation",
    "rollback",
    "deliverables",
    "acceptance",
)
ALLOWED = frozenset(REQUIRED)
TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
PLACEHOLDER = re.compile(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*")
CREDENTIAL = re.compile(
    r"(?i)(?:-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|\b(?:api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|password|passwd|secret)\b\s*[:=]\s*"
    r"[\"']?[A-Za-z0-9_./+=-]{8,}|\bgh[pousr]_[A-Za-z0-9_]{20,}\b|"
    r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b|\bAKIA[0-9A-Z]{16}\b|"
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b|\b(?:https?|ssh)://[^/\s:@]+:[^@\s]+@)"
)


class PlanError(ValueError):
    """Raised when metadata is not safe or complete."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{field} must be a non-empty string")
    value = value.strip()
    if any(control in value for control in ("\x00", "\r", "\n")):
        raise PlanError(f"{field} must not contain control characters")
    if PLACEHOLDER.search(value):
        raise PlanError(f"{field} contains an unresolved placeholder")
    if CREDENTIAL.search(value):
        raise PlanError(f"{field} contains credential-like content")
    return value


def _items(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PlanError(f"{field} must be a non-empty list")
    return [_text(item, f"{field}[{index}]") for index, item in enumerate(value)]


def normalize(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise PlanError("metadata must be a JSON object")
    unknown = sorted(set(metadata) - ALLOWED)
    if unknown:
        raise PlanError(f"unknown metadata fields: {', '.join(unknown)}")
    missing = [field for field in REQUIRED if field not in metadata]
    if missing:
        raise PlanError(f"missing required fields: {', '.join(missing)}")
    task_id = _text(metadata["task_id"], "task_id")
    if not TASK_ID.fullmatch(task_id):
        raise PlanError("task_id must be a portable identifier")
    revision = metadata["revision"]
    if isinstance(revision, bool) or not isinstance(revision, (int, str)):
        raise PlanError("revision must be a positive integer or text identifier")
    if isinstance(revision, int) and revision < 1:
        raise PlanError("revision must be positive")
    if isinstance(revision, str):
        revision = _text(revision, "revision")
    return {
        "task_id": task_id,
        "revision": revision,
        "owner_authorization": _text(metadata["owner_authorization"], "owner_authorization"),
        "objective": _text(metadata["objective"], "objective"),
        "scope": _items(metadata["scope"], "scope"),
        "exclusions": _items(metadata["exclusions"], "exclusions"),
        "sources": _items(metadata["sources"], "sources"),
        "dependencies": _items(metadata["dependencies"], "dependencies"),
        "steps": _items(metadata["steps"], "steps"),
        "risk_and_authority": _items(metadata["risk_and_authority"], "risk_and_authority"),
        "validation": _items(metadata["validation"], "validation"),
        "rollback": _items(metadata["rollback"], "rollback"),
        "deliverables": _items(metadata["deliverables"], "deliverables"),
        "acceptance": _items(metadata["acceptance"], "acceptance"),
    }


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def render_plan(metadata: Any) -> str:
    values = normalize(metadata)
    sections = (
        ("Scope", values["scope"]),
        ("Exclusions", values["exclusions"]),
        ("Sources of truth", values["sources"]),
        ("Assumptions and dependencies", values["dependencies"]),
        ("Ordered steps", values["steps"]),
        ("Risk and authority", values["risk_and_authority"]),
        ("Validation", values["validation"]),
        ("Rollback and safe stop", values["rollback"]),
        ("Deliverables", values["deliverables"]),
        ("Acceptance", values["acceptance"]),
    )
    body = [
        f"# Plan: {values['objective']}",
        "",
        f"- task_id: `{values['task_id']}`",
        f"- revision: `{values['revision']}`",
        f"- owner_authorization: {values['owner_authorization']}",
        "",
    ]
    for title, items in sections:
        body.extend((f"## {title}", "", _bullets(items), ""))
    body.extend(
        (
            "## Execution gate",
            "",
            "The main task window must obtain an independent read-only reviewer `LGTM` "
            "for this plan's exact SHA-256 before substantive mutation.",
            "",
        )
    )
    return "\n".join(body)


def write_atomic(path: Path, content: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        rendered = render_plan(metadata)
    except (OSError, json.JSONDecodeError, PlanError) as error:
        parser.error(str(error))
    if args.output:
        write_atomic(args.output, rendered)
    else:
        print(rendered, end="")
    print(f"plan_sha256={hashlib.sha256(rendered.encode('utf-8')).hexdigest()}", file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
