#!/usr/bin/env python3
"""Render a strict, reusable Herdr task brief from JSON metadata.

The renderer intentionally has no third-party dependencies.  Profiles contain
only role-specific defaults and fields; the lifecycle and safety contract stays
in one core template so that it cannot drift between roles.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from string import Template
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = PACKAGE_ROOT / "templates" / "core.md.tmpl"
DEFAULT_PROFILES = PACKAGE_ROOT / "profiles"

CORE_REQUIRED = (
    "task_id",
    "profile",
    "objective",
    "workspace",
    "role",
    "sources",
    "scope",
    "exclusions",
    "allowed_mutations",
    "checks",
)
DEFAULTABLE_FIELDS = ("artifact_path", "completion_marker", "handoff_target")
OPTIONAL_FIELDS = ("notes", "acceptance", "progress_timing")
ALLOWED_TOP_LEVEL = frozenset(
    CORE_REQUIRED
    + DEFAULTABLE_FIELDS
    + OPTIONAL_FIELDS
    + ("profile_fields",)
)
ALLOWED_WORKSPACE_FIELDS = frozenset(("repo", "cwd"))

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
MARKER_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
PLACEHOLDER_RE = re.compile(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*")

# These patterns are deliberately conservative: they catch recognizable
# credential forms without rejecting ordinary prose that merely mentions a
# secret or token.
CREDENTIAL_PATTERNS = (
    ("PEM private key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
            r"client[_-]?secret|password|passwd|secret)\b\s*[:=]\s*"
            r"[\"']?[A-Za-z0-9_./+=-]{8,}"
        ),
    ),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI-like key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "JWT",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "URL credentials",
        re.compile(r"\b(?:https?|ssh)://[^/\s:@]+:[^@\s]+@"),
    ),
)


class RenderError(ValueError):
    """Raised when metadata cannot be rendered safely and deterministically."""


def _error(message: str) -> RenderError:
    return RenderError(message)


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(f"{field} must be a non-empty string")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise _error(f"{field} must be a single line without control characters")
    return value.strip()


def _string_list(value: Any, field: str, *, required: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise _error(f"{field} must be a list of strings")
    if required and not value:
        raise _error(f"{field} must not be empty")
    result = []
    for index, item in enumerate(value):
        result.append(_require_text(item, f"{field}[{index}]"))
    return result


def _validate_no_credentials(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=True, sort_keys=True)
    for label, pattern in CREDENTIAL_PATTERNS:
        if pattern.search(serialized):
            raise _error(f"credential-like content detected ({label})")


def _validate_task_id(value: Any) -> str:
    task_id = _require_text(value, "task_id")
    if task_id in {".", ".."} or not TASK_ID_RE.fullmatch(task_id):
        raise _error("task_id must be a path-safe identifier using letters, digits, '.', '_' or '-'")
    return task_id


def _validate_relative_path(value: Any, field: str, *, allow_task_placeholder: bool = False) -> str:
    path = _require_text(value, field)
    if "\\" in path or path.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", path):
        raise _error(f"{field} must be a relative portable path")
    if allow_task_placeholder:
        path_for_check = path.replace("${task_id}", "task-id")
        if "${" in path_for_check or "$" in path_for_check:
            raise _error(f"{field} contains an unknown placeholder")
    elif "$" in path:
        raise _error(f"{field} must not contain placeholders")
    parts = path_for_check.split("/") if allow_task_placeholder else path.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _error(f"{field} contains an invalid path segment")
    return path


def _validate_target(value: Any) -> str:
    target = _require_text(value, "handoff_target")
    if not TARGET_RE.fullmatch(target):
        raise _error("handoff_target must be a stable agent name or pane id")
    return target


def _validate_marker(value: Any) -> str:
    marker = _require_text(value, "completion_marker")
    if not MARKER_RE.fullmatch(marker):
        raise _error("completion_marker must be an uppercase marker such as WRITER_COMPLETE")
    return marker


def _validate_profile_definition(profile: dict[str, Any], source: Path) -> dict[str, Any]:
    _validate_no_credentials(profile)
    required = profile.get("required_fields")
    optional = profile.get("optional_fields", [])
    labels = profile.get("field_labels")
    field_types = profile.get("field_types")
    if not isinstance(profile.get("name"), str) or not profile["name"]:
        raise _error(f"{source} has no valid name")
    if not isinstance(profile.get("role"), str) or not profile["role"]:
        raise _error(f"{source} has no valid role")
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise _error(f"{source} has invalid required_fields")
    if not isinstance(optional, list) or any(not isinstance(item, str) for item in optional):
        raise _error(f"{source} has invalid optional_fields")
    if set(required) & set(optional):
        raise _error(f"{source} repeats a profile field in required and optional fields")
    if not isinstance(labels, dict) or not isinstance(field_types, dict):
        raise _error(f"{source} must define field_labels and field_types")
    declared = set(required) | set(optional)
    if set(labels) != declared or set(field_types) != declared:
        raise _error(f"{source} field labels/types must exactly match declared fields")
    for field_name, field_type in field_types.items():
        if field_type not in {"text", "list"}:
            raise _error(f"{source} has unsupported type for profile field {field_name}")
    _require_text(profile.get("instructions"), f"{source}.instructions")
    defaults = profile.get("defaults")
    if not isinstance(defaults, dict):
        raise _error(f"{source} must define defaults")
    for field in ("artifact_path", "completion_marker", "handoff_target"):
        if field not in defaults:
            raise _error(f"{source}.defaults is missing {field}")
    return profile


def _load_profile(profile_name: str, profiles_dir: Path) -> dict[str, Any]:
    profile_path = profiles_dir / f"{profile_name}.json"
    if not profile_path.is_file():
        raise _error(f"unknown profile: {profile_name}")
    try:
        with profile_path.open("r", encoding="utf-8") as handle:
            profile = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise _error(f"cannot read profile {profile_name}: {exc}") from exc
    if not isinstance(profile, dict):
        raise _error(f"profile {profile_name} must be a JSON object")
    validated = _validate_profile_definition(profile, profile_path)
    if validated["name"] != profile_name:
        raise _error(f"profile filename and name disagree: {profile_name}")
    return validated


def _validate_profile_fields(metadata: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    fields = metadata.get("profile_fields", {})
    if not isinstance(fields, dict):
        raise _error("profile_fields must be an object")
    required = profile["required_fields"]
    optional = profile["optional_fields"]
    declared = set(required) | set(optional)
    unknown = sorted(set(fields) - declared)
    if unknown:
        raise _error(f"unknown profile field(s): {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    for field_name in required:
        if field_name not in fields:
            raise _error(f"missing required profile field: profile_fields.{field_name}")
    for field_name, value in fields.items():
        field_type = profile["field_types"][field_name]
        if field_type == "text":
            normalized[field_name] = _require_text(value, f"profile_fields.{field_name}")
        else:
            normalized[field_name] = _string_list(value, f"profile_fields.{field_name}")
    return normalized


def _format_list(values: list[str], *, empty: str = "- None provided.") -> str:
    if not values:
        return empty
    return "\n".join(f"- {value}" for value in values)


def _format_profile_fields(fields: dict[str, Any], profile: dict[str, Any]) -> str:
    sections: list[str] = []
    ordered = profile["required_fields"] + profile["optional_fields"]
    for field_name in ordered:
        if field_name not in fields:
            continue
        label = profile["field_labels"][field_name]
        value = fields[field_name]
        if isinstance(value, list):
            rendered = _format_list(value)
        else:
            rendered = value
        sections.append(f"### {label}\n{rendered}")
    return "\n\n".join(sections)


def _format_optional(value: Any, field: str) -> str:
    if value is None:
        return "- None provided."
    if isinstance(value, list):
        return _format_list(_string_list(value, field, required=False))
    return _require_text(value, field)


def _validate_metadata(metadata: Any, profiles_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(metadata, dict):
        raise _error("metadata must be a JSON object")
    _validate_no_credentials(metadata)
    unknown = sorted(set(metadata) - ALLOWED_TOP_LEVEL)
    if unknown:
        raise _error(f"unknown metadata field(s): {', '.join(unknown)}")
    missing = [field for field in CORE_REQUIRED if field not in metadata]
    if missing:
        raise _error(f"missing required metadata field(s): {', '.join(missing)}")

    normalized = dict(metadata)
    normalized["task_id"] = _validate_task_id(metadata["task_id"])
    normalized["profile"] = _require_text(metadata["profile"], "profile")
    profile = _load_profile(normalized["profile"], profiles_dir)
    normalized["objective"] = _require_text(metadata["objective"], "objective")
    normalized["role"] = _require_text(metadata["role"], "role")
    if normalized["role"] != profile["role"]:
        raise _error(f"role must be {profile['role']} for profile {profile['name']}")

    workspace = metadata["workspace"]
    if not isinstance(workspace, dict):
        raise _error("workspace must be an object with repo and optional cwd")
    unknown_workspace = sorted(set(workspace) - ALLOWED_WORKSPACE_FIELDS)
    if unknown_workspace:
        raise _error(f"unknown workspace field(s): {', '.join(unknown_workspace)}")
    if "repo" not in workspace:
        raise _error("workspace.repo is required")
    normalized_workspace = {
        "repo": _require_text(workspace["repo"], "workspace.repo"),
        "cwd": _require_text(workspace.get("cwd", "repository root"), "workspace.cwd"),
    }
    normalized["workspace"] = normalized_workspace

    for field in ("sources", "scope", "exclusions", "allowed_mutations", "checks"):
        normalized[field] = _string_list(metadata[field], field)
    for index, scope_item in enumerate(normalized["scope"]):
        _validate_relative_path(scope_item, f"scope[{index}]")

    for field, default_key in (
        ("artifact_path", "artifact_path"),
        ("completion_marker", "completion_marker"),
        ("handoff_target", "handoff_target"),
    ):
        if field not in normalized:
            normalized[field] = profile["defaults"][default_key]
    normalized["artifact_path"] = _validate_relative_path(
        normalized["artifact_path"], "artifact_path", allow_task_placeholder=True
    )
    resolved_artifact = normalized["artifact_path"].replace("${task_id}", normalized["task_id"])
    _validate_relative_path(resolved_artifact, "artifact_path")
    normalized["artifact_path"] = resolved_artifact
    normalized["completion_marker"] = _validate_marker(normalized["completion_marker"])
    normalized["handoff_target"] = _validate_target(normalized["handoff_target"])

    normalized["profile_fields"] = _validate_profile_fields(normalized, profile)
    if "notes" in normalized:
        normalized["notes"] = _format_optional(normalized["notes"], "notes")
    else:
        normalized["notes"] = "- None provided."
    if "acceptance" in normalized:
        normalized["acceptance"] = _format_optional(normalized["acceptance"], "acceptance")
    else:
        normalized["acceptance"] = "- Coordinator verifies the scoped diff and evidence before acceptance."
    normalized["progress_timing"] = _require_text(
        normalized.get(
            "progress_timing",
            "Report the first substantive milestone within five minutes and meaningful milestones thereafter.",
        ),
        "progress_timing",
    )
    return normalized, profile


def render_brief(
    metadata: dict[str, Any],
    *,
    template_path: Path | None = None,
    profiles_dir: Path | None = None,
) -> str:
    """Return a rendered brief or raise RenderError on any strict failure."""

    template_path = template_path or DEFAULT_TEMPLATE
    profiles_dir = profiles_dir or DEFAULT_PROFILES
    template_path = Path(template_path)
    profiles_dir = Path(profiles_dir)
    normalized, profile = _validate_metadata(metadata, profiles_dir)
    try:
        template_text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _error(f"cannot read template: {exc}") from exc

    values = {
        "task_id": normalized["task_id"],
        "profile": normalized["profile"],
        "objective": normalized["objective"],
        "role": normalized["role"],
        "workspace_repo": normalized["workspace"]["repo"],
        "workspace_cwd": normalized["workspace"]["cwd"],
        "sources_block": _format_list(normalized["sources"]),
        "scope_block": _format_list(normalized["scope"]),
        "exclusions_block": _format_list(normalized["exclusions"]),
        "allowed_mutations_block": _format_list(normalized["allowed_mutations"]),
        "checks_block": _format_list(normalized["checks"]),
        "artifact_path": normalized["artifact_path"],
        "completion_marker": normalized["completion_marker"],
        "handoff_target": normalized["handoff_target"],
        "profile_instructions": profile["instructions"],
        "profile_fields_block": _format_profile_fields(normalized["profile_fields"], profile),
        "notes": normalized["notes"],
        "acceptance_block": normalized["acceptance"],
        "progress_timing": normalized["progress_timing"],
    }
    try:
        rendered = Template(template_text).substitute(values)
    except (KeyError, ValueError) as exc:
        raise _error(f"template placeholder failure: {exc}") from exc
    unresolved = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if unresolved:
        raise _error(f"unresolved placeholder(s): {', '.join(unresolved)}")
    _validate_no_credentials(rendered)
    return rendered.rstrip() + "\n"


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise _error(f"cannot read metadata: {exc}") from exc
    if not isinstance(metadata, dict):
        raise _error("metadata must be a JSON object")
    return metadata


def _write_atomic(path: Path, content: str) -> None:
    if path.exists() and path.is_dir():
        raise _error(f"output path is a directory: {path}")
    if not path.parent.is_dir():
        raise _error(f"output parent does not exist: {path.parent}")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, type=Path, help="JSON metadata file")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output", type=Path, help="write atomically to this path; default is stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rendered = render_brief(
            _load_metadata(args.metadata),
            template_path=args.template,
            profiles_dir=args.profiles_dir,
        )
        if args.output:
            _write_atomic(args.output, rendered)
        else:
            sys.stdout.write(rendered)
    except RenderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
