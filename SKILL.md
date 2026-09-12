---
name: plan-gated-execution
description: Require a written plan and an independent high-capability, read-only subagent LGTM before substantive implementation, debugging, design, documentation, tests, deployment, or external mutation; then let the main task window execute and accept the scoped work.
---

# Plan-Gated Execution

這個 Skill 要求主工作視窗在實質工作前建立 task-local `plan.md`，固定 revision／SHA-256，
再自行呼叫一名獨立高能力 subagent 只做計畫審核。預設 validator 只接受可核對的
`gpt-6-astra` 或 `gpt-5.6-sol`；其他更高模型需先完成獨立 allowlist review，並在獨立
artifact 以零 blocker／high finding 回覆精確 `LGTM`；否則
主視窗不得執行 substantive mutation。

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
