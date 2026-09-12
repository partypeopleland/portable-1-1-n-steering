# AI Runbook：Plan-Gated Execution

本文件是給 AI 的執行索引與決策摘要。使用 MUST／MUST NOT 判讀硬性要求；不要把這份文件
當人類教學或 runtime proof。完整 rules 以 [`../references/protocol.md`](../references/protocol.md)、
[`../references/review-contract.md`](../references/review-contract.md) 與
[`../references/execution-and-safety.md`](../references/execution-and-safety.md) 為準。

## 0. 分類

以下是 substantive work，MUST 先建立 plan：implementation、debugging、design、正式文件、
tests、deploy、restart、Secret、資料／權限、Git 或其他 external mutation。純對話和 bounded
read-only lookup 可略過；轉成變更時立即停下補 plan。

## 1. Plan gate

主工作視窗 MUST 在第一個 substantive mutation 前以 atomic write 建立 task-local `plan.md`，
列出目標、scope、exclusions、sources、依賴、步驟、授權／風險、validation、rollback、
deliverables 與 acceptance；固定 revision／SHA-256，plan substantive change 後重新審核。

## 2. Independent review

主工作視窗 MUST 呼叫一名獨立 subagent，提供 plan path／digest、必要來源與 read-only 限制。
Reviewer MUST 使用 validator 可核對的 `gpt-6-astra` 或 `gpt-5.6-sol`；其他更高模型
只有在先完成獨立 allowlist review 並提供 capability evidence 時才可使用，且只寫獨立
`plan-review.md`。
Artifact MUST 有 matching digest、`scope: read-only`、`blockers: 0`、`high_findings: 0`、
`conclusion: LGTM`、`marker: LGTM`。

digest 不符、model 身份／能力未知、review 有 blocker、artifact 缺失或 reviewer 越界時，狀態
是 `BLOCKED`，不得執行。LGTM 只解除該 revision 的 plan gate，不是 Owner mutation 授權或
final acceptance。

## 3. Main execution and close

主工作視窗直接執行 plan，保持 actual／planned／historical／runtime unknown 分類；可選
subagent 只能做 plan 明列的 bounded read-only 工作，不建立 hidden worker pool、watcher 或
無界 polling。執行後寫 `report.md`，執行 planned checks，做一次 bounded acceptance。

## 4. Safety and publication

保留 dirty／untracked；deploy、restart、Secret、資料／權限與 online mutation 需要 Owner 明確
授權。未完成 checks、LGTM 與 acceptance，不得 commit／push。發佈時只 stage 精確 paths，
核對 remote divergence，正常 commit／non-force push 並驗證 SHA；禁止 history rewrite。

## 5. 快速停止條件

遇到以下任一情況，停止並回報具體 blocker：授權、source、scope、plan digest、reviewer model
或 rollback 不可驗證；reviewer 不是 read-only、沒有精確 LGTM 或有未處理 finding；發現未授權
檔案、Secret、runtime／external mutation 或 dirty overlap；測試、diff、link、sensitive scan、
remote divergence 或 acceptance 失敗。
