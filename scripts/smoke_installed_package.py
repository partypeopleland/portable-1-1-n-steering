#!/usr/bin/env python3
"""Run a finite contract check against the installed package root."""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXPECTED_FILES = (
    "SKILL.md",
    "README.md",
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
)


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    missing = [relative for relative in EXPECTED_FILES if not (package_root / relative).is_file()]
    if missing:
        print(f"fresh-install smoke failed: missing {', '.join(missing)}", file=sys.stderr)
        return 1

    metadata_path = package_root / "templates" / "example-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        sys.path.insert(0, str(package_root / "scripts"))
        import render_brief

        rendered = render_brief.render_brief(metadata)
    except (OSError, json.JSONDecodeError, ValueError, ImportError) as exc:
        print(f"fresh-install smoke failed: {exc}", file=sys.stderr)
        return 1

    if not rendered.strip() or "${" in rendered or "Profile: `developer`" not in rendered:
        print("fresh-install smoke failed: rendered example contract is invalid", file=sys.stderr)
        return 1

    print(f"fresh-install smoke ok: {len(EXPECTED_FILES)} files; example rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
