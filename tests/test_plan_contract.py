#!/usr/bin/env python3
"""Deterministic tests for the plan gate, reviewer selection, and installer contract."""

from __future__ import annotations

import hashlib
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


def metadata(**overrides) -> dict:
    values = {
        "task_id": "test-plan-01",
        "revision": 1,
        "owner_authorization": "approved source change",
        "objective": "Validate the plan gate.",
        "risk_tier": "low",
        "review_mode": "frontier-single",
        "review_rationale": "The change is low risk and the selected review mode is available.",
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
    values.update(overrides)
    return values


def review_and_dispatch(plan: bytes, reviewer_id="sol-01", model="gpt-5.6-sol", provider="openai", capability="frontier-plan-review"):
    digest = hashlib.sha256(plan).hexdigest()
    dispatch = {
        "task": "test-plan-01",
        "plan_revision": "1",
        "plan_sha256": digest,
        "reviewer_id": reviewer_id,
        "provider": provider,
        "model": model,
        "capability": capability,
        "review_mode": "frontier-single",
        "scope": "read-only",
    }
    review = "\n".join(
        (
            "task: test-plan-01",
            "plan_revision: 1",
            f"plan_sha256: {digest}",
            f"reviewer_id: {reviewer_id}",
            f"reviewer_model: {model}",
            "review_mode: frontier-single",
            f"provider: {provider}",
            f"capability: {capability}",
            "scope: read-only",
            "blockers: 0",
            "high_findings: 0",
            "findings: none",
            "required_changes: none",
            "conclusion: LGTM",
            "marker: LGTM",
        )
    )
    return review, dispatch


def fallback_artifacts(plan: bytes):
    digest = hashlib.sha256(plan).hexdigest()
    reviewers = (
        ("agy-review-01", "agy", "gemini-3.8-flash-high", "agy-high-plan-review"),
        ("devin-review-01", "devin", "swe-2-high", "SWE-2 high"),
    )
    reviews = []
    dispatches = []
    for reviewer_id, provider, model, capability in reviewers:
        dispatches.append(
            {
                "task": "test-plan-01",
                "plan_revision": "1",
                "plan_sha256": digest,
                "reviewer_id": reviewer_id,
                "provider": provider,
                "model": model,
                "capability": capability,
                "review_mode": "dual-fallback",
                "scope": "read-only",
            }
        )
        reviews.append(
            "\n".join(
                (
                    "task: test-plan-01",
                    "plan_revision: 1",
                    f"plan_sha256: {digest}",
                    f"reviewer_id: {reviewer_id}",
                    f"reviewer_model: {model}",
                    "review_mode: dual-fallback",
                    f"provider: {provider}",
                    f"capability: {capability}",
                    "scope: read-only",
                    "blockers: 0",
                    "high_findings: 0",
                    "findings: none",
                    "required_changes: none",
                    "conclusion: LGTM",
                    "marker: LGTM",
                )
            )
        )
    return reviews, dispatches


class PlanRendererTests(unittest.TestCase):
    def test_render_is_deterministic_and_complete(self):
        first = RENDER.render_plan(metadata())
        second = RENDER.render_plan(metadata())
        self.assertEqual(first, second)
        self.assertIn("# Plan: Validate the plan gate.", first)
        self.assertIn("- risk_tier: `low`", first)
        self.assertIn("- review_mode: `frontier-single`", first)
        self.assertIn("## Execution gate", first)
        self.assertNotIn("${", first)

    def test_invalid_risk_and_review_modes_fail(self):
        for field, value in (("risk_tier", "critical"), ("review_mode", "single")):
            invalid = metadata(**{field: value})
            with self.subTest(field=field):
                with self.assertRaises(RENDER.PlanError):
                    RENDER.render_plan(invalid)

    def test_missing_unknown_and_unsafe_values_fail(self):
        missing = metadata()
        del missing["rollback"]
        with self.assertRaisesRegex(RENDER.PlanError, "missing required"):
            RENDER.render_plan(missing)

        unknown = metadata(extra="not allowed")
        with self.assertRaisesRegex(RENDER.PlanError, "unknown metadata"):
            RENDER.render_plan(unknown)

        placeholder = metadata(objective="${unresolved}")
        with self.assertRaisesRegex(RENDER.PlanError, "placeholder"):
            RENDER.render_plan(placeholder)

        for value in (
            "api_key: abcdefghijklmnop",
            "sk-proj-123456789012345678901234",
            "AKIA1234567890ABCDEF",
            "eyJabcdefghijk.eyJabcdefghijk.eyJabcdefghijk",
            "xoxb-1234567890",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RENDER.PlanError, "credential-like"):
                    RENDER.render_plan(metadata(owner_authorization=value))

    def test_renderer_writes_atomically_to_requested_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "plan.md"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "render_plan.py"),
                 "--metadata", str(ROOT / "templates" / "example-plan.json"),
                 "--output", str(output)],
                cwd=ROOT, check=False, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output.is_file())
            self.assertIn("plan_sha256=", completed.stderr)
            self.assertNotIn("${", output.read_text(encoding="utf-8"))


