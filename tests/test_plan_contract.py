#!/usr/bin/env python3
"""Deterministic tests for the portable plan gate and installer contract."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RENDER = load_module("test_render_plan", ROOT / "scripts" / "render_plan.py")
GATE = load_module("test_validate_plan_gate", ROOT / "scripts" / "validate_plan_gate.py")
INSTALLER = ROOT / "install.sh"


def metadata() -> dict:
    return {
        "task_id": "test-plan-01",
        "revision": 1,
        "owner_authorization": "approved source change",
        "objective": "Validate the plan gate.",
        "scope": ["src/example.py", "tests/test_example.py"],
        "exclusions": ["deployment", "credentials"],
        "sources": ["canonical brief", "repository documentation"],
        "dependencies": ["the public interface remains stable"],
        "steps": ["implement the seam", "test the seam", "inspect the diff"],
        "risk_and_authority": ["source and tests only"],
        "validation": ["python3 -m unittest discover -s tests"],
        "rollback": ["restore the listed files from the snapshot"],
        "deliverables": [".coordination/tasks/test-plan-01/plan.md", "report.md"],
        "acceptance": ["main window verifies the scoped diff"],
    }


class PlanRendererTests(unittest.TestCase):
    def test_render_is_deterministic_and_complete(self):
        first = RENDER.render_plan(metadata())
        second = RENDER.render_plan(metadata())
        self.assertEqual(first, second)
        self.assertIn("# Plan: Validate the plan gate.", first)
        self.assertIn("## Execution gate", first)
        self.assertNotIn("${", first)

    def test_missing_unknown_and_unsafe_values_fail(self):
        missing = metadata()
        del missing["rollback"]
        with self.assertRaisesRegex(RENDER.PlanError, "missing required"):
            RENDER.render_plan(missing)

        unknown = metadata()
        unknown["extra"] = "not allowed"
        with self.assertRaisesRegex(RENDER.PlanError, "unknown metadata"):
            RENDER.render_plan(unknown)

        placeholder = metadata()
        placeholder["objective"] = "${unresolved}"
        with self.assertRaisesRegex(RENDER.PlanError, "placeholder"):
            RENDER.render_plan(placeholder)

        for value in (
            "api_key: abcdefghijklmnop",
            "sk-proj-123456789012345678901234",
            "AKIA1234567890ABCDEF",
            "eyJabcdefghijk.eyJabcdefghijk.eyJabcdefghijk",
            "xoxb-1234567890",
        ):
            credential = metadata()
            credential["owner_authorization"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(RENDER.PlanError, "credential-like"):
                    RENDER.render_plan(credential)

    def test_renderer_writes_atomically_to_requested_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "plan.md"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "render_plan.py"),
                 "--metadata", str(ROOT / "templates" / "example-plan.json"),
                 "--output", str(output)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output.is_file())
            self.assertIn("plan_sha256=", completed.stderr)
            self.assertNotIn("${", output.read_text(encoding="utf-8"))


class PlanGateTests(unittest.TestCase):
    def test_matching_digest_model_and_lgtm_pass(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        digest = __import__("hashlib").sha256(plan).hexdigest()
        review = "\n".join(
            (
                "task: test-plan-01",
                "plan_revision: 1",
                f"plan_sha256: {digest}",
                "reviewer_model: gpt-6-astra",
                "scope: read-only",
                "blockers: 0",
                "high_findings: 0",
                "findings: none",
                "required_changes: none",
                "conclusion: LGTM",
                "marker: LGTM",
            )
        )
        self.assertEqual(digest, GATE.validate_gate(plan, review, {"model": "gpt-6-astra"}))

    def test_digest_model_and_conclusion_fail_closed(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        digest = __import__("hashlib").sha256(plan).hexdigest()
        base = {
            "task": "test-plan-01",
            "plan_revision": "1",
            "plan_sha256": digest,
            "scope": "read-only",
            "reviewer_model": "gpt-6-astra",
            "blockers": "0",
            "high_findings": "0",
            "findings": "none",
            "required_changes": "none",
            "conclusion": "LGTM",
            "marker": "LGTM",
        }

        def review_text(values):
            return "\n".join(f"{key}: {value}" for key, value in values.items())

        bad_digest = dict(base)
        bad_digest["plan_sha256"] = "0" * 64
        with self.assertRaisesRegex(GATE.GateError, "does not match"):
            GATE.validate_gate(plan, review_text(bad_digest), {"model": "gpt-6-astra"})

        bad_model = dict(base)
        bad_model["reviewer_model"] = "basic-model"
        with self.assertRaisesRegex(GATE.GateError, "capability floor"):
            GATE.validate_gate(plan, review_text(bad_model), {"model": "basic-model"})

        weak_model = dict(base)
        weak_model["reviewer_model"] = "gpt-6-mini"
        with self.assertRaisesRegex(GATE.GateError, "capability floor"):
            GATE.validate_gate(plan, review_text(weak_model), {"model": "gpt-6-mini"})

        bad_suffix = dict(base)
        bad_suffix["reviewer_model"] = "gpt-5.6-sol-max"
        with self.assertRaisesRegex(GATE.GateError, "capability floor"):
            GATE.validate_gate(plan, review_text(bad_suffix), {"model": "gpt-5.6-sol-max"})

        for label in ("GPT-6-ASTRA", " gpt-6-astra", "gpt-6-astra "):
            non_exact = dict(base)
            non_exact["reviewer_model"] = label
            with self.subTest(label=label):
                with self.assertRaisesRegex(GATE.GateError, "capability floor"):
                    GATE.validate_gate(plan, review_text(non_exact), {"model": label})

        mismatch = dict(base)
        with self.assertRaisesRegex(GATE.GateError, "do not match"):
            GATE.validate_gate(plan, review_text(mismatch), {"model": "gpt-5.6-sol"})

        duplicate = review_text(base) + "\nblockers: 0"
        with self.assertRaisesRegex(GATE.GateError, "duplicate"):
            GATE.validate_gate(plan, duplicate, {"model": "gpt-6-astra"})

        for missing in ("task", "plan_revision", "findings", "required_changes"):
            incomplete = dict(base)
            del incomplete[missing]
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(GATE.GateError, "missing required"):
                    GATE.validate_gate(plan, review_text(incomplete), {"model": "gpt-6-astra"})

        template_plan = plan.replace(b"- task_id: `test-plan-01`", b"- task_id: test-plan-01").replace(b"- revision: `1`", b"- revision: 1")
        template_review = dict(base)
        template_review["plan_sha256"] = __import__("hashlib").sha256(template_plan).hexdigest()
        with self.assertRaisesRegex(GATE.GateError, "exactly one task identity"):
            GATE.validate_gate(template_plan, review_text(template_review), {"model": "gpt-6-astra"})

        duplicate_identity = plan + b"\n- task_id: `test-plan-01`\n"
        duplicate_review = dict(base)
        duplicate_review["plan_sha256"] = __import__("hashlib").sha256(duplicate_identity).hexdigest()
        with self.assertRaisesRegex(GATE.GateError, "exactly one task identity"):
            GATE.validate_gate(duplicate_identity, review_text(duplicate_review), {"model": "gpt-6-astra"})

        bad_conclusion = dict(base)
        bad_conclusion["conclusion"] = "REQUEST_CHANGES"
        with self.assertRaisesRegex(GATE.GateError, "LGTM"):
            GATE.validate_gate(plan, review_text(bad_conclusion), {"model": "gpt-6-astra"})

    def test_cli_rejects_duplicate_dispatch_key(self):
        import hashlib

        plan = RENDER.render_plan(metadata()).encode("utf-8")
        digest = hashlib.sha256(plan).hexdigest()
        review = "\n".join(
            (
                "task: test-plan-01",
                "plan_revision: 1",
                f"plan_sha256: {digest}",
                "reviewer_model: gpt-6-astra",
                "scope: read-only",
                "blockers: 0",
                "high_findings: 0",
                "findings: none",
                "required_changes: none",
                "conclusion: LGTM",
                "marker: LGTM",
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            plan_path = directory / "plan.md"
            review_path = directory / "review.md"
            dispatch_path = directory / "dispatch.json"
            plan_path.write_bytes(plan)
            review_path.write_text(review, encoding="utf-8")
            dispatch_path.write_text('{"model":"gpt-6-mini","model":"gpt-6-astra"}', encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_plan_gate.py"), "--plan", str(plan_path), "--review", str(review_path), "--dispatch", str(dispatch_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("duplicate dispatch field", completed.stderr)

class PackageContractTests(unittest.TestCase):
    def test_active_package_has_no_retired_protocol_terms(self):
        paths = [
            ROOT / "README.md",
            ROOT / "SKILL.md",
            ROOT / "install.sh",
            *(ROOT / "docs").rglob("*.md"),
            *(ROOT / "references").glob("*.md"),
            *(ROOT / "scripts").glob("*.py"),
            *(ROOT / "templates").glob("*"),
        ]
        retired = re.compile(r"1:1:N|1-1-n|Herdr", re.IGNORECASE)
        for path in paths:
            with self.subTest(path=path):
                self.assertIsNone(retired.search(path.read_text(encoding="utf-8")))

    def test_markdown_links_fences_and_whitespace(self):
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        markdown = [ROOT / "README.md", ROOT / "SKILL.md", *(ROOT / "docs").rglob("*.md"), *(ROOT / "references").glob("*.md")]
        for path in markdown:
            source = path.read_text(encoding="utf-8")
            self.assertEqual(source.count("```") % 2, 0, path)
            self.assertFalse(any(line.rstrip() != line for line in source.splitlines()), path)
            for target in link_pattern.findall(source):
                if target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                self.assertTrue((path.parent / target.split("#", 1)[0]).resolve().is_file(), f"{path}: {target}")

    def test_installer_and_fresh_smoke_are_finite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "installed"
            completed = subprocess.run(
                [str(INSTALLER), str(destination)],
                cwd=ROOT,
                env={**os.environ, "HOME": temp_dir},
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            expected = (
                "SKILL.md", "README.md", "install.sh", "docs/README.md", "docs/ai-runbook.md",
                "references/protocol.md", "references/review-contract.md", "references/execution-and-safety.md",
                "scripts/render_plan.py", "scripts/validate_plan_gate.py", "scripts/smoke_installed_package.py",
                "templates/plan.md.tmpl", "templates/example-plan.json", "tests/test_plan_contract.py",
            )
            for relative in expected:
                with self.subTest(relative=relative):
                    self.assertTrue((destination / relative).is_file(), relative)
            smoke = subprocess.run(
                [sys.executable, str(destination / "scripts" / "smoke_installed_package.py")],
                cwd=destination,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(smoke.returncode, 0, smoke.stderr)
            self.assertIn("fresh-install smoke ok", smoke.stdout)
            self.assertFalse((destination / "references" / "roles-and-gates.md").exists())
            self.assertFalse((destination / "profiles").exists())

    def test_shell_and_python_compile(self):
        shell = subprocess.run(["sh", "-n", str(INSTALLER)], cwd=ROOT, check=False, capture_output=True, text=True)
        self.assertEqual(shell.returncode, 0, shell.stderr)
        for path in (ROOT / "scripts").glob("*.py"):
            completed = subprocess.run([sys.executable, "-m", "py_compile", str(path)], cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, f"{path}: {completed.stderr}")


if __name__ == "__main__":
    unittest.main()
