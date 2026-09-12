# Plan review contract

## Request

The main window sends one bounded request per reviewer containing the task id, exact `plan.md`
path, plan SHA-256, necessary sources, review artifact path, selected `review_mode`, and the
read-only boundary. The dispatch record must preserve the actual reviewer identity, provider,
model, and capability; fields not exposed by the calling API remain unknown rather than inferred.

The default validator recognizes the exact frontier model identifiers `gpt-6-astra` and
`gpt-5.6-sol`. In `dual-fallback`, the default approved pairs are `(agy,
gemini-3.8-flash-high)` and `(devin, swe-2-high)` with their exact capability labels in
the validator: `agy` uses `agy-high-plan-review`, `devin` uses `SWE-2 high`, and
frontier dispatch uses `provider: openai` with `capability: frontier-plan-review`.
A different or
higher model/adapter requires a separately reviewed validator allowlist change with verifiable
capability evidence; a version-looking name alone is not enough. Every reviewer must not execute
the plan, modify product/source/configuration/runtime/Git, deploy, restart, read secrets, start a
watcher, or dispatch another agent.

The main task window chooses `frontier-single` for high or unknown risk. Low or medium risk may use
`dual-fallback` only when at least two reviewer identities and providers are distinct and both
can inspect the same plan independently. If the main task window cannot determine the risk or the
capability equivalence, it records `owner-choice` and asks the Owner; that state cannot open the
execution gate.

## Required artifact

Write one artifact atomically in the review task directory for each reviewer:

```text
task: <id>
plan_revision: <revision>
plan_sha256: <sha256>
reviewer_id: <stable identity>
reviewer_model: <actual model>
review_mode: frontier-single | dual-fallback
provider: <dispatch provider>
capability: <dispatch capability label>
scope: read-only
blockers: 0
high_findings: 0
findings: <summary or none>
required_changes: <none or exact changes>
conclusion: LGTM | REQUEST_CHANGES | BLOCKED
marker: LGTM | PLAN_REVIEW_BLOCKED
```

`LGTM` is valid only when the digest matches, the dispatch identity/provider/model/capability and
artifact fields are byte-exact identical and meet the selected mode, the review stayed read-only,
and both blocker and high-finding counts are zero. `frontier-single` requires exactly one artifact;
`dual-fallback` requires at least two artifacts with distinct identities and providers, and the
validator rejects high or unknown risk in that mode. Every artifact must pass; one failure closes
the gate. LGTM opens the execution gate for that exact revision; it does not announce completion.
