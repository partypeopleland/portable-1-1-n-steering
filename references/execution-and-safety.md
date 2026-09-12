# Execution, evidence, and safety

## Before execution

The main window checks Owner authorization, the exact plan digest, reviewer dispatch and
model evidence, a matching `LGTM`, scope/exclusions, dirty or untracked overlap, rollback,
and every planned check. Any missing item, digest change, unresolved finding, conflict,
or permission problem is a safe stop.

## During execution

- Start with the smallest verifiable slice and do not expand scope because a search,
  dependency, or test suggests more work.
- Preserve unrelated dirty/untracked files and name every actual change.
- Read, search, tests, and diff checks are normally safe; deployment, restart, secrets,
  permissions, data deletion, or online mutation needs explicit Owner authorization even
  after plan review.
- Source-only, fixture, and offline evidence must not be described as live or deployed.

## Close and publish

`report.md` records commands and results, tests, precise diff, limitations, rollback,
unfinished work, and status markers. The main window performs one bounded acceptance
check against plan, review, workspace, and required runtime evidence.

Only after required checks, `LGTM`, and acceptance may the exact repository/branch/remote
paths be published. Inspect status and diff, verify remote divergence, stage only listed
paths, run staged checks, inspect the complete staged diff, create a normal commit, push
without force, and verify local/tracking/remote SHAs. Never use merge, rebase, amend,
reset, force push, or a tag to bypass a gate.

## Stop and rollback

On an unknown, conflict, failed check, dirty overlap, missing authorization, remote
divergence, or irreversible risk, stop new mutations and preserve plan/review/report/logs
and any reproducible candidate. Roll back only with the exact snapshot or reversible
operation named in the plan; never use a broad reset or deletion to hide a failure.
