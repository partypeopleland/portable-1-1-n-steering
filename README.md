# 1:1:N / Herdr Collaboration Skill

This repository provides the portable **1:1:N / Herdr Collaboration Skill** for AI coding assistants (such as Antigravity, Claude Code, Codex, and other Agent Skills-compatible harnesses).

## What is 1:1:N / Herdr?

A structured multi-agent coordination protocol designed for complex, high-rigor development tasks. It decouples high-level scope/acceptance coordination from deep, visible worker execution:

- **1 Coordinator**: The single user-facing agent handling scoping, task briefs, and final acceptance.
- **N Workers**: Dedicated execution units (developer writers, independent reviewers) running in visible, interactive panes with strict evidence deliverables.

## Structure

```text
herdr-1-1-n/
├── SKILL.md                          # Main skill entry point with YAML frontmatter & lifecycle
├── install.sh                        # Installation helper script
└── references/                       # Detailed sub-protocols (lazy-loaded on demand)
    ├── roles-and-gates.md            # Roles, model tiers, and N-gate policies
    ├── lifecycle-and-handoff.md      # Herdr layout, brief/report contracts & dispatch
    └── delivery-and-safety.md        # Evidence verification & safe Git delivery gates
```

## Installation

### 1. Install to Personal Skills (`~/.agents/skills/`)

Run without arguments to install directly to `$HOME/.agents/skills/herdr-1-1-n`:

```sh
./install.sh
```

### 2. Install to a Specific Workspace

Pass the workspace path to install locally into `<workspace>/.agents/skills/herdr-1-1-n`:

```sh
./install.sh /path/to/workspace
```

## How to Trigger

The skill is model-invoked on-demand and triggers when:
- The user explicitly mentions `1:1:N`, `1-1-n`, `Herdr`, or `多 Agent 派工`.
- The user requests complex multi-agent dispatch with formal brief/report/review and delivery gates.

Routine tasks (simple edits, single-command checks, `git commit`) will **not** trigger this skill, ensuring fast and lean execution for everyday tasks.
