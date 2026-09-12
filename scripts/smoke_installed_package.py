#!/usr/bin/env python3
"""Run a finite fresh-install contract check without invoking a test runner."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def load_renderer():
    path = ROOT / "scripts" / "render_plan.py"
    spec = importlib.util.spec_from_file_location("installed_plan_renderer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load plan renderer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    required = (
        "SKILL.md",
        "README.md",
        "references/protocol.md",
        "references/review-contract.md",
        "references/execution-and-safety.md",
        "scripts/render_plan.py",
        "scripts/validate_plan_gate.py",
        "templates/plan.md.tmpl",
        "templates/example-plan.json",
    )
    for relative in required:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"missing installed package file: {relative}")
    renderer = load_renderer()
    metadata = json.loads((ROOT / "templates/example-plan.json").read_text(encoding="utf-8"))
    rendered = renderer.render_plan(metadata)
    if "## Execution gate" not in rendered or "${" in rendered:
        raise SystemExit("rendered plan contract is invalid")
    with tempfile.TemporaryDirectory(prefix="plan-gated-smoke-"):
        pass
    print("fresh-install smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
