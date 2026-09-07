# AI Runbook：1:1:N／Herdr

本文件是給 AI 的執行索引與決策摘要。使用 MUST／MUST NOT 判讀硬性要求；不要把這份文件當成人類教學或 runtime proof。完整 operational rules 以 [`../references/roles-and-gates.md`](../references/roles-and-gates.md)、[`../references/lifecycle-and-handoff.md`](../references/lifecycle-and-handoff.md) 與 [`../references/delivery-and-safety.md`](../references/delivery-and-safety.md) 為準。

## 0. 啟用條件

只有符合下列任一條件才啟用 1:1:N：

- 使用者明確提到 `1:1:N`、`1-1-n`、`Herdr` 或多 Agent 派工。
- 使用者明確要求跨模組、多角色協作和獨立驗收。

一般單檔修改、單純 Git 操作、簡單診斷，不得自行啟用多 Agent 流程。

## 1. 角色與 canonical route

| 角色 | MUST 做 | MUST NOT 做 |
| --- | --- | --- |
| `coordinator` | 確認範圍、授權、brief、依賴、handoff、驗收和回報 | 不把 worker 的實作細節當成自己的工作範圍 |
| `developer` | 只改 brief 授權的檔案，留下 report、marker 和檢查結果 | 不自行擴大範圍、開第二個 CLI、部署或修改 Secret |
| `reviewer` | 以唯讀方式檢查需求、標準、diff 和 evidence | 不修改 product、測試、runtime 或 Git |

角色、N gate、能力選擇與 publication gate 讀 [`roles-and-gates.md`](../references/roles-and-gates.md)；dispatch、handoff、anomaly recovery 與 pane cleanup 讀 [`lifecycle-and-handoff.md`](../references/lifecycle-and-handoff.md)；artifact、resource checkpoint、acceptance 與 Git safety 讀 [`delivery-and-safety.md`](../references/delivery-and-safety.md)。

## 2. Trust gate

在讀取 brief 或執行命令前，先確認：

- exact `cwd`；
- Git remote 和 branch；
- task scope、排除項和 allowed mutations；
- 唯一事實來源是否存在且可讀。

工作區信任提示尚未核對時，狀態是 `blocked`，不是 `working`。來源、範圍或規則缺失時停止，不要用猜測補齊。

## 3. 交接 transport preflight

「跨視窗交接資訊」包含三種訊息：

1. coordinator → worker assignment；
2. worker → coordinator completion handoff；
3. coordinator → worker correction／review handoff。

Coordinator 在 dispatch 前 MUST 先讀取 current Herdr CLI help，解析一個實際支援的 assignment／completion transport 與精確 coordinator target，並將這個已解析的 transport 和 target 寫入 task-specific brief；不得把候選 subcommand 留給 worker 在完成 artifact 後探測。若 CLI 沒有 `agent prompt`，必須在 dispatch 前選定 ordinary-pane atomic `herdr pane run <target-pane> "<message>"` seam。

| 目標 | 正常 transport | 禁止混淆 |
| --- | --- | --- |
| Herdr 已辨識且可用的 live agent | `herdr agent prompt <agent-or-pane> "<message>"` | 不把 pane label 當成 native agent identity |
| 已存在的 ordinary interactive pane | `herdr pane run <target-pane> "<message>"`，每次只送一次 | 不拆成 `send-text` 加 `send-keys Enter` |
| 啟動 shell／CLI process | `herdr pane run <pane-id> <command>...` | 這不是 handoff，也不是 readiness 或完成證據 |

只有 atomic `pane run` 和 native `agent prompt` 都不可用時，才可明確標記 compatibility recovery，對 ordinary pane 將 raw split pair 嘗試一次。該嘗試必須 at-most-once，並在 artifact／report 記錄失敗；不得補第二次 Enter、重送、輪詢或宣稱 runtime 已驗證。

任何 transport 成功都只代表訊息寫入 API，不代表對方已讀、已執行或已完成。上述 preflight 是本 runbook 保留的 remote handoff contract；完整 lifecycle 與 cleanup 以 [`lifecycle-and-handoff.md`](../references/lifecycle-and-handoff.md) 為唯一 source。

## 4. 工作生命週期摘要

Coordinator 先建立 brief，完成 CLI-help preflight，寫入 resolved transport／target，確認 pane ready／idle 且沒有其他 turn，再派工。收到 handoff 後只做一次 bounded liveness check，依 canonical cleanup gate 處理 completed pane，再核對 report／review、diff、checks、文件與 runtime boundary。

Worker 先通過 trust gate，只使用 assigned pane 與 foreground command，先以 temp + atomic rename 完成 artifact 與 marker，再依 brief 指定的 transport 做一次 applicable handoff，然後停止工作；不得探測替代 subcommand、輪詢、重送或自行關閉 pane。

## 5. Artifact、resource 與 evidence route

`report.md`／`review.md` 至少要包含 task ID、role、source pin、工作目錄、精確修改與排除項、命令結果、限制、未執行的 runtime／external actions、敏感資料處理方式與 completion marker。resource checkpoint 只作 provider-neutral prose hook；不新增 metadata key、profile field、renderer behavior、daemon 或 watcher。

這些規則的完整版本在 [`delivery-and-safety.md`](../references/delivery-and-safety.md)。source-only、planned 或 offline evidence 不得寫成 current、deployed 或 runtime verified。

## 6. Git 與外部 mutation 摘要

- 保留既有 dirty／untracked，不得 reset、clean 或覆蓋不相關工作。
- commit／push 前必須完成必要驗收，且只 stage 精確授權檔案。
- deploy、restart、Secret、Discord、資料庫或其他外部 mutation 必須有明確授權。
- 不得以 merge、rebase、amend、reset、force push 或 tag 改寫歷史來繞過 publication gate。

完整 Git safety 與 publication gate 讀 [`delivery-and-safety.md`](../references/delivery-and-safety.md)。

## 7. 快速停止條件

遇到以下任一情況，停止並回報具體 blocker：

- cwd、remote、branch 或 scope 不符合 brief；
- 唯一事實來源缺失、不可讀或互相矛盾；
- resolved transport seam 不可用且 compatibility recovery 未被授權；
- report／review 不能 atomic rename，或缺少 marker；
- 發現未授權檔案、Secret、runtime 或外部 mutation；
- 測試／審查出現未處理的 blocking finding。
