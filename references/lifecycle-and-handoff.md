# Herdr 版面與任務交接

本檔是 1:1:N／Herdr module 的可見工作格、ready-gated dispatch、brief／report／review、direct handoff 與 coordinator acceptance implementation。Native agent seam 是預設；raw terminal seam 只保留給相容性 fallback。

## Herdr 版面

- `coordinator` 使用獨立且易辨認的主工作格，優先重用既有或 `idle` pane。
- `workers1` 最多四格且固定 2×2；只有前一組全忙且確實需要下一位 worker，才建立下一組，並一次建滿四格 2×2。不要關閉仍在工作的 pane；worker 完成交接後不保留 completed pane 為 `idle`，由 coordinator 依完成清理閘門關閉。
- 一格只執行一個明確 worker 工作。pane ID 是動態資料；brief 可記錄當次 coordinator pane，但 portable 文件不得寫死任何 pane ID。
- 派工前先確認目標 pane 是 `idle`／ready，且不在 CLI／MCP 啟動、trust approval prompt 或其他 task；先以 task ID 標籤 pane，避免 stale／duplicate label 造成重派。
- `herdr agent rename <target> <name>` 是 native agent 的穩定名稱；`herdr pane rename` 只改 display label，不能取代 agent identity。

## 建立任務

每個 task 使用 workspace-relative `.coordination/tasks/<task-id>/`，至少有：

- `brief.md`：目標、範圍、唯一事實來源、限制、驗收、檢查、完成標記與交接對象；可由 `templates/core.md.tmpl` 加 profile metadata 產生。
- `report.md`：developer／investigation／design 的成果、變更或調查證據、檢查、限制與完成標記。
- `review.md`：獨立 reviewer 的唯讀審查與完成標記。

`report`／`review` 是證據，不是自動通過。Coordinator 必須核對 workspace、diff、測試、文件與執行期證據。

長任務的 brief 必須設定 progress timing；若未覆寫，worker 須在 5 分鐘內先交 substantive progress，之後至少每 10 分鐘或到達 meaningful milestone，取先到者。

## Native dispatch 與 bounded startup

### 已辨識的 live agent

用本機 CLI help 所定義的 atomic seam：

```text
herdr agent prompt <agent-name-or-pane-id> "<assignment>"
```

這個命令會一次提交文字與 Enter；它是 recognized live agent 的預設派工方式。可先用：

```text
herdr agent rename <target> <stable-name>
```

不要把 `herdr pane rename` 當成 agent rename；後者只是顯示名稱。完成交接也用同一個 `herdr agent prompt`，不要把 raw pane input 當預設。

### 新 ready shell

當既有 pane 在互動式 shell prompt 且 readiness 可靠時：

```text
herdr agent start <name> --kind <kind> --pane <id>
```

`<kind>` 必須是 CLI help 列出的 supported interactive agent kind。只有在 start 的 ready evidence 可信後，才對該 name 發送一次 native prompt；不要因 pane 存在或舊 spinner 就假設已 ready。

### First-run startup recovery

若 Codex first-run bootstrap 自動更新／自我替換後退出，或在 misleading ready signal 後沒有活著的 agent，狀態必須記為 `startup_failed`。不要 prompt stale target，也不要把它記為 `working`。讓更新完成後，只做一次 bounded clean restart；第二次仍不能取得 native readiness 就停止 native retry。

若 native startup 仍不可用，確認 pane 是 fresh shell，再用 ordinary-process seam：

```text
herdr pane run <pane-id> <command>...
```

這是 shell/process fallback；worker 仍以 report/review artifact 主動交接，coordinator 不靠 polling 補救缺少的 native handoff。

### Startup trust gate

Codex 可能在讀取 brief 前詢問是否信任 working directory。這是 `blocked`，不是 `working`。先核對 exact cwd、預期 Git remote、branch 與 task scope；只有明確授權的 workspace 才能批准，否則停止並報告 blocker。不得盲目回答任意 approval prompt。

## Context reuse gate

