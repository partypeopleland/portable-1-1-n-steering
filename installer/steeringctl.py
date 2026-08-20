#!/usr/bin/env python3
"""Safe installer prototype for the portable 1:1:N steering bundle.

The installer has one canonical source: a release root whose exact file set,
SHA256SUMS, and externally pinned SHA256SUMS digest have all been verified.
Target writes use one descriptor-relative transaction.  There is deliberately
no pathname fallback: if the host cannot provide the required POSIX dir-fd
operations, planning and applying fail closed.
"""

from __future__ import annotations

import argparse
import difflib
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Iterable


MODULE_ID = "1-1-n"
RECEIPT_REL = ".steeringctl/1-1-n.json"
MANIFEST_SCHEMA_VERSION = 1
RECEIPT_SCHEMA_VERSION = 2
START_MARKER = "<!-- steeringctl:managed-module:1-1-n:start -->"
END_MARKER = "<!-- steeringctl:managed-module:1-1-n:end -->"
EXIT_OK = 0
EXIT_CONFLICT = 2
EXIT_USAGE = 64
DIFF_MAX_BYTES = 64 * 1024
DIFF_MAX_LINES = 240
DIFF_MAX_TOTAL_LINES = 1200

PORTABLE_PAYLOAD = (
    "AGENTS.md",
    "docs/agent/1-1-n/INDEX.md",
    "docs/agent/1-1-n/roles-and-gates.md",
    "docs/agent/1-1-n/lifecycle-and-handoff.md",
    "docs/agent/1-1-n/delivery-and-safety.md",
)
RELEASE_FILES = (
    "README.md",
    "modules/1-1-n/manifest.json",
    "modules/1-1-n/AGENTS.md",
    "modules/1-1-n/docs/agent/1-1-n/INDEX.md",
    "modules/1-1-n/docs/agent/1-1-n/roles-and-gates.md",
    "modules/1-1-n/docs/agent/1-1-n/lifecycle-and-handoff.md",
    "modules/1-1-n/docs/agent/1-1-n/delivery-and-safety.md",
    "installer/steeringctl.py",
    "tests/test_steeringctl.py",
    "docs/distribution.md",
    ".gitignore",
)
RELEASE_METADATA = "SHA256SUMS"


class SteeringError(Exception):
    """A bounded, user-actionable installer error."""

    exit_code = EXIT_CONFLICT


class BundleError(SteeringError):
    pass


class ConflictError(SteeringError):
    pass


class ApplyError(SteeringError):
    pass


class MissingPath(Exception):
    """An absent target parent or node during a read-only preflight."""


@dataclass(frozen=True)
class PayloadEntry:
    path: str
    sha256: str
    data: bytes


@dataclass(frozen=True)
class Bundle:
    root: Path
    module_root: Path
    manifest_path: Path
    manifest_sha256: str
    module_id: str
    version: str
    payload: tuple[PayloadEntry, ...]
    managed_block: bytes
    release_sha256: str | None

    @property
    def payload_digests(self) -> dict[str, str]:
        return {entry.path: entry.sha256 for entry in self.payload}

    @property
    def non_root_payload(self) -> tuple[PayloadEntry, ...]:
        return tuple(entry for entry in self.payload if entry.path != "AGENTS.md")

    def data_for(self, rel: str) -> bytes:
        for entry in self.payload:
            if entry.path == rel:
                return entry.data
        raise KeyError(rel)

    @property
    def identity(self) -> tuple[str, str, str, str, tuple[tuple[str, str], ...]]:
        return (
            self.module_id,
            self.version,
            self.release_sha256 or "",
            self.manifest_sha256,
            tuple(sorted(self.payload_digests.items())),
        )


@dataclass(frozen=True)
class NodeSnapshot:
    exists: bool
    data: bytes = b""
    mode: int = 0o644


@dataclass(frozen=True)
class FileWrite:
    rel: str
    data: bytes
    mode: int


