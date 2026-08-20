# Portable 1:1:N steering

This repository is a small, self-contained document package for the portable 1:1:N／Herdr collaboration rules. Its local copy helper has no network, state, or version-management logic.

## Files

- `AGENTS.md` — root instruction entry point.
- `docs/agent/1-1-n/` — the four linked module documents.
- `install.sh` — conservative local copy helper.

## Quick Start

From this checkout, pass an existing workspace directory to the helper:

```sh
./install.sh /absolute/path/to/workspace
```

The helper accepts exactly one workspace path. It stops if the path is missing or not a directory, or if `AGENTS.md` or any module file already exists. It never overwrites or merges existing content. After a successful copy, restart the Agent session before doing work.

## Manual copy

The same five files can be copied by hand without running a helper:

```sh
mkdir -p /absolute/path/to/workspace/docs/agent/1-1-n
cp AGENTS.md /absolute/path/to/workspace/AGENTS.md
cp docs/agent/1-1-n/INDEX.md /absolute/path/to/workspace/docs/agent/1-1-n/INDEX.md
cp docs/agent/1-1-n/roles-and-gates.md /absolute/path/to/workspace/docs/agent/1-1-n/roles-and-gates.md
cp docs/agent/1-1-n/lifecycle-and-handoff.md /absolute/path/to/workspace/docs/agent/1-1-n/lifecycle-and-handoff.md
cp docs/agent/1-1-n/delivery-and-safety.md /absolute/path/to/workspace/docs/agent/1-1-n/delivery-and-safety.md
```