Pane reuse 不是單純看到 `idle` 就能重派。先判斷：

1. 舊 turn 是否已安全完成，是否仍可能執行或持有未提交的工具操作。
2. 這個 CLI 是否安全支援 `/new`，以及 reset 後是否能取得 fresh readiness。
3. 舊 context 的內容與 token 狀態是否會污染新 task。

只有舊 turn 已完成且 `/new` 安全時，才 reset、等待 fresh readiness，再派新工作。若 reset 不安全，只有在 pane 已完成且可安全關閉時才 close，之後建立／start fresh pane。不得在舊 turn 可能仍跑時重派；這是 context/token isolation 與 at-most-once 的必要保護。

## Completed worker pane cleanup

Worker 的資源生命週期在 artifact 與 handoff 完成後停止：worker 寫好並 atomic rename `report.md`／`review.md`、發送一次 native completion handoff，接著不再發 work，也不得關閉、操作或重用自己的 pane。Worker 也不得開 subagent、background agent、watcher、second CLI、extra pane/tab、headless task 或 self-dispatch path。

Coordinator 在收到 handoff 後只做一次 bounded liveness check。若確認舊 turn 不再執行、不持有未提交的 tool operation，才由 coordinator 執行：

```text
herdr pane close <pane-id>
```

這個 close 是 coordinator-only，目的是釋放 completed worker CLI/pane 的記憶體；不得在舊 turn 仍可能執行時關閉。完成 subtask 的 pane 預設關閉，不保留為 idle。重用只適用於未完成且仍安全，或已安全 reset 並取得 fresh readiness 的 context；若 handoff 失敗，先在 artifact 記錄失敗，讓 coordinator 決定安全 close/recovery，不重送 handoff，也不留下 watcher。

## Bounded acknowledgement 與 progress

- `herdr agent start` 的 readiness 或 `herdr agent prompt` 的提交證明，只表示該 seam 已接受輸入，不是 worker 完成證明。
- 只做 brief 所需的 bounded startup/readiness check；不要用 completion polling、continuous polling、transcript loop、background watcher 或無界 wait。
- Worker 初次 substantive progress 必須說明目前工作、已完成的 evidence、blocker（若有）與下一個 milestone。純 `OK`／同意／確認不算 progress。
- 若錯過 progress deadline，Coordinator 只做一次 bounded liveness audit，接著給一次 recovery instruction，或記錄 worker 失敗並重新安排；不得重送同一 assignment。

## Worker 完成與 direct handoff

Worker 必須先把 artifact 寫好並完成 marker，再 handoff：

1. 在 artifact 同一目錄建立 temp 檔。
2. 寫入完整 `report.md`／`review.md`、檢查內容與 marker。
3. 以 atomic rename 取代正式 artifact path。
4. 解析名稱或標籤為 `coordinator` 的 live agent，發送**一次**短 native prompt，例如：

   ```text
   herdr agent prompt coordinator "Task <task-id>: artifact <exact-path>; marker <MARKER>. Please continue coordinator acceptance."
   ```

這個 prompt 不使用 `--wait`，也不再補 Enter。成功 API write 不是 coordinator 已讀取的證明，因此不要查詢回覆、輪詢、重送文字或建立 acknowledgement loop。若 native handoff 失敗，在 artifact 如實記錄失敗；最多發一次可見人類通知，不得宣稱 coordinator 已收到。

`herdr pane send-text` 加 `herdr pane send-keys ... Enter` 僅能作為清楚標記的 compatibility/raw-terminal fallback；若 brief 沒有特別授權，不得用它取代 recognized live agent 的 `herdr agent prompt`。

## Coordinator acceptance

Coordinator 只在收到已提交 handoff 後做一次 bounded liveness check，依前述閘門關閉 completed worker CLI/pane，再讀指定報告／審查一次，核對最終 workspace、精確 diff、檢查、文件同步、限制、敏感資訊與必要 runtime evidence。若有未處理 finding 或新增實質工作，回到角色閘門重新派可見 worker；不能把 worker 的完成標記直接當成驗收。
