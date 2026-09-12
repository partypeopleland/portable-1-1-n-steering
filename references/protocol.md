# Plan-Gated Execution protocol

This package has one operating rule: the main task window writes and owns the plan,
gets an independent high-capability review, then executes the approved plan itself.
There is no required worker pool, pane layout, or coordinator/worker handoff.

## Required sequence

1. Classify the request. Conversation and a bounded read-only lookup may skip a plan;
   implementation, debugging, design, formal documentation, tests, deployment, data,
   permission, Git, or external mutation is substantive work.
2. Before the first substantive mutation, create a task-local `plan.md` using the
   required fields in [`plan.md.tmpl`](../templates/plan.md.tmpl). Write it to a temporary
   file in the same directory and atomically rename it. Record a revision and SHA-256.
3. The main window calls one independent subagent with the plan path, digest, sources,
   and a read-only restriction. The reviewer must be Astra, GPT-5.6 Sol, or a clearly
   higher-capability equivalent. Record the actual model and dispatch evidence; an
   unavailable identity is a stop condition.
4. The reviewer writes a separate `plan-review.md`. It must contain the matching digest,
   read-only scope, model evidence, blocker counts, and an exact `LGTM` marker. A changed
   plan, a missing artifact, an unresolved blocker, or an unverifiable model keeps the
   gate closed.
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