class PlanGateTests(unittest.TestCase):
    def test_frontier_single_matching_digest_and_lgtm_pass(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        self.assertEqual(hashlib.sha256(plan).hexdigest(), GATE.validate_gate(plan, review, dispatch))

    def test_fallback_requires_two_independent_reviewers(self):
        plan = RENDER.render_plan(
            metadata(review_mode="dual-fallback", risk_tier="medium", review_rationale="No frontier reviewer is available; use two independent host adapters.")
        ).encode("utf-8")
        reviews, dispatches = fallback_artifacts(plan)
        self.assertEqual(hashlib.sha256(plan).hexdigest(), GATE.validate_gate(plan, reviews, dispatches))
        with self.assertRaisesRegex(GATE.GateError, "at least two"):
            GATE.validate_gate(plan, reviews[:1], dispatches[:1])

    def test_fallback_requires_distinct_provider_and_identity(self):
        plan = RENDER.render_plan(
            metadata(review_mode="dual-fallback", risk_tier="low", review_rationale="Two independent host adapters are available.")
        ).encode("utf-8")
        reviews, dispatches = fallback_artifacts(plan)
        dispatches[1] = dict(dispatches[0], reviewer_id="devin-review-01")
        with self.assertRaisesRegex(GATE.GateError, "approved fallback reviewer|providers must be independent"):
            GATE.validate_gate(plan, reviews, dispatches)

    def test_high_or_unknown_fallback_requires_owner_or_frontier(self):
        plan = RENDER.render_plan(
            metadata(review_mode="dual-fallback", risk_tier="high", review_rationale="Risk is high.")
        ).encode("utf-8")
        reviews, dispatches = fallback_artifacts(plan)
        with self.assertRaisesRegex(GATE.GateError, "high or unknown"):
            GATE.validate_gate(plan, reviews, dispatches)

        owner_plan = RENDER.render_plan(
            metadata(review_mode="owner-choice", risk_tier="unknown", review_rationale="The coordinator cannot determine equivalence.")
        ).encode("utf-8")
        with self.assertRaisesRegex(GATE.GateError, "Owner decision"):
            GATE.validate_gate(owner_plan, reviews, dispatches)

    def test_identity_model_capability_and_conclusion_fail_closed(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        digest = hashlib.sha256(plan).hexdigest()

        bad = dict(dispatch, model="gpt-5.6-sol-max")
        with self.assertRaisesRegex(GATE.GateError, "capability floor"):
            GATE.validate_gate(plan, review, bad)

        for label in ("GPT-6-ASTRA", " gpt-6-astra", "gpt-6-astra "):
            non_exact = dict(dispatch, model=label)
            non_exact_review = review.replace("reviewer_model: gpt-5.6-sol", f"reviewer_model: {label}")
            with self.subTest(label=label):
                with self.assertRaisesRegex(GATE.GateError, "capability floor|surrounding whitespace"):
                    GATE.validate_gate(plan, non_exact_review, non_exact)

        bad_digest = review.replace(digest, "0" * 64)
        with self.assertRaisesRegex(GATE.GateError, "plan_sha256 does not match"):
            GATE.validate_gate(plan, bad_digest, dispatch)

        bad_model_binding = dict(dispatch, model="gpt-6-astra")
        with self.assertRaisesRegex(GATE.GateError, "model does not match"):
            GATE.validate_gate(plan, review, bad_model_binding)

        bad_review = review.replace("reviewer_id: sol-01", "reviewer_id: other")
        with self.assertRaisesRegex(GATE.GateError, "reviewer_id"):
            GATE.validate_gate(plan, bad_review, dispatch)

        duplicate = review + "\nblockers: 0"
        with self.assertRaisesRegex(GATE.GateError, "duplicate"):
            GATE.validate_gate(plan, duplicate, dispatch)

        bad_conclusion = review.replace("conclusion: LGTM", "conclusion: REQUEST_CHANGES")
        with self.assertRaisesRegex(GATE.GateError, "LGTM"):
            GATE.validate_gate(plan, bad_conclusion, dispatch)

    def test_missing_fields_and_plan_identity_markers_fail_closed(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        for field in ("reviewer_id", "capability", "findings", "required_changes"):
            incomplete = "\n".join(
                line for line in review.splitlines() if not line.startswith(f"{field}:")
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(GATE.GateError, "missing required"):
                    GATE.validate_gate(plan, incomplete, dispatch)

        for field in ("task", "plan_revision"):
            incomplete = "\n".join(
                line for line in review.splitlines() if not line.startswith(f"{field}:")
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(GATE.GateError, "missing required"):
                    GATE.validate_gate(plan, incomplete, dispatch)

        duplicate_task = plan + b"\n- task_id: `test-plan-01`\n"
        with self.assertRaisesRegex(GATE.GateError, "exactly one task"):
            GATE.validate_gate(duplicate_task, review, dispatch)
        duplicate_revision = plan + b"\n- revision: `1`\n"
        with self.assertRaisesRegex(GATE.GateError, "exactly one revision"):
            GATE.validate_gate(duplicate_revision, review, dispatch)

    def test_review_task_and_revision_mismatch_fail_closed(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        with self.assertRaisesRegex(GATE.GateError, "task does not match"):
            GATE.validate_gate(plan, review.replace("task: test-plan-01", "task: other"), dispatch)
        with self.assertRaisesRegex(GATE.GateError, "revision does not match"):
            GATE.validate_gate(plan, review.replace("plan_revision: 1", "plan_revision: 2"), dispatch)

    def test_plan_identity_markers_must_be_backticked(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        for old, new, message in (
            (b"- task_id: `test-plan-01`", b"- task_id: test-plan-01", "exactly one task"),
            (b"- revision: `1`", b"- revision: 1", "exactly one revision"),
        ):
            malformed = plan.replace(old, new)
            with self.subTest(message=message):
                with self.assertRaisesRegex(GATE.GateError, message):
                    GATE.validate_gate(malformed, review, dispatch)

    def test_dispatch_bindings_and_shape_fail_closed(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        cases = (
            ("task", "other", "plan identity does not match"),
            ("plan_revision", "2", "plan identity does not match"),
            ("plan_sha256", "0" * 64, "plan_sha256 does not match"),
            ("review_mode", "dual-fallback", "review_mode does not match"),
        )
        for key, value, message in cases:
            with self.subTest(key=key):
                with self.assertRaisesRegex(GATE.GateError, message):
                    GATE.validate_gate(plan, review, dict(dispatch, **{key: value}))

        missing = dict(dispatch)
        del missing["capability"]
        with self.assertRaisesRegex(GATE.GateError, "missing fields"):
            GATE.validate_gate(plan, review, missing)
        with self.assertRaisesRegex(GATE.GateError, "unknown fields"):
            GATE.validate_gate(plan, review, dict(dispatch, extra="unexpected"))

        bad_provider = review.replace("provider: openai", "provider: other")
        with self.assertRaisesRegex(GATE.GateError, "provider/capability"):
            GATE.validate_gate(plan, bad_provider, dispatch)

    def test_gate_zero_findings_scope_and_markers_are_mandatory(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        for field, value, message in (
            ("blockers", "1", "blocker/high findings"),
            ("high_findings", "1", "blocker/high findings"),
            ("scope", "write", "scope must be read-only"),
            ("required_changes", "change this", "required_changes"),
            ("marker", "PLAN_REVIEW_BLOCKED", "LGTM"),
            ("review_mode", "dual-fallback", "review_mode does not match"),
        ):
            bad_review = "\n".join(
                f"{field}: {value}" if line.startswith(f"{field}:") else line
                for line in review.splitlines()
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(GATE.GateError, message):
                    GATE.validate_gate(plan, bad_review, dispatch)

        bad_dispatch_scope = dict(dispatch, scope="write")
        with self.assertRaisesRegex(GATE.GateError, "scope must be read-only"):
            GATE.validate_gate(plan, review, bad_dispatch_scope)
        for field in ("provider", "capability"):
            bad_dispatch = dict(dispatch, **{field: "other"})
            with self.subTest(dispatch_field=field):
                with self.assertRaisesRegex(GATE.GateError, "provider/capability"):
                    GATE.validate_gate(plan, review, bad_dispatch)

    def test_cli_accepts_repeated_review_and_dispatch(self):
        plan = RENDER.render_plan(
            metadata(review_mode="dual-fallback", risk_tier="medium", review_rationale="Two host reviewers are the bounded fallback.")
        ).encode("utf-8")
        reviews, dispatches = fallback_artifacts(plan)
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            plan_path = directory / "plan.md"
            plan_path.write_bytes(plan)
            review_paths, dispatch_paths = [], []
            for index, (review, dispatch) in enumerate(zip(reviews, dispatches), start=1):
                review_path = directory / f"review-{index}.md"
                dispatch_path = directory / f"dispatch-{index}.json"
                review_path.write_text(review, encoding="utf-8")
                dispatch_path.write_text(json.dumps(dispatch), encoding="utf-8")
                review_paths.append(review_path)
                dispatch_paths.append(dispatch_path)
            command = [sys.executable, str(ROOT / "scripts" / "validate_plan_gate.py"), "--plan", str(plan_path)]
            for path in review_paths:
                command.extend(("--review", str(path)))
            for path in dispatch_paths:
                command.extend(("--dispatch", str(path)))
            completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("PLAN_GATE_LGTM", completed.stdout)

    def test_cli_rejects_duplicate_dispatch_key(self):
        plan = RENDER.render_plan(metadata()).encode("utf-8")
        review, dispatch = review_and_dispatch(plan)
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            plan_path = directory / "plan.md"
            review_path = directory / "review.md"
            dispatch_path = directory / "dispatch.json"
            plan_path.write_bytes(plan)
            review_path.write_text(review, encoding="utf-8")
            dispatch_path.write_text('{"model":"gpt-5.6-sol","model":"gpt-6-astra"}', encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_plan_gate.py"), "--plan", str(plan_path), "--review", str(review_path), "--dispatch", str(dispatch_path)],
                cwd=ROOT, check=False, capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("duplicate dispatch field", completed.stderr)

    def test_fallback_rejects_duplicate_identity_even_with_distinct_providers(self):
        plan = RENDER.render_plan(
            metadata(review_mode="dual-fallback", risk_tier="medium", review_rationale="Two independent host reviewers are available.")
        ).encode("utf-8")
        reviews, dispatches = fallback_artifacts(plan)
        dispatches[1] = dict(dispatches[1], reviewer_id=dispatches[0]["reviewer_id"])
        with self.assertRaisesRegex(GATE.GateError, "identities must be distinct"):
            GATE.validate_gate(plan, reviews, dispatches)


class PackageContractTests(unittest.TestCase):
    def test_active_package_has_no_retired_protocol_terms(self):
        paths = [
            ROOT / "README.md", ROOT / "SKILL.md", ROOT / "install.sh",
            *(ROOT / "docs").rglob("*.md"), *(ROOT / "references").glob("*.md"),
            *(ROOT / "scripts").glob("*.py"), *(ROOT / "templates").glob("*"),
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
            completed = subprocess.run([str(INSTALLER), str(destination)], cwd=ROOT, env={**os.environ, "HOME": temp_dir}, check=False, capture_output=True, text=True, timeout=15)
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
            smoke = subprocess.run([sys.executable, str(destination / "scripts" / "smoke_installed_package.py")], cwd=destination, check=False, capture_output=True, text=True, timeout=10)
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
