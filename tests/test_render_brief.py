#!/usr/bin/env python3
"""Deterministic tests for the portable brief renderer and installer contract."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "scripts" / "render_brief.py"
BOUNDED_PROCESS_PATH = ROOT / "scripts" / "bounded_process.py"
SMOKE_ENTRYPOINT = ROOT / "scripts" / "smoke_installed_package.py"
INSTALLER = ROOT / "install.sh"
TEST_SOURCE = Path(__file__).resolve()


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


RENDERER = load_module("portable_render_brief", RENDERER_PATH)
BOUNDED_PROCESS = load_module("portable_bounded_process", BOUNDED_PROCESS_PATH)


def metadata(profile: str = "developer") -> dict:
    values = {
        "task_id": "test-task-01",
        "profile": profile,
        "objective": "Validate the reusable brief seam.",
        "workspace": {"repo": "example-org/example-project", "cwd": "repository root"},
        "role": profile,
        "sources": ["canonical brief"],
        "scope": ["src/example.py", "tests/test_example.py"],
        "exclusions": ["deployment"],
        "allowed_mutations": ["edit the scoped files"],
        "checks": ["python3 -m unittest"],
        "profile_fields": {},
    }
    fields = {
        "developer": {"changes": ["Make the smallest implementation."]},
        "reviewer": {"review_focus": ["Check the requested behavior."]},
        "investigation": {"questions": ["What is the current behavior?"]},
        "design": {"decisions": ["Keep the seam compositional."]},
    }
    values["profile_fields"] = fields[profile]
    return values


class RenderBriefTests(unittest.TestCase):
    def test_render_is_deterministic_and_selects_all_profiles(self):
        outputs = {}
        for profile in ("developer", "reviewer", "investigation", "design"):
            first = RENDERER.render_brief(metadata(profile))
            second = RENDERER.render_brief(metadata(profile))
            self.assertEqual(first, second)
            self.assertIn(f"Profile: `{profile}`", first)
            self.assertNotIn("${", first)
            outputs[profile] = first
        self.assertIn("WRITER_COMPLETE", outputs["developer"])
        self.assertIn("REVIEW_COMPLETE", outputs["reviewer"])
        self.assertIn("INVESTIGATION_COMPLETE", outputs["investigation"])
        self.assertIn("DESIGN_COMPLETE", outputs["design"])

    def test_defaults_fill_profile_specific_artifact_and_marker(self):
        rendered = RENDERER.render_brief(metadata("reviewer"))
        self.assertIn(".coordination/tasks/test-task-01/review.md", rendered)
        self.assertIn("REVIEW_COMPLETE", rendered)

    def test_missing_required_values_fail_strictly(self):
        cases = []
        missing_objective = metadata()
        del missing_objective["objective"]
        cases.append(missing_objective)
        missing_profile_field = metadata()
        missing_profile_field["profile_fields"] = {}
        cases.append(missing_profile_field)
        for candidate in cases:
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(RENDERER.RenderError, "missing required"):
                    RENDERER.render_brief(candidate)

    def test_unknown_profile_fails(self):
        candidate = metadata()
        candidate["profile"] = "unknown"
        with self.assertRaisesRegex(RENDERER.RenderError, "unknown profile"):
            RENDERER.render_brief(candidate)

    def test_unresolved_placeholder_fails(self):
        candidate = metadata()
        candidate["objective"] = "Leave ${unresolved} in the result."
        with self.assertRaisesRegex(RENDERER.RenderError, "unresolved placeholder"):
            RENDERER.render_brief(candidate)

    def test_invalid_task_and_path_inputs_fail(self):
        invalid_task = metadata()
        invalid_task["task_id"] = "../escape"
        with self.assertRaises(RENDERER.RenderError):
            RENDERER.render_brief(invalid_task)

        invalid_artifact = metadata()
        invalid_artifact["artifact_path"] = "../report.md"
        with self.assertRaises(RENDERER.RenderError):
            RENDERER.render_brief(invalid_artifact)

        invalid_scope = metadata()
        invalid_scope["scope"] = ["src/../outside.py"]
        with self.assertRaises(RENDERER.RenderError):
            RENDERER.render_brief(invalid_scope)

    def test_credential_like_content_fails(self):
        candidate = metadata()
        candidate["notes"] = ["api_key: abcdefghijklmnop"]
        with self.assertRaisesRegex(RENDERER.RenderError, "credential-like"):
            RENDERER.render_brief(candidate)

    def test_repository_process_launches_use_the_bounded_helper(self):
        launch_names = {"run", "Popen", "check_call", "check_output"}
        direct_calls = []
        candidates = sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py"))
        for path in candidates:
            if path == BOUNDED_PROCESS_PATH:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr not in launch_names:
                    continue
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                    direct_calls.append(f"{path}:{node.lineno}")
        self.assertEqual([], direct_calls)
        helper_source = BOUNDED_PROCESS_PATH.read_text(encoding="utf-8")
        self.assertIn("start_new_session", helper_source)
        self.assertIn("os.killpg", helper_source)
        self.assertIn("communicate(timeout=", helper_source)

    def test_timeout_cleans_up_the_whole_process_group(self):
        with self.assertRaises(BOUNDED_PROCESS.BoundedProcessTimeout) as caught:
            BOUNDED_PROCESS.run_bounded(
                ["sh", "-c", "trap '' TERM; while :; do sleep 30; done"],
                timeout=0.2,
                grace_timeout=0.1,
            )
        actions = caught.exception.cleanup_actions
        self.assertIn("SIGTERM process group", actions)
        self.assertIn("SIGKILL process group", actions)
        self.assertIn("reaped root process", actions)

    def test_installed_smoke_is_finite_and_not_recursive(self):
        source = SMOKE_ENTRYPOINT.read_text(encoding="utf-8")
        lowered = source.lower()
        for forbidden in ("unittest", "pytest", "discover", "install.sh", "subprocess"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)
        tree = ast.parse(source, filename=str(SMOKE_ENTRYPOINT))
        imported_names = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("tests", imported_names)
        self.assertIn("render_brief", imported_names)

        test_tree = ast.parse(TEST_SOURCE.read_text(encoding="utf-8"), filename=str(TEST_SOURCE))
        fresh_install_test = next(
            node
            for node in ast.walk(test_tree)
            if isinstance(node, ast.FunctionDef) and node.name == "test_fresh_install_contains_runtime_package"
        )
        fresh_install_source = ast.get_source_segment(
            TEST_SOURCE.read_text(encoding="utf-8"), fresh_install_test
        )
        self.assertIsNotNone(fresh_install_source)
        for forbidden in ("unittest discover", "pytest", "discover"):
            self.assertNotIn(forbidden, fresh_install_source.lower())
        self.assertIn("smoke_installed_package.py", fresh_install_source)
        self.assertEqual(fresh_install_source.count("run_bounded"), 2)

    def test_cli_writes_atomically_and_example_has_no_local_path(self):
        example = json.loads((ROOT / "templates" / "example-metadata.json").read_text(encoding="utf-8"))
        rendered = RENDERER.render_brief(example)
        self.assertNotIn("/home/", rendered)
        self.assertNotIn("${", rendered)
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "brief.md"
            completed = BOUNDED_PROCESS.run_bounded(
                [
                    "python3",
                    str(RENDERER_PATH),
                    "--metadata",
                    str(ROOT / "templates" / "example-metadata.json"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), rendered)

    def test_fresh_install_contains_runtime_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "installed-skill"
            completed = BOUNDED_PROCESS.run_bounded(
                [str(INSTALLER), str(destination)],
                cwd=ROOT,
                env={**os.environ, "HOME": temp_dir},
                timeout=15,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            expected = [
                "SKILL.md",
                "README.md",
                "install.sh",
                "references/lifecycle-and-handoff.md",
                "references/roles-and-gates.md",
                "references/delivery-and-safety.md",
                "templates/core.md.tmpl",
                "templates/metadata-contract.json",
                "templates/example-metadata.json",
                "profiles/developer.json",
                "profiles/reviewer.json",
                "profiles/investigation.json",
                "profiles/design.json",
                "scripts/render_brief.py",
                "scripts/bounded_process.py",
                "scripts/smoke_installed_package.py",
                "tests/test_render_brief.py",
            ]
            for relative in expected:
                with self.subTest(relative=relative):
                    self.assertTrue((destination / relative).is_file(), relative)
            smoke = BOUNDED_PROCESS.run_bounded(
                [sys.executable, str(destination / "scripts/smoke_installed_package.py")],
                cwd=destination,
                timeout=10,
            )
            self.assertEqual(smoke.returncode, 0, smoke.stderr)
            self.assertIn("fresh-install smoke ok", smoke.stdout)


if __name__ == "__main__":
    unittest.main()
