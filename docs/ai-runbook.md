# AI Runbook：Plan-Gated Execution

本文件是給 AI 的執行索引與決策摘要。使用 MUST／MUST NOT 判讀硬性要求；不要把這份文件
當人類教學或 runtime proof。完整 rules 以 [`../references/protocol.md`](../references/protocol.md)、
[`../references/review-contract.md`](../references/review-contract.md) 與
[`../references/execution-and-safety.md`](../references/execution-and-safety.md) 為準。

## 0. 分類

以下是 substantive work，MUST 先建立 plan：implementation、debugging、design、正式文件、
tests、deploy、restart、Secret、資料／權限、Git 或其他 external mutation。純對話和 bounded
read-only lookup 可略過；轉成變更時立即停下補 plan。

## 1. Review mode selection

主工作視窗 MUST 在 plan 中填 `risk_tier`（`low`／`medium`／`high`／`unknown`）、
`review_mode`（`frontier-single`／`dual-fallback`／`owner-choice`）與判斷理由。

- `high` 或 `unknown`：需要一名可核對 frontier reviewer；不可用時停止並請 Owner
  指定今天的 reviewer／模式。
- `low` 或 `medium`：frontier 可用時可使用單一 frontier；不可用且能力等價性足夠時，
  可使用至少兩名獨立 fallback。Host 的明確 adapter/model/capability labels 是 `agy`／`gemini-3.8-flash-high`／`agy-high-plan-review` 與 `devin`／`swe-2-high`／`SWE-2 high`。
- 主工作視窗無法判斷風險、是否需要最強模型或 fallback 是否等價：使用 `owner-choice`，
  先取得 Owner 決定，再重修 plan 並重新 review。`owner-choice` 不會通過 gate。

fallback reviewer 必須有不同 `reviewer_id` 與 `provider`，每人只讀同一份 plan，且每份
review 都要 `LGTM`；一份缺失、身份重複、能力不在 allowlist 或 digest 不同都 fail closed。

## 2. Plan gate

主工作視窗 MUST 在第一個 substantive mutation 前以 atomic write 建立 task-local `plan.md`，
列出目標、scope、exclusions、sources、依賴、步驟、risk tier、review mode、判斷理由、
授權／風險、validation、rollback、deliverables 與 acceptance；固定 revision／SHA-256，
plan substantive change 後重新審核。

## 3. Independent review

主工作視窗 MUST 依 plan mode 呼叫一名 frontier reviewer，或至少兩名獨立 fallback reviewer，
提供 plan path／digest、必要來源與 read-only 限制。frontier MUST 使用 validator 可核對的
`gpt-6-astra` 或 `gpt-5.6-sol`；fallback MUST 使用已核准的 provider/model/capability
pair。其他更高模型或 adapter 只有在先完成獨立 allowlist review 並提供 capability evidence
時才可使用；每名 reviewer 只寫自己的獨立 review artifact。
Artifact MUST 有 matching digest、`scope: read-only`、`blockers: 0`、`high_findings: 0`、
`conclusion: LGTM`、`marker: LGTM`。

digest 不符、model／provider／identity／能力未知、review 有 blocker、artifact 缺失或
reviewer 越界時，狀態是 `BLOCKED`，不得執行。LGTM 只解除該 revision 的 plan gate，不是
Owner mutation 授權或 final acceptance。

## 4. Main execution and close

主工作視窗直接執行 plan，保持 actual／planned／historical／runtime unknown 分類；可選
subagent 只能做 plan 明列的 bounded read-only 工作，不建立 hidden worker pool、watcher 或
無界 polling。執行後寫 `report.md`，執行 planned checks，做一次 bounded acceptance。

## 5. Safety and publication

保留 dirty／untracked；deploy、restart、Secret、資料／權限與 online mutation 需要 Owner 明確
授權。未完成 checks、LGTM 與 acceptance，不得 commit／push。發佈時只 stage 精確 paths，
核對 remote divergence，正常 commit／non-force push 並驗證 SHA；禁止 history rewrite。

## 6. 快速停止條件

遇到以下任一情況，停止並回報具體 blocker：授權、source、scope、plan digest、reviewer model
或 rollback 不可驗證；reviewer 不是 read-only、沒有精確 LGTM 或有未處理 finding；發現未授權
檔案、Secret、runtime／external mutation 或 dirty overlap；測試、diff、link、sensitive scan、
remote divergence 或 acceptance 失敗。