@dataclass(frozen=True)
class Plan:
    action: str
    module_id: str
    version: str
    target: Path
    writes: tuple[FileWrite, ...] = ()
    deletes: tuple[str, ...] = ()
    preconditions: tuple[tuple[str, NodeSnapshot], ...] = ()
    no_op: bool = False

    def _before(self) -> dict[str, NodeSnapshot]:
        return dict(self.preconditions)

    def _after(self) -> dict[str, bytes | None]:
        result: dict[str, bytes | None] = {
            rel: snapshot.data if snapshot.exists else None
            for rel, snapshot in self.preconditions
        }
        for item in self.writes:
            result[item.rel] = item.data
        for rel in self.deletes:
            result[rel] = None
        return result

    def preview(self) -> str:
        lines = [
            f"action={self.action}",
            f"module={self.module_id}",
            f"version={self.version}",
            f"target={self.target}",
            "mode=preview",
        ]
        if self.no_op:
            lines.append("result=already-installed")
            return "\n".join(lines)
        before = self._before()
        after = self._after()
        changed = sorted(rel for rel in set(before) | set(after) if _before_bytes(before.get(rel)) != after.get(rel))
        lines.append("diff-start")
        total = 0
        for rel in changed:
            diff_lines = _bounded_unified_diff(
                rel,
                _before_bytes(before.get(rel)),
                after.get(rel),
            )
            if total + len(diff_lines) > DIFF_MAX_TOTAL_LINES:
                lines.append("@@ bounded unified diff truncated @@")
                lines.append(f"  remaining_files={len(changed) - changed.index(rel)}")
                break
            lines.extend(diff_lines)
            total += len(diff_lines)
        if not changed:
            lines.append("(no content changes)")
        lines.append("diff-end")
        return "\n".join(lines)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_digest(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BundleError("manifest contains an unsafe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        raise BundleError("manifest contains an absolute or non-canonical path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError("manifest contains path traversal")
    if ":" in path.parts[0]:
        raise BundleError("manifest contains a drive-qualified path")
    return value


def _reject_symlink_tree(root: Path) -> None:
    if root.is_symlink():
        raise BundleError(f"symlink is not allowed: {root}")
    for directory, names, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in (*names, *files):
            candidate = directory_path / name
            if candidate.is_symlink():
                raise BundleError(f"symlink is not allowed: {candidate}")
            if candidate.is_file() and not stat.S_ISREG(candidate.stat().st_mode):
                raise BundleError(f"non-regular release file is not allowed: {candidate}")


def _release_dirs() -> set[str]:
    result: set[str] = set()
    for rel in (*RELEASE_FILES, RELEASE_METADATA):
        parts = PurePosixPath(rel).parts
        result.update("/".join(parts[:index]) for index in range(1, len(parts)))
    return result


def _is_repository_metadata(rel: str) -> bool:
    """Exclude the checkout's VCS metadata from the release file allowlist."""
    return rel == ".git" or rel.startswith(".git/")


def _release_snapshot(root: Path, trusted_sha256: str | None) -> dict[str, bytes]:
    if os.name != "posix":
        raise BundleError("this installer requires POSIX descriptor-relative filesystem support")
    candidate = Path(root).expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise BundleError("release root must be an existing, non-symlink directory")
    root = candidate.resolve()
    _reject_symlink_tree(root)
    actual_files = {
        rel
        for path in root.rglob("*")
        if path.is_file()
        for rel in (path.relative_to(root).as_posix(),)
        if not _is_repository_metadata(rel)
    }
    expected_files = set(RELEASE_FILES) | {RELEASE_METADATA}
    if actual_files != expected_files:
        extras = sorted(actual_files - expected_files)
        missing = sorted(expected_files - actual_files)
        raise BundleError(f"release file set mismatch; extras={extras}, missing={missing}")
    actual_dirs = {
        rel
        for path in root.rglob("*")
        if path.is_dir()
        for rel in (path.relative_to(root).as_posix(),)
        if not _is_repository_metadata(rel)
    }
    unexpected_dirs = sorted(actual_dirs - _release_dirs())
    if unexpected_dirs:
        raise BundleError(f"release directory set mismatch; extras={unexpected_dirs}")
    files = {rel: (root / rel).read_bytes() for rel in sorted(expected_files)}
    if trusted_sha256 is None:
        return files
    if not _is_digest(trusted_sha256):
        raise BundleError("trusted release SHA-256 must be 64 hexadecimal characters")
    sums = files[RELEASE_METADATA]
    if _sha256(sums) != trusted_sha256:
        raise BundleError("trusted release SHA256SUMS digest does not match")
    try:
        text = sums.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BundleError("SHA256SUMS is not valid UTF-8") from error
    checks: dict[str, str] = {}
    for line in text.splitlines():
        if not line or "  " not in line:
            raise BundleError("SHA256SUMS contains an invalid line")
        digest, rel = line.split("  ", 1)
        _safe_relative(rel)
        if rel in checks or not _is_digest(digest):
            raise BundleError("SHA256SUMS contains a duplicate or invalid entry")
        checks[rel] = digest
    if set(checks) != set(RELEASE_FILES):
        extras = sorted(set(checks) - set(RELEASE_FILES))
        missing = sorted(set(RELEASE_FILES) - set(checks))
        raise BundleError(f"SHA256SUMS allowlist mismatch; extras={extras}, missing={missing}")
    for rel, expected in checks.items():
        if _sha256(files[rel]) != expected:
            raise BundleError(f"release checksum mismatch: {rel}")
    return files


def _extract_managed_block(text: str) -> str:
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise BundleError("AGENTS.md must contain exactly one steeringctl managed block")
    start = text.index(START_MARKER)
    end = text.index(END_MARKER)
    if end < start:
        raise BundleError("AGENTS.md managed markers are out of order")
    return text[start : end + len(END_MARKER)]


def _replace_managed_block(text: str, block: str) -> str:
    starts = text.count(START_MARKER)
    ends = text.count(END_MARKER)
    if starts == 0 and ends == 0:
        separator = "" if not text or text.endswith("\n") else "\n"
        return f"{text}{separator}{block}\n"
    if starts != 1 or ends != 1:
        raise ConflictError("AGENTS.md has a partial or duplicated managed block")
    start = text.index(START_MARKER)
    end = text.index(END_MARKER)
    if end < start:
        raise ConflictError("AGENTS.md managed markers are out of order")
    return f"{text[:start]}{block}{text[end + len(END_MARKER):]}"


def _remove_managed_block(text: str) -> str:
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise ConflictError("AGENTS.md managed block is missing or ambiguous")
    start = text.index(START_MARKER)
    end = text.index(END_MARKER)
    if end < start:
        raise ConflictError("AGENTS.md managed markers are out of order")
    before = text[:start]
    after = text[end + len(END_MARKER) :]
    if before.endswith("\n") and after.startswith("\n"):
        after = after[1:]
    return before + after


def load_bundle(
    bundle_root: Path | None = None,
    module_id: str = MODULE_ID,
    trusted_release_sha256: str | None = None,
) -> Bundle:
    root = (bundle_root or Path(__file__).resolve().parents[1]).expanduser()
    files = _release_snapshot(root, trusted_release_sha256)
    root = root.resolve()
    manifest_rel = f"modules/{module_id}/manifest.json"
    manifest_bytes = files.get(manifest_rel)
    if manifest_bytes is None:
        raise BundleError("bundle manifest is missing")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError("bundle manifest is not valid UTF-8 JSON") from error
    if not isinstance(manifest, dict):
        raise BundleError("bundle manifest must be an object")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BundleError("unsupported bundle manifest schema")
    if manifest.get("module_id") != module_id:
        raise BundleError("bundle module id does not match requested module")
    version = manifest.get("version")
    if not isinstance(version, str) or not version or any(ch.isspace() for ch in version):
        raise BundleError("bundle version is invalid")
    raw_payload = manifest.get("payload")
    if not isinstance(raw_payload, list) or not raw_payload:
        raise BundleError("bundle payload is missing")
    entries: list[PayloadEntry] = []
    for raw_entry in raw_payload:
        if not isinstance(raw_entry, dict):
            raise BundleError("bundle payload entry is invalid")
        rel = _safe_relative(raw_entry.get("path"))
        digest = raw_entry.get("sha256")
        if not _is_digest(digest):
            raise BundleError(f"bundle digest is invalid: {rel}")
        source_rel = f"modules/{module_id}/{rel}"
        data = files.get(source_rel)
        if data is None:
            raise BundleError(f"bundle file is missing: {rel}")
        if _sha256(data) != digest:
            raise BundleError(f"bundle payload digest mismatch: {rel}")
        entries.append(PayloadEntry(rel, digest, data))
    paths = [entry.path for entry in entries]
    if len(paths) != len(set(paths)) or set(paths) != set(PORTABLE_PAYLOAD):
        raise BundleError("bundle payload is not the exact 1:1:N manifest")
    try:
        managed_block = _extract_managed_block(next(entry.data for entry in entries if entry.path == "AGENTS.md").decode("utf-8"))
    except (StopIteration, UnicodeDecodeError) as error:
        raise BundleError("bundle AGENTS.md is not valid UTF-8") from error
    return Bundle(
        root=root,
        module_root=root / "modules" / module_id,
        manifest_path=root / manifest_rel,
        manifest_sha256=_sha256(manifest_bytes),
        module_id=module_id,
        version=version,
        payload=tuple(sorted(entries, key=lambda entry: entry.path)),
        managed_block=managed_block.encode("utf-8"),
        release_sha256=trusted_release_sha256,
    )


def _require_plan_trust(bundle: Bundle) -> None:
    if bundle.release_sha256 is None:
        raise BundleError("trusted release checksum is required before planning or applying")


def _validate_target(value: str) -> Path:
    target = Path(value).expanduser()
    if not target.is_absolute():
        raise ConflictError("target must be an absolute workspace path")
    try:
        info = target.lstat()
    except OSError as error:
        raise ConflictError("target must be an existing workspace directory") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ConflictError("target must be an existing, non-symlink directory")
    return target.resolve()


def _require_dirfd_capabilities() -> None:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise ConflictError("descriptor-relative POSIX filesystem capabilities are unavailable; refusing to write")
    supported = getattr(os, "supports_dir_fd", set())
    # CPython exposes os.replace(src_dir_fd=..., dst_dir_fd=...) on POSIX,
    # while some versions omit the wrapper from supports_dir_fd.  os.rename
    # is the capability probe for the same underlying renameat operation.
    required = (os.open, os.stat, os.mkdir, os.rename, os.unlink, os.rmdir)
    if any(operation not in supported for operation in required):
        raise ConflictError("required dir-fd filesystem operations are unavailable; refusing to write")


@dataclass
class _DirRef:
    fd: int
    dev: int
    ino: int
    rel: tuple[str, ...]
    parent: "_DirRef | None" = None
    name: str | None = None

    def assert_inode(self) -> None:
        current = os.fstat(self.fd)
        if (current.st_dev, current.st_ino) != (self.dev, self.ino) or not stat.S_ISDIR(current.st_mode):
            raise ConflictError("target directory inode changed; refusing to continue")

    def assert_stable(self) -> None:
        self.assert_inode()
        if self.parent is not None and self.name is not None:
            self.parent.assert_stable()
            try:
                linked = os.stat(self.name, dir_fd=self.parent.fd, follow_symlinks=False)
            except OSError as error:
                raise ConflictError("target directory binding disappeared; refusing to continue") from error
            if (linked.st_dev, linked.st_ino) != (self.dev, self.ino) or not stat.S_ISDIR(linked.st_mode):
                raise ConflictError("target directory binding changed; refusing to continue")


@dataclass(frozen=True)
class _CreatedDir:
    parent: _DirRef
    name: str
    child: _DirRef


class _TargetTree:
    def __init__(self, target: Path) -> None:
        _require_dirfd_capabilities()
        before = target.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
            raise ConflictError("target must be an existing, non-symlink directory")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(str(target), flags)
        except OSError as error:
            raise ConflictError("could not open workspace directory safely") from error
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            os.close(fd)
            raise ConflictError("workspace directory changed while opening; refusing to write")
        self.target = target
        self.root = _DirRef(fd, after.st_dev, after.st_ino, ())
        self._dirs: dict[tuple[str, ...], _DirRef] = {(): self.root}
        self.created: list[_CreatedDir] = []

    def __enter__(self) -> "_TargetTree":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        for rel, directory in sorted(self._dirs.items(), key=lambda item: len(item[0]), reverse=True):
            if rel:
                try:
                    os.close(directory.fd)
                except OSError:
                    pass
        try:
            os.close(self.root.fd)
        except OSError:
            pass

    def parent_for(self, rel: str, *, create: bool) -> tuple[_DirRef, str] | None:
        _safe_relative(rel)
        parts = PurePosixPath(rel).parts
        parent_parts = tuple(parts[:-1])
        current = self._dirs[()]
        for index, part in enumerate(parent_parts, start=1):
            current_parts = tuple(parent_parts[:index])
            cached = self._dirs.get(current_parts)
            if cached is not None:
                cached.assert_stable()
                current = cached
                continue
            current.assert_stable()
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            made = False
            try:
                fd = os.open(part, flags, dir_fd=current.fd)
            except FileNotFoundError:
                if not create:
                    return None
                try:
                    os.mkdir(part, 0o755, dir_fd=current.fd)
                    made = True
                except FileExistsError:
                    pass
                fd = os.open(part, flags, dir_fd=current.fd)
            except OSError as error:
                raise ConflictError(f"target parent is not a safe directory: {rel}") from error
            child_stat = os.fstat(fd)
            if not stat.S_ISDIR(child_stat.st_mode):
                os.close(fd)
                raise ConflictError(f"target parent is not a directory: {rel}")
            child = _DirRef(fd, child_stat.st_dev, child_stat.st_ino, current_parts, current, part)
            child.assert_stable()
            self._dirs[current_parts] = child
            if made:
                self.created.append(_CreatedDir(current, part, child))
            current = child
        return current, parts[-1]


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _read_node(tree: _TargetTree, rel: str, *, required: bool) -> NodeSnapshot | None:
    reference = tree.parent_for(rel, create=False)
    if reference is None:
        if required:
            raise ConflictError(f"target path is missing: {rel}")
        return None
    parent, name = reference
    parent.assert_stable()
    try:
        info = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        if required:
            raise ConflictError(f"target path is missing: {rel}")
        return None
    except OSError as error:
        raise ConflictError(f"could not inspect target path: {rel}") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ConflictError(f"target path is not a regular file: {rel}")
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, dir_fd=parent.fd)
    except OSError as error:
        raise ConflictError(f"could not open target file safely: {rel}") from error
    try:
        current = os.fstat(fd)
        if not _same_inode(info, current):
            raise ConflictError(f"target file changed while reading: {rel}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return NodeSnapshot(True, b"".join(chunks), stat.S_IMODE(current.st_mode))
    finally:
        os.close(fd)


def _receipt_from_bytes(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConflictError("receipt is not valid UTF-8 JSON") from error
    expected = {
        "schema_version",
        "module_id",
        "version",
        "release_sha256",
        "manifest_sha256",
        "source_payload_sha256",
        "payload_sha256",
        "root_created",
        "root_managed_block_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ConflictError("receipt fields are invalid")
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION or value.get("module_id") != MODULE_ID:
        raise ConflictError("receipt schema or module id is invalid")
    for key in ("release_sha256", "manifest_sha256", "root_managed_block_sha256"):
        if not _is_digest(value.get(key)):
            raise ConflictError(f"receipt {key} is invalid")
    if not isinstance(value.get("version"), str) or not value["version"]:
        raise ConflictError("receipt version is invalid")
    for key in ("source_payload_sha256", "payload_sha256"):
        mapping = value.get(key)
        if not isinstance(mapping, dict):
            raise ConflictError(f"receipt {key} is invalid")
        for rel, digest in mapping.items():
            try:
                _safe_relative(rel)
            except BundleError as error:
                raise ConflictError(f"receipt path is invalid: {rel}") from error
            if not _is_digest(digest):
                raise ConflictError(f"receipt digest is invalid: {rel}")
    if not isinstance(value.get("root_created"), bool):
        raise ConflictError("receipt root ownership flag is invalid")
    return value


def _load_receipt(tree: _TargetTree) -> tuple[dict[str, Any], bytes] | None:
    node = _read_node(tree, RECEIPT_REL, required=False)
    if node is None:
        return None
    value = _receipt_from_bytes(node.data)
    return value, node.data


def _verify_installed(bundle: Bundle, tree: _TargetTree) -> dict[str, Any]:
    _require_plan_trust(bundle)
    loaded = _load_receipt(tree)
    if loaded is None:
        raise ConflictError("module receipt is missing")
    receipt, _data = loaded
    expected_payload = bundle.payload_digests
    expected_non_root = {entry.path: entry.sha256 for entry in bundle.non_root_payload}
    if (
        receipt["module_id"] != bundle.module_id
        or receipt["version"] != bundle.version
        or receipt["release_sha256"] != bundle.release_sha256
        or receipt["manifest_sha256"] != bundle.manifest_sha256
        or receipt["source_payload_sha256"] != expected_payload
        or receipt["payload_sha256"] != expected_non_root
        or receipt["root_managed_block_sha256"] != _sha256(bundle.managed_block)
    ):
        raise ConflictError("receipt is not authorized by the trusted release manifest")
    root = _read_node(tree, "AGENTS.md", required=True)
    assert root is not None
    try:
        block = _extract_managed_block(root.data.decode("utf-8"))
    except (UnicodeDecodeError, BundleError) as error:
        raise ConflictError("target AGENTS.md managed block is invalid") from error
    if block.encode("utf-8") != bundle.managed_block:
        raise ConflictError("target AGENTS.md managed block changed after installation")
    for entry in bundle.non_root_payload:
        node = _read_node(tree, entry.path, required=True)
        assert node is not None
        if _sha256(node.data) != entry.sha256:
            raise ConflictError(f"managed file changed after installation: {entry.path}")
    return receipt


def _make_receipt(bundle: Bundle, *, root_created: bool) -> bytes:
    _require_plan_trust(bundle)
    value = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "module_id": bundle.module_id,
        "version": bundle.version,
        "release_sha256": bundle.release_sha256,
        "manifest_sha256": bundle.manifest_sha256,
        "source_payload_sha256": bundle.payload_digests,
        "payload_sha256": {entry.path: entry.sha256 for entry in bundle.non_root_payload},
        "root_created": root_created,
        "root_managed_block_sha256": _sha256(bundle.managed_block),
    }
    return _json_bytes(value)


def _preconditions_for(tree: _TargetTree, paths: Iterable[str]) -> tuple[tuple[str, NodeSnapshot], ...]:
    result: list[tuple[str, NodeSnapshot]] = []
    for rel in sorted(set(paths)):
        node = _read_node(tree, rel, required=False)
        result.append((rel, node or NodeSnapshot(False)))
    return tuple(result)


def _prepare_install(bundle: Bundle, target: Path, installed_bundle: Bundle | None) -> Plan:
    _require_plan_trust(bundle)
    with _TargetTree(target) as tree:
        loaded = _load_receipt(tree)
        if loaded is not None:
            if installed_bundle is None:
                raise ConflictError("a trusted manifest for the installed release is required")
            receipt = _verify_installed(installed_bundle, tree)
            if installed_bundle.identity == bundle.identity and receipt["version"] == bundle.version:
                preconditions = _preconditions_for(tree, ["AGENTS.md", RECEIPT_REL, *PORTABLE_PAYLOAD[1:]])
                return Plan("install", bundle.module_id, bundle.version, target, preconditions=preconditions, no_op=True)
            raise ConflictError("module is installed; use update for a newer bundle")
        before_root = _read_node(tree, "AGENTS.md", required=False)
        root_created = before_root is None
        if root_created:
            root_data = bundle.data_for("AGENTS.md")
            root_mode = 0o644
        else:
            assert before_root is not None
            current_text = _decode_utf8(before_root.data, "target AGENTS.md")
            if START_MARKER in current_text or END_MARKER in current_text:
                raise ConflictError("target AGENTS.md already has an unowned steeringctl block")
            root_data = _replace_managed_block(current_text, bundle.managed_block.decode("utf-8")).encode("utf-8")
            root_mode = before_root.mode
        before_paths = ["AGENTS.md", RECEIPT_REL, *[entry.path for entry in bundle.non_root_payload]]
        for entry in bundle.non_root_payload:
            if _read_node(tree, entry.path, required=False) is not None:
                raise ConflictError(f"unmanaged target path already exists: {entry.path}")
        writes = [FileWrite("AGENTS.md", root_data, root_mode)]
        writes.extend(FileWrite(entry.path, entry.data, 0o644) for entry in bundle.non_root_payload)
        writes.append(FileWrite(RECEIPT_REL, _make_receipt(bundle, root_created=root_created), 0o600))
        return Plan(
            "install", bundle.module_id, bundle.version, target, tuple(writes),
            preconditions=_preconditions_for(tree, before_paths),
        )


def _prepare_update(bundle: Bundle, target: Path, installed_bundle: Bundle | None) -> Plan:
    _require_plan_trust(bundle)
    with _TargetTree(target) as tree:
        if installed_bundle is None:
            raise ConflictError("a trusted manifest for the installed release is required")
        receipt = _verify_installed(installed_bundle, tree)
        current_root = _read_node(tree, "AGENTS.md", required=True)
        assert current_root is not None
        root_data = _replace_managed_block(
            _decode_utf8(current_root.data, "target AGENTS.md"), bundle.managed_block.decode("utf-8")
        ).encode("utf-8")
        before_paths = ["AGENTS.md", RECEIPT_REL, *[entry.path for entry in bundle.non_root_payload]]
        writes = [FileWrite("AGENTS.md", root_data, current_root.mode)]
        writes.extend(FileWrite(entry.path, entry.data, 0o644) for entry in bundle.non_root_payload)
        writes.append(FileWrite(RECEIPT_REL, _make_receipt(bundle, root_created=bool(receipt["root_created"])), 0o600))
        return Plan(
            "update", bundle.module_id, bundle.version, target, tuple(writes),
            preconditions=_preconditions_for(tree, before_paths),
        )


def _prepare_uninstall(bundle: Bundle, target: Path, installed_bundle: Bundle | None) -> Plan:
    _require_plan_trust(bundle)
    with _TargetTree(target) as tree:
        if installed_bundle is None:
            raise ConflictError("a trusted manifest for the installed release is required")
        _verify_installed(installed_bundle, tree)
        current_root = _read_node(tree, "AGENTS.md", required=True)
        assert current_root is not None
        before_paths = ["AGENTS.md", RECEIPT_REL, *[entry.path for entry in installed_bundle.non_root_payload]]
        writes: list[FileWrite] = []
        deletes = [entry.path for entry in installed_bundle.non_root_payload]
        root_data = _remove_managed_block(_decode_utf8(current_root.data, "target AGENTS.md")).encode("utf-8")
        writes.append(FileWrite("AGENTS.md", root_data, current_root.mode))
        deletes.append(RECEIPT_REL)
        return Plan(
            "uninstall", bundle.module_id, bundle.version, target, tuple(writes), tuple(sorted(deletes)),
            preconditions=_preconditions_for(tree, before_paths),
        )


def build_plan(
    action: str,
    bundle: Bundle,
    target: Path,
    installed_bundle: Bundle | None = None,
) -> Plan:
    _require_plan_trust(bundle)
    if action == "install":
        return _prepare_install(bundle, target, installed_bundle)
    if action == "update":
        return _prepare_update(bundle, target, installed_bundle)
    if action == "uninstall":
        return _prepare_uninstall(bundle, target, installed_bundle)
    raise SteeringError(f"unsupported action: {action}")


def _decode_utf8(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConflictError(f"{label} is not valid UTF-8") from error


def _before_bytes(snapshot: NodeSnapshot | None) -> bytes | None:
    return None if snapshot is None or not snapshot.exists else snapshot.data


def _digest_summary(label: str, data: bytes | None) -> str:
    if data is None:
        return f"{label}=absent"
    return f"{label}=sha256:{_sha256(data)} bytes:{len(data)}"


def _bounded_unified_diff(rel: str, before: bytes | None, after: bytes | None) -> list[str]:
    if before == after:
        return []
    if (
        before is None or after is None
        or len(before) > DIFF_MAX_BYTES
        or len(after) > DIFF_MAX_BYTES
    ):
        return [
            f"--- {'/dev/null' if before is None else 'a/' + rel}",
            f"+++ {'/dev/null' if after is None else 'b/' + rel}",
            "@@ bounded diff summary @@",
            f"  {_digest_summary('before', before)}",
            f"  {_digest_summary('after', after)}",
        ]
    try:
        old = before.decode("utf-8") if before is not None else ""
        new = after.decode("utf-8") if after is not None else ""
    except UnicodeDecodeError:
        return [
            f"--- {'/dev/null' if before is None else 'a/' + rel}",
            f"+++ {'/dev/null' if after is None else 'b/' + rel}",
            "@@ binary diff summary @@",
            f"  {_digest_summary('before', before)}",
            f"  {_digest_summary('after', after)}",
        ]
    diff = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile="/dev/null" if before is None else f"a/{rel}",
        tofile="/dev/null" if after is None else f"b/{rel}",
        lineterm="",
        n=3,
    ))
    if len(diff) > DIFF_MAX_LINES:
        return [
            f"--- {'/dev/null' if before is None else 'a/' + rel}",
            f"+++ {'/dev/null' if after is None else 'b/' + rel}",
            "@@ bounded diff summary @@",
            f"  {_digest_summary('before', before)}",
            f"  {_digest_summary('after', after)}",
            f"  omitted_lines={len(diff)}",
        ]
    return diff


def _stat_at(parent: _DirRef, name: str, *, bound_only: bool = False) -> os.stat_result | None:
    (parent.assert_inode if bound_only else parent.assert_stable)()
    try:
        return os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ApplyError(f"could not inspect transaction path: {name}") from error


def _open_temp(parent: _DirRef, data: bytes, mode: int, *, bound_only: bool = False) -> str:
    (parent.assert_inode if bound_only else parent.assert_stable)()
    for _attempt in range(20):
        name = f".steeringctl-tmp-{os.getpid()}-{uuid.uuid4().hex}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(name, flags, mode, dir_fd=parent.fd)
        except FileExistsError:
            continue
        try:
            offset = 0
            while offset < len(data):
                offset += os.write(fd, data[offset:])
            os.fchmod(fd, mode)
            os.fsync(fd)
        except Exception:
            os.close(fd)
            try:
                os.unlink(name, dir_fd=parent.fd)
            except OSError:
                pass
            raise
        os.close(fd)
        try:
            (parent.assert_inode if bound_only else parent.assert_stable)()
        except Exception:
            try:
                os.unlink(name, dir_fd=parent.fd)
            except OSError:
                pass
            raise
        return name
    raise ApplyError("could not allocate a transaction temporary file")


def _replace_from_temp(parent: _DirRef, temporary: str, name: str, *, bound_only: bool = False) -> None:
    (parent.assert_inode if bound_only else parent.assert_stable)()
    os.replace(temporary, name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd)


def _sync_parent(parent: _DirRef, *, bound_only: bool = False) -> None:
    (parent.assert_inode if bound_only else parent.assert_stable)()
    os.fsync(parent.fd)


def _delete_file(parent: _DirRef, name: str, *, bound_only: bool = False) -> None:
    (parent.assert_inode if bound_only else parent.assert_stable)()
    info = _stat_at(parent, name, bound_only=bound_only)
    if info is None:
        raise ApplyError(f"transaction path is missing: {name}")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ApplyError(f"transaction path is not a regular file: {name}")
    os.unlink(name, dir_fd=parent.fd)


def _cleanup_temp(parent: _DirRef, name: str, *, bound_only: bool = False) -> None:
    (parent.assert_inode if bound_only else parent.assert_stable)()
    info = _stat_at(parent, name, bound_only=bound_only)
    if info is None:
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ApplyError(f"transaction temporary is not a regular file: {name}")
    os.unlink(name, dir_fd=parent.fd)
    _sync_parent(parent, bound_only=bound_only)


def _restore_snapshot(parent: _DirRef, name: str, snapshot: NodeSnapshot) -> None:
    parent.assert_inode()
    current = _stat_at(parent, name, bound_only=True)
    if not snapshot.exists:
        if current is not None:
            _delete_file(parent, name, bound_only=True)
        return
    temporary = _open_temp(parent, snapshot.data, snapshot.mode, bound_only=True)
    try:
        _replace_from_temp(parent, temporary, name, bound_only=True)
        _sync_parent(parent, bound_only=True)
        temporary = ""
    finally:
        if temporary:
            _cleanup_temp(parent, temporary, bound_only=True)


def _cleanup_created_dirs(tree: _TargetTree) -> None:
    for created in reversed(tree.created):
        created.parent.assert_inode()
        try:
            current = os.stat(created.name, dir_fd=created.parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        # If an adversary replaced the name, never delete the replacement.
        # The original directory remains reachable through its already-open
        # descriptor and its own descendants can still be cleaned safely.
        if not _same_inode(current, os.fstat(created.child.fd)) or not stat.S_ISDIR(current.st_mode):
            continue
        os.rmdir(created.name, dir_fd=created.parent.fd)
        created.parent.assert_inode()
        os.fsync(created.parent.fd)


def execute_plan(plan: Plan, *, failure_after: int | None = None) -> None:
    """Apply a plan using one target fd and descriptor-relative parents only."""
    _require_dirfd_capabilities()
    operations: list[tuple[str, FileWrite | str]] = []
    operations.extend(("write", item) for item in plan.writes)
    operations.extend(("delete", rel) for rel in plan.deletes)
    with _TargetTree(plan.target) as tree:
        # Check the exact bytes observed while building the plan before creating
        # any parent.  A user edit between preview and --yes is a conflict.
        for rel, expected in plan.preconditions:
            actual = _read_node(tree, rel, required=False) or NodeSnapshot(False)
            if actual.exists != expected.exists or (actual.exists and actual.data != expected.data):
                raise ConflictError(f"target changed after plan was built: {rel}")

        expected_by_rel = dict(plan.preconditions)
        references: dict[str, tuple[_DirRef, str]] = {}
        snapshots: dict[str, NodeSnapshot] = {}
        try:
            for kind, item in operations:
                rel = item.rel if kind == "write" else item
                assert isinstance(rel, str)
                reference = tree.parent_for(rel, create=(kind == "write"))
                if reference is None:
                    raise ConflictError(f"target parent is missing: {rel}")
                references[rel] = reference
                node = _read_node(tree, rel, required=False) or NodeSnapshot(False)
                expected = expected_by_rel.get(rel)
                if expected is not None and (
                    node.exists != expected.exists or (node.exists and node.data != expected.data)
                ):
                    raise ConflictError(f"target changed during transaction preflight: {rel}")
                snapshots[rel] = node
        except Exception as error:
            try:
                _cleanup_created_dirs(tree)
            except Exception as cleanup_error:
                raise ApplyError(f"preflight failed and parent rollback failed: {cleanup_error}") from error
            raise

        temporary_files: list[tuple[_DirRef, str]] = []
        applied: list[str] = []
        try:
            for kind, item in operations:
                if kind != "write":
                    continue
                assert isinstance(item, FileWrite)
                parent, _name = references[item.rel]
                temporary_files.append((parent, _open_temp(parent, item.data, item.mode)))
            temporary_by_rel = {
                item.rel: temporary
                for (kind, item), (_parent, temporary) in zip(
                    (operation for operation in operations if operation[0] == "write"), temporary_files
                )
                if kind == "write" and isinstance(item, FileWrite)
            }
            count = 0
            for kind, item in operations:
                if failure_after is not None and count >= failure_after:
                    raise ApplyError("injected apply failure")
                if kind == "write":
                    assert isinstance(item, FileWrite)
                    parent, name = references[item.rel]
                    temporary = temporary_by_rel[item.rel]
                    _replace_from_temp(parent, temporary, name)
                    temporary_by_rel[item.rel] = ""
                    applied.append(item.rel)
                    _sync_parent(parent)
                else:
                    assert isinstance(item, str)
                    parent, name = references[item]
                    _delete_file(parent, name)
                    applied.append(item)
                    _sync_parent(parent)
                count += 1
            for parent, temporary in temporary_files:
                if temporary:
                    _cleanup_temp(parent, temporary)
        except Exception as error:
            rollback_error: Exception | None = None
            try:
                for rel in reversed(applied):
                    parent, name = references[rel]
                    _restore_snapshot(parent, name, snapshots[rel])
                for parent, temporary in temporary_files:
                    if temporary:
                        _cleanup_temp(parent, temporary, bound_only=True)
                _cleanup_created_dirs(tree)
            except Exception as restore_error:
                rollback_error = restore_error
            if rollback_error is not None:
                raise ApplyError(f"apply failed and rollback failed: {rollback_error}") from error
            if isinstance(error, SteeringError):
                raise
            raise ApplyError(f"apply failed; rollback completed: {error}") from error


def _receipt_version_hint(target: Path) -> dict[str, Any] | None:
    with _TargetTree(target) as tree:
        loaded = _load_receipt(tree)
        return None if loaded is None else loaded[0]


def _select_installed_bundle(
    target: Path,
    current: Bundle,
    installed_release_root: str | None,
    installed_release_sha256: str | None,
) -> Bundle | None:
    receipt = _receipt_version_hint(target)
    if receipt is None:
        return None
    if receipt.get("module_id") != MODULE_ID:
        raise ConflictError("installed receipt module id is invalid")
    if (
        receipt.get("version") == current.version
        and receipt.get("release_sha256") == current.release_sha256
        and receipt.get("manifest_sha256") == current.manifest_sha256
    ):
        return current
    if not installed_release_root or not installed_release_sha256:
        raise ConflictError(
            f"trusted manifest for installed version {receipt.get('version', '<unknown>')} is required; "
            "provide --installed-release-root and --installed-release-sha256"
        )
    installed = load_bundle(Path(installed_release_root), trusted_release_sha256=installed_release_sha256)
    if installed.module_id != MODULE_ID or installed.version != receipt.get("version"):
        raise ConflictError("installed release does not match receipt version")
    return installed


def _doctor(current: Bundle, target: Path, installed: Bundle | None) -> tuple[int, dict[str, Any]]:
    if installed is None:
        return EXIT_OK, {"module_id": current.module_id, "status": "not-installed", "version": current.version}
    with _TargetTree(target) as tree:
        receipt = _verify_installed(installed, tree)
    same = installed.identity == current.identity
    result = {
        "module_id": current.module_id,
        "status": "installed" if same else "update-available",
        "version": receipt["version"],
        "available_version": current.version,
    }
    return (EXIT_OK if same else EXIT_CONFLICT), result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steeringctl.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "update", "uninstall"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("module_id")
        subparser.add_argument("--target", required=True)
        subparser.add_argument("--release-sha256")
        subparser.add_argument("--installed-release-root")
        subparser.add_argument("--installed-release-sha256")
        subparser.add_argument("--dry-run", action="store_true")
        subparser.add_argument("--yes", action="store_true")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("module_id")
    doctor.add_argument("--target", required=True)
    doctor.add_argument("--release-sha256")
    doctor.add_argument("--installed-release-root")
    doctor.add_argument("--installed-release-sha256")
    doctor.add_argument("--json", action="store_true")
    version = subparsers.add_parser("version")
    version.add_argument("module_id")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.module_id != MODULE_ID:
            raise SteeringError(f"unsupported module: {args.module_id}")
        if args.command == "version":
            bundle = load_bundle()
            print(f"{bundle.module_id} {bundle.version}")
            return EXIT_OK
        if not args.release_sha256:
            raise BundleError("--release-sha256 is required; verify the pinned release SHA256SUMS first")
        bundle = load_bundle(trusted_release_sha256=args.release_sha256)
        target = _validate_target(args.target)
        installed = _select_installed_bundle(
            target,
            bundle,
            getattr(args, "installed_release_root", None),
            getattr(args, "installed_release_sha256", None),
        )
        if args.command == "doctor":
            code, result = _doctor(bundle, target, installed)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            else:
                print(" ".join(f"{key}={result[key]}" for key in sorted(result)))
            return code
        if args.dry_run and args.yes:
            raise SteeringError("--dry-run and --yes cannot be combined")
        plan = build_plan(args.command, bundle, target, installed_bundle=installed)
        if plan.no_op:
            print(plan.preview())
            return EXIT_OK
        if not args.yes:
            print(plan.preview())
            print("preview-only; rerun with --yes to apply")
            return EXIT_OK
        execute_plan(plan)
        print(f"applied action={plan.action} module={plan.module_id} version={plan.version}")
        print("restart the Codex session, then run doctor")
        return EXIT_OK
    except SteeringError as error:
        print(f"error: {error}", file=sys.stderr)
        return error.exit_code
    except OSError as error:
        print(f"error: filesystem operation failed: {error}", file=sys.stderr)
        return EXIT_CONFLICT


if __name__ == "__main__":
    raise SystemExit(main())
