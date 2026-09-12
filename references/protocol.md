# Plan-Gated Execution protocol

This package has one operating rule: the main task window writes and owns the plan,
selects a review mode by risk, gets the required independent review evidence, then executes
the approved plan itself. There is no required worker pool, pane layout, or worker handoff.

## Required sequence

1. Classify the request. Conversation and a bounded read-only lookup may skip a plan;
   implementation, debugging, design, formal documentation, tests, deployment, data,
   permission, Git, or external mutation is substantive work.
2. Before the first substantive mutation, create a task-local `plan.md` using the
   required fields in [`plan.md.tmpl`](../templates/plan.md.tmpl). Write it to a temporary
   file in the same directory and atomically rename it. Record a revision and SHA-256.
3. The plan records `risk_tier`, `review_mode`, and `review_rationale`:
   - `frontier-single` is one exact `gpt-6-astra` or `gpt-5.6-sol` reviewer.
   - `dual-fallback` is at least two approved, independent provider/model pairs. The
     portable Host examples are `agy` with model `gemini-3.8-flash-high` and `devin`
     with model `swe-2-high` (`SWE-2 high` capability); both must be represented by
     real dispatch evidence, not an unverified string.
   - `owner-choice` is a stop state. If the main window cannot judge whether frontier
     capability is necessary or whether fallback is equivalent, it asks the Owner which
     reviewer/mode to use, records the answer, revises the plan, and reopens review.
     `high` or `unknown` risk cannot silently use dual fallback.
4. The main window calls the number of independent reviewers required by the mode, providing
   the plan path, digest, sources, and a read-only restriction. Each reviewer writes a separate
   artifact with matching identity, provider/model/capability, digest, blocker counts, and an
   exact `LGTM` marker. A changed plan, a missing artifact, an unresolved blocker, duplicate
   identity/provider, or unverifiable capability keeps the gate closed.
5. The main window executes the plan, records actual versus planned work, and may use
   additional subagents only for bounded read-only work explicitly listed in the plan.
   No hidden worker pool, background watcher, unbounded polling, or unreviewed workflow
   may be introduced.
6. The main window writes `report.md`, runs the planned checks, and performs acceptance.
   `LGTM`, a completion marker, or passing tests is evidence, not automatic acceptance.

## Authorization boundary

Owner authorization, reviewer approval, execution, and final acceptance are separate
decisions. Review approval never authorizes deployment, restart, secrets, data deletion,
permissions, history rewriting, or another external mutation. Existing dirty and
untracked work stays untouched unless the plan explicitly names it.

## Status vocabulary

Use `current`, `planned`, `historical`, and `runtime unknown` precisely. Use `BLOCKED`
when a source, authorization, model identity, digest, check, or rollback is unavailable;
do not silently substitute a weaker process.
