---
name: plan-gated-execution
description: Require a written plan and an independent review gate before substantive implementation, debugging, design, documentation, tests, deployment, or external mutation; choose a frontier reviewer or a multi-reviewer fallback by risk, then let the main task window execute and accept the scoped work.
---

# Plan-Gated Execution

這個 Skill 要求主工作視窗在實質工作前建立 task-local `plan.md`，固定 revision／SHA-256，
先依風險選擇 review mode，再呼叫獨立 read-only reviewer。高風險或風險未知需要
frontier reviewer；低／中風險在 frontier 不可用時，至少要有兩個不同 identity／provider
的核准 fallback reviewer。Host 可用的 fallback adapter 是 `agy`（`gemini-3.8-flash-high`）與
`devin`（`swe-2-high`／`SWE-2 high`）。
若主工作視窗無法判斷風險或能力等價性，必須回問 Owner；不能猜測或以單一弱 reviewer
代替。所有 reviewer 都要在獨立 artifact 以零 blocker／high finding 回覆精確 `LGTM`，
否則主視窗不得執行 substantive mutation。

完整 normative rules：

- [protocol](references/protocol.md)
- [review contract](references/review-contract.md)
- [execution and safety](references/execution-and-safety.md)

可選工具：

```sh
python3 scripts/render_plan.py --metadata templates/example-plan.json
python3 scripts/validate_plan_gate.py --plan plan.md --review plan-review.md --dispatch dispatch.json
```

工具與 package tests 是 source/package evidence，不代表任何 runtime、部署或外部服務已驗證。
安裝器不會刪除既有技能或 runtime copy。
