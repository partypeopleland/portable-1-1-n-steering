# AI Runbook：1:1:N／Herdr

本文件是給 AI 的執行規則。使用 MUST／MUST NOT 判讀硬性要求；不要把這份文件當成人類教學或 runtime proof。

## 0. 啟用條件

只有符合下列任一條件才啟用 1:1:N：

- 使用者明確提到 `1:1:N`、`1-1-n`、`Herdr` 或多 Agent 派工。
- 使用者明確要求跨模組、多角色協作和獨立驗收。

一般單檔修改、單純 Git 操作、簡單診斷，不得自行啟用多 Agent 流程。

## 1. 角色與責任

| 角色 | MUST 做 | MUST NOT 做 |
| --- | --- | --- |
| `coordinator` | 確認範圍、授權、brief、依賴、handoff、驗收和回報 | 不把 worker 的實作細節當成自己的工作範圍 |
| `developer` | 只改 brief 授權的檔案，留下 report、marker 和檢查結果 | 不自行擴大範圍、開第二個 CLI、部署或修改 Secret |
| `reviewer` | 以唯讀方式檢查需求、標準、diff 和證據 | 不修改 product、測試、runtime 或 Git |

使用者只和 coordinator 溝通。worker 的完成 marker 不是 acceptance；coordinator 必須重新核對證據。

## 2. Trust gate

在讀取 brief 或執行命令前，先確認：

- exact `cwd`；
- Git remote 和 branch；
- task scope、排除項和 allowed mutations；
- 唯一事實來源是否存在且可讀。

工作區信任提示尚未核對時，狀態是 `blocked`，不是 `working`。來源、範圍或規則缺失時停止，不要用猜測補齊。

## 3. 交接 transport 決策表

「跨視窗交接資訊」包含三種訊息：

1. coordinator → worker assignment；
2. worker → coordinator completion handoff；
3. coordinator → worker correction／review handoff。

Coordinator 在 dispatch 前 MUST 先讀取 current Herdr CLI help，解析一個實際支援的
assignment／completion transport 與精確 coordinator target，並將這個已解析的 transport
和 target 寫入 task-specific brief；不得把候選 subcommand 留給 worker 在完成 artifact
後探測。若 CLI 沒有 `agent prompt`，必須在 dispatch 前選定 ordinary-pane atomic
`herdr pane run <target-pane> "<message>"` seam。

| 目標 | 正常 transport | 禁止混淆 |
| --- | --- | --- |
| Herdr 已辨識且可用的 live agent | `herdr agent prompt <agent-or-pane> "<message>"` | 不把 pane label 當成 native agent identity |
| 已存在的 ordinary interactive pane | `herdr pane run <target-pane> "<message>"`，每次只送一次 | 不拆成 `send-text` 加 `send-keys Enter` |
| 啟動 shell／CLI process | `herdr pane run <pane-id> <command>...` | 這不是 handoff，也不是 readiness 或完成證據 |

只有 atomic `pane run` 和 native `agent prompt` 都不可用時，才可明確標記 compatibility recovery，對 ordinary pane 將 raw split pair 嘗試一次。該嘗試必須 at-most-once，並在 artifact／report 記錄失敗；不得補第二次 Enter、重送、輪詢或宣稱 runtime 已驗證。

任何 transport 成功都只代表訊息寫入 API，不代表對方已讀、已執行或已完成。

## 4. 工作生命週期

### Coordinator

1. 建立 brief：目標、範圍、排除項、allowed mutations、checks、artifact path、completion marker。
2. 在 dispatch 前完成 CLI-help preflight，並將 resolved transport 與 coordinator target 寫入 brief；只在 ready、idle、沒有其他 turn 的可見 pane 派工。
3. 需要修正時使用同一套已解析的 atomic handoff transport；不另開重複任務，也不讓 worker 探測替代 subcommand。
4. 收到 handoff 後做一次 bounded liveness check，再關閉已完成 worker pane。
5. 讀取 report／review，核對 diff、測試、限制、敏感資訊和 runtime boundary。

### Worker

1. 先通過 trust gate，再讀 brief 和唯一事實來源。
2. 只使用 assigned pane 和 foreground command；不得開 subagent、第二個 CLI、watcher、background agent 或額外 pane。
3. 先在 artifact 同一目錄寫 temp file，完成檢查與 marker，再 atomic rename 成 `report.md`／`review.md`。
4. 只做一次 applicable atomic completion handoff，然後停止工作；不得自行關閉或重用 pane。

## 5. Artifact 合約

`report.md`／`review.md` 至少要包含：

- task ID、role、source pin 和工作目錄；
- 實際修改檔案與未修改的排除項；
- 命令、測試結果和失敗分類；
- 未執行的 runtime／deploy／Secret／Discord 動作；
- 敏感資料處理方式；
- 最終 completion marker。

「source-only」、「planned」或文件中的描述，不得寫成「current」或「已在 runtime 驗證」。

## 6. Git 與外部 mutation

- 保留既有 dirty／untracked，不得 reset、clean 或覆蓋不相關工作。
- commit／push 前必須完成必要驗收，且只 stage 精確授權檔案。
- deploy、restart、Secret、Discord、資料庫或其他外部 mutation 必須有明確授權。
- 不得把成功 commit、API write 或文件 marker 當成 deploy／runtime 成功證據。

## 7. 快速停止條件

遇到以下任一情況，停止並回報具體 blocker：

- cwd、remote、branch 或 scope 不符合 brief；
- 唯一事實來源缺失、不可讀或互相矛盾；
- transport seam 不可用且 compatibility recovery 未被授權；
- report／review 不能 atomic rename，或缺少 marker；
- 發現未授權檔案、Secret、runtime 或外部 mutation；
- 測試／審查出現未處理的 blocking finding。
