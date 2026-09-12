# Plan review contract

## Request

The main window sends one bounded request containing the task id, exact `plan.md` path,
plan SHA-256, necessary sources, review artifact path, and the read-only boundary. The
dispatch record must preserve the model actually selected; fields not exposed by the
calling API remain unknown rather than inferred.

The default validator recognizes the exact model identifiers `gpt-6-astra` and
`gpt-5.6-sol`. A different or higher model requires a separately reviewed validator
allowlist change with verifiable capability evidence; a version-looking name alone is
not enough. The reviewer must not execute the plan, modify product/source/configuration/runtime/Git,
deploy, restart, read secrets, start a watcher, or dispatch another agent.

## Required artifact

Write the artifact atomically in the review task directory:

```text
task: <id>
plan_revision: <revision>
plan_sha256: <sha256>
reviewer_model: <actual model>
scope: read-only
blockers: 0
high_findings: 0
findings: <summary or none>
required_changes: <none or exact changes>
conclusion: LGTM | REQUEST_CHANGES | BLOCKED
marker: LGTM | PLAN_REVIEW_BLOCKED
```

`LGTM` is valid only when the digest matches, the dispatch model and artifact model are
byte-exact identical and meet the capability floor, the review stayed read-only, and both blocker
and high-finding counts are zero. It opens
the execution gate for that exact revision; it does not announce completion.
