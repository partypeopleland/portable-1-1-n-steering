from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
STAGING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGING_ROOT / "installer"))
import steeringctl  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_digest(root: Path) -> str:
    return digest((root / "SHA256SUMS").read_bytes())


def refresh_release(root: Path, *, version: str | None = None) -> str:
    manifest_path = root / "modules/1-1-n/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if version is not None:
        manifest["version"] = version
    for entry in manifest["payload"]:
        source = root / "modules/1-1-n" / entry["path"]
        entry["sha256"] = digest(source.read_bytes())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        f"{digest((root / rel).read_bytes())}  {rel}\n"
        for rel in steeringctl.RELEASE_FILES
    ]
    (root / steeringctl.RELEASE_METADATA).write_text("".join(lines), encoding="utf-8")
    return release_digest(root)


def documented_dispatch_outcome(statuses: tuple[str, ...]) -> tuple[str, int]:
    """Small deterministic fixture for the documented bounded dispatch protocol."""
    if not statuses:
        return "dispatch_failed", 0
    if statuses[0] == "working":
        return "started", 0
    if len(statuses) >= 2 and statuses[1] == "working":
        return "started", 1
    return "dispatch_failed", 1


class SteeringCtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="steeringctl-test-")
        self.workspace = Path(self.tempdir.name) / "workspace"
        self.workspace.mkdir()
        self.release_sha = release_digest(STAGING_ROOT)
        self.bundle = steeringctl.load_bundle(STAGING_ROOT, trusted_release_sha256=self.release_sha)
        self.variant_index = 0

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, *args: str, release_sha: str | None = "default") -> tuple[int, str, str]:
        if release_sha == "default":
            args = (*args, "--release-sha256", self.release_sha)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = steeringctl.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def snapshot(self, root: Path | None = None) -> dict[str, bytes]:
        root = root or self.workspace
        result: dict[str, bytes] = {}
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                result[path.relative_to(root).as_posix()] = path.read_bytes()
        return result

    def install(self) -> None:
        code, _out, err = self.run_cli("install", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual((code, err), (0, ""))

    def copy_release(self) -> Path:
        self.variant_index += 1
        variant = Path(self.tempdir.name) / f"release-variant-{self.variant_index}"
        shutil.copytree(
            STAGING_ROOT,
            variant,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        return variant

    def load_variant(self, variant: Path, *, version: str | None = None) -> steeringctl.Bundle:
        trusted = refresh_release(variant, version=version)
        return steeringctl.load_bundle(variant, trusted_release_sha256=trusted)

    def test_preview_is_deterministic_bounded_unified_diff_and_writes_nothing(self) -> None:
        first = self.run_cli("install", "1-1-n", "--target", str(self.workspace))
        second = self.run_cli("install", "1-1-n", "--target", str(self.workspace))
        self.assertEqual(first, second)
        self.assertEqual(first[0], 0)
        self.assertIn("mode=preview", first[1])
        self.assertIn("diff-start", first[1])
        self.assertIn("--- /dev/null", first[1])
        self.assertIn("+++ b/AGENTS.md", first[1])
        self.assertIn("@@", first[1])
        self.assertIn("preview-only", first[1])
        self.assertLessEqual(len(first[1].splitlines()), steeringctl.DIFF_MAX_TOTAL_LINES + 20)
        self.assertEqual(self.snapshot(), {})

    def test_existing_update_uninstall_previews_have_literal_unified_diff(self) -> None:
        (self.workspace / "AGENTS.md").write_text("# user\n", encoding="utf-8")
        install_preview = self.run_cli("install", "1-1-n", "--target", str(self.workspace))[1]
        self.assertIn("--- a/AGENTS.md", install_preview)
        self.assertIn("+++ b/AGENTS.md", install_preview)
        self.install()
        variant = self.copy_release()
        changed = variant / "modules/1-1-n/docs/agent/1-1-n/delivery-and-safety.md"
        changed.write_text(changed.read_text(encoding="utf-8") + "\npreview update\n", encoding="utf-8")
        new_bundle = self.load_variant(variant, version="0.1.1")
        update_preview = steeringctl.build_plan(
            "update", new_bundle, self.workspace, installed_bundle=self.bundle
        ).preview()
        self.assertIn("diff-start", update_preview)
        self.assertIn("@@", update_preview)
        uninstall_preview = self.run_cli("uninstall", "1-1-n", "--target", str(self.workspace))[1]
        self.assertIn("+++ /dev/null", uninstall_preview)

    def test_fresh_install_and_doctor_json(self) -> None:
        self.install()
        self.assertTrue((self.workspace / "AGENTS.md").is_file())
        root = (self.workspace / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("狀態：`required`", root)
        self.assertIn("docs/agent/1-1-n/INDEX.md", root)
        receipt = json.loads((self.workspace / ".steeringctl/1-1-n.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(receipt["source_payload_sha256"], self.bundle.payload_digests)
        code, output, err = self.run_cli("doctor", "1-1-n", "--target", str(self.workspace), "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(output)["status"], "installed")

    def test_dispatch_liveness_contract_is_portable_and_bounded(self) -> None:
        lifecycle = (
            STAGING_ROOT / "modules/1-1-n/docs/agent/1-1-n/lifecycle-and-handoff.md"
        ).read_text(encoding="utf-8")
        readme = (STAGING_ROOT / "README.md").read_text(encoding="utf-8")
        for document in (lifecycle, readme):
            self.assertIn("herdr pane run <worker-pane> \"<assignment>\"", document)
            self.assertIn(
                "herdr wait agent-status <worker-pane> --status working --timeout <bounded-ms>",
                document,
            )
            self.assertIn("dispatch_failed", document)
        self.assertIn("ready", lifecycle)
        self.assertIn("liveness audit", lifecycle)
        self.assertIn("exactly one `Enter`", lifecycle)
        self.assertIn("不得重送 assignment text", lifecycle)
        for phrase in ("stale／duplicate label", "replacement", "continuous polling"):
            self.assertIn(phrase, lifecycle)
        for forbidden in ("/" + "home/art", "w3" + ":pC", "2026" + "-08-20"):
            self.assertNotIn(forbidden, lifecycle)
            self.assertNotIn(forbidden, readme)

        cases = (
            (("composer", "working"), ("started", 1)),
            (("working",), ("started", 0)),
            (("idle", "idle"), ("dispatch_failed", 1)),
        )
        for statuses, expected in cases:
            with self.subTest(statuses=statuses):
                self.assertEqual(documented_dispatch_outcome(statuses), expected)

        self.install()
        installed_lifecycle = (
            self.workspace / "docs/agent/1-1-n/lifecycle-and-handoff.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(installed_lifecycle, lifecycle)

    def test_existing_agents_and_post_install_other_blocks_are_preserved(self) -> None:
        original = (
            "# Existing workspace\n"
            "owner prose must remain\n"
            "<!-- steeringctl:managed-module:other:start -->\n"
            "other module\n"
            "<!-- steeringctl:managed-module:other:end -->\n"
        )
        (self.workspace / "AGENTS.md").write_text(original, encoding="utf-8")
        self.install()
        installed = (self.workspace / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(installed.startswith(original))
        self.assertIn("other module", installed)
        owner_edit = "\npost-install owner prose\n"
        other_edit = "<!-- steeringctl:managed-module:other:v2 -->\n"
        (self.workspace / "AGENTS.md").write_text(installed + owner_edit + other_edit, encoding="utf-8")
        code, _out, err = self.run_cli("doctor", "1-1-n", "--target", str(self.workspace))
        self.assertEqual((code, err), (0, ""))
        code, _out, err = self.run_cli("update", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual((code, err), (0, ""))
        code, _out, err = self.run_cli("uninstall", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual((code, err), (0, ""))
        final = (self.workspace / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(final, original + owner_edit + other_edit)

    def test_same_version_reinstall_is_idempotent(self) -> None:
        self.install()
        before = self.snapshot()
        code, output, err = self.run_cli("install", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("already-installed", output)
        self.assertEqual(self.snapshot(), before)

    def test_update_changes_only_owned_payload_and_preserves_root_prose(self) -> None:
        prefix = "# Owner prose\nDo not remove this line.\n"
        (self.workspace / "AGENTS.md").write_text(prefix, encoding="utf-8")
        self.install()
        variant = self.copy_release()
        changed = variant / "modules/1-1-n/docs/agent/1-1-n/delivery-and-safety.md"
        changed.write_text(changed.read_text(encoding="utf-8") + "\nUpdated payload.\n", encoding="utf-8")
        new_bundle = self.load_variant(variant, version="0.1.1")
        plan = steeringctl.build_plan("update", new_bundle, self.workspace, installed_bundle=self.bundle)
        steeringctl.execute_plan(plan)
        self.assertTrue((self.workspace / "AGENTS.md").read_text(encoding="utf-8").startswith(prefix))
        installed_changed = self.workspace / "docs/agent/1-1-n/delivery-and-safety.md"
        self.assertIn("Updated payload.", installed_changed.read_text(encoding="utf-8"))
        receipt = json.loads((self.workspace / ".steeringctl/1-1-n.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["version"], "0.1.1")

    def test_modified_owned_file_blocks_update_and_uninstall(self) -> None:
        self.install()
        managed = self.workspace / "docs/agent/1-1-n/INDEX.md"
        managed.write_text(managed.read_text(encoding="utf-8") + "manual edit\n", encoding="utf-8")
        update = self.run_cli("update", "1-1-n", "--target", str(self.workspace), "--yes")
        uninstall = self.run_cli("uninstall", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual(update[0], steeringctl.EXIT_CONFLICT)
        self.assertEqual(uninstall[0], steeringctl.EXIT_CONFLICT)
        self.assertTrue(managed.exists())
        self.assertTrue((self.workspace / ".steeringctl/1-1-n.json").exists())

    def test_uninstall_preserves_user_agents_and_retains_fresh_root(self) -> None:
        original = "# User root\nKeep this exact content.\n"
        (self.workspace / "AGENTS.md").write_text(original, encoding="utf-8")
        self.install()
        code, _output, err = self.run_cli("uninstall", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual((self.workspace / "AGENTS.md").read_text(encoding="utf-8"), original)
        self.assertFalse((self.workspace / "docs/agent/1-1-n/INDEX.md").exists())
        self.assertFalse((self.workspace / ".steeringctl/1-1-n.json").exists())
        fresh = Path(self.tempdir.name) / "fresh-workspace"
        fresh.mkdir()
        code, _output, err = self.run_cli("install", "1-1-n", "--target", str(fresh), "--yes")
        self.assertEqual((code, err), (0, ""))
        code, _output, err = self.run_cli("uninstall", "1-1-n", "--target", str(fresh), "--yes")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue((fresh / "AGENTS.md").is_file())

    def test_tampered_root_created_receipt_never_deletes_existing_root(self) -> None:
        owner_prose = "# Owner prose retained\n"
        variant = self.copy_release()
        variant_root = variant / "modules/1-1-n/AGENTS.md"
        variant_root.write_text(
            owner_prose + self.bundle.managed_block.decode("utf-8") + "\n",
            encoding="utf-8",
        )
        variant_bundle = self.load_variant(variant)
        (self.workspace / "AGENTS.md").write_text(owner_prose, encoding="utf-8")
        steeringctl.execute_plan(steeringctl.build_plan("install", variant_bundle, self.workspace))
        self.assertEqual(
            (self.workspace / "AGENTS.md").read_bytes(),
            variant_bundle.data_for("AGENTS.md"),
        )
        receipt_path = self.workspace / ".steeringctl/1-1-n.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["root_created"] = True
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        steeringctl.execute_plan(
            steeringctl.build_plan(
                "uninstall", variant_bundle, self.workspace, installed_bundle=variant_bundle
            )
        )
        self.assertTrue((self.workspace / "AGENTS.md").is_file())
        self.assertEqual((self.workspace / "AGENTS.md").read_text(encoding="utf-8"), owner_prose)

    def test_apply_failure_rolls_back_every_file(self) -> None:
        plan = steeringctl.build_plan("install", self.bundle, self.workspace)
        with self.assertRaises(steeringctl.ApplyError):
            steeringctl.execute_plan(plan, failure_after=1)
        self.assertEqual(self.snapshot(), {})

    def test_missing_descriptor_capability_fails_closed(self) -> None:
        plan = steeringctl.build_plan("install", self.bundle, self.workspace)
        with mock.patch.object(steeringctl.os, "supports_dir_fd", set()):
            with self.assertRaises(steeringctl.ConflictError):
                steeringctl.execute_plan(plan)
        self.assertEqual(self.snapshot(), {})

    def test_descriptor_parent_race_never_writes_external_and_rolls_back(self) -> None:
        plan = steeringctl.build_plan("install", self.bundle, self.workspace)
        external = Path(self.tempdir.name) / "external"
        (external / "agent" / "1-1-n").mkdir(parents=True)
        original_replace = steeringctl.os.replace
        calls = {"count": 0, "raced": False}

        def race(src: str, dst: str, *, src_dir_fd: int | None = None, dst_dir_fd: int | None = None) -> None:
            if calls["count"] == 1 and (self.workspace / "docs").is_dir():
                (self.workspace / "docs").rename(self.workspace / "docs-before-race")
                (self.workspace / "docs").symlink_to(external)
                calls["raced"] = True
            calls["count"] += 1
            original_replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

        steeringctl.os.replace = race
        try:
            with self.assertRaises(steeringctl.SteeringError):
                steeringctl.execute_plan(plan)
        finally:
            steeringctl.os.replace = original_replace
        self.assertTrue(calls["raced"])
        self.assertEqual([path for path in external.rglob("*") if path.is_file()], [])
        self.assertEqual(self.snapshot(), {})

    def test_bundle_rejects_traversal_absolute_symlink_digest_missing_and_extra(self) -> None:
        cases: list[tuple[str, callable]] = []

        def traversal(variant: Path) -> None:
            path = variant / "modules/1-1-n/manifest.json"
            value = json.loads(path.read_text())
            value["payload"][0]["path"] = "../outside"
            path.write_text(json.dumps(value), encoding="utf-8")

        def absolute(variant: Path) -> None:
            path = variant / "modules/1-1-n/manifest.json"
            value = json.loads(path.read_text())
            value["payload"][0]["path"] = "/tmp/outside"
            path.write_text(json.dumps(value), encoding="utf-8")

        def symlink(variant: Path) -> None:
            payload = variant / "modules/1-1-n/docs/agent/1-1-n/INDEX.md"
            payload.unlink()
            outside = Path(self.tempdir.name) / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            payload.symlink_to(outside)

        def payload_digest(variant: Path) -> None:
            payload = variant / "modules/1-1-n/docs/agent/1-1-n/INDEX.md"
            payload.write_text(payload.read_text(encoding="utf-8") + "tamper", encoding="utf-8")

        def missing(variant: Path) -> None:
            (variant / "modules/1-1-n/docs/agent/1-1-n/INDEX.md").unlink()

        def extra(variant: Path) -> None:
            (variant / "extra.md").write_text("extra", encoding="utf-8")

        cases.extend([
            ("traversal", traversal), ("absolute", absolute), ("symlink", symlink),
            ("digest", payload_digest), ("missing", missing), ("extra", extra),
        ])
        for name, mutate in cases:
            with self.subTest(name=name):
                variant = self.copy_release()
                mutate(variant)
                with self.assertRaises(steeringctl.BundleError):
                    steeringctl.load_bundle(variant)

    def test_immutable_snapshot_ignores_post_load_source_tamper(self) -> None:
        variant = self.copy_release()
        trusted = refresh_release(variant)
        verified = steeringctl.load_bundle(variant, trusted_release_sha256=trusted)
        source = variant / "modules/1-1-n/docs/agent/1-1-n/INDEX.md"
        source.write_bytes(source.read_bytes() + b"POST_LOAD_TAMPER\n")
        plan = steeringctl.build_plan("install", verified, self.workspace)
        steeringctl.execute_plan(plan)
        installed = (self.workspace / "docs/agent/1-1-n/INDEX.md").read_bytes()
        self.assertEqual(installed, verified.data_for("docs/agent/1-1-n/INDEX.md"))
        self.assertNotIn(b"POST_LOAD_TAMPER", installed)

    def test_trusted_release_checksum_gate_rejects_missing_tampered_and_extra(self) -> None:
        missing = self.run_cli("install", "1-1-n", "--target", str(self.workspace), "--yes", release_sha=None)
        self.assertEqual(missing[0], steeringctl.EXIT_CONFLICT)
        self.assertEqual(self.snapshot(), {})
        variant = self.copy_release()
        (variant / "README.md").write_bytes((variant / "README.md").read_bytes() + b"tamper")
        proc = subprocess.run(
            [sys.executable, str(variant / "installer/steeringctl.py"), "install", "1-1-n", "--target", str(self.workspace), "--release-sha256", self.release_sha, "--yes"],
            text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(proc.returncode, steeringctl.EXIT_CONFLICT)
        extra = self.copy_release()
        (extra / "unlisted.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(steeringctl.BundleError):
            steeringctl.load_bundle(extra, trusted_release_sha256=self.release_sha)

    def test_receipt_only_version_and_file_plus_receipt_tamper_fail_closed(self) -> None:
        self.install()
        receipt_path = self.workspace / ".steeringctl/1-1-n.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["version"] = "forged"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        doctor = self.run_cli("doctor", "1-1-n", "--target", str(self.workspace))
        self.assertEqual(doctor[0], steeringctl.EXIT_CONFLICT)

        self.tearDown()
        self.setUp()
        self.install()
        receipt_path = self.workspace / ".steeringctl/1-1-n.json"
        managed = self.workspace / "docs/agent/1-1-n/INDEX.md"
        modified = managed.read_bytes() + b"USER MODIFICATION\n"
        managed.write_bytes(modified)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["payload_sha256"]["docs/agent/1-1-n/INDEX.md"] = digest(modified)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        uninstall = self.run_cli("uninstall", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual(uninstall[0], steeringctl.EXIT_CONFLICT)
        self.assertTrue(managed.exists())

    def test_wrong_installed_trusted_release_cannot_authorize_update(self) -> None:
        self.install()
        variant = self.copy_release()
        wrong = self.load_variant(variant, version="0.9.0")
        with self.assertRaises(steeringctl.ConflictError):
            steeringctl.build_plan("update", self.bundle, self.workspace, installed_bundle=wrong)

    def test_duplicate_owned_markers_fail_closed(self) -> None:
        self.workspace.joinpath("AGENTS.md").write_text(
            steeringctl.START_MARKER + "\n" + steeringctl.END_MARKER + "\n" + steeringctl.START_MARKER + "\n",
            encoding="utf-8",
        )
        result = self.run_cli("install", "1-1-n", "--target", str(self.workspace), "--yes")
        self.assertEqual(result[0], steeringctl.EXIT_CONFLICT)
        self.assertEqual(self.snapshot(), {"AGENTS.md": self.workspace.joinpath("AGENTS.md").read_bytes()})

    def test_doctor_human_and_version_are_stable(self) -> None:
        code, output, err = self.run_cli("doctor", "1-1-n", "--target", str(self.workspace))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("status=not-installed", output)
        code, output, err = self.run_cli("version", "1-1-n", release_sha=None)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(output.strip(), "1-1-n 0.1.0")


if __name__ == "__main__":
    unittest.main()
