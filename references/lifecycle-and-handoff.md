# Herdr 版面與任務交接

本檔是 public package 中可見工作格、ready-gated dispatch、brief／report／review、bounded acknowledgement、異常 recovery、direct handoff 與 completed-pane cleanup 的唯一 normative source。角色／N gate 見 [`roles-and-gates.md`](roles-and-gates.md)；artifact evidence 與 Git safety 見 [`delivery-and-safety.md`](delivery-and-safety.md)。

## Herdr 版面

- `coordinator` 使用獨立且易辨認的主工作格，優先重用既有或 `idle` pane。
- worker panes 只在確實需要且前一組已滿時擴充；不要關閉仍在工作的 pane。worker 完成交接後，completed pane 依本檔的 cleanup gate 處理。
- 一格只執行一個明確 worker 工作。pane ID 是動態資料；brief 可記錄當次 target，但 portable guidance 不得寫死任何 pane／session instance。
- 派工前先確認目標是 `idle`／ready，且不在 CLI／MCP 啟動、trust approval prompt 或其他 task；先以 task ID 標籤 target，避免 stale／duplicate label 造成重派。

## 建立任務

每個 task 使用 workspace-relative `.coordination/tasks/<task-id>/`，至少有：

- `brief.md`：目標、範圍、唯一事實來源、限制、驗收、檢查、完成標記與交接對象；
- `report.md`：writer／investigation／design 的成果、變更或調查 evidence、檢查、限制與完成標記；
- `review.md`：獨立 reviewer 的唯讀審查與完成標記。

`report`／`review` 是 evidence，不是自動通過。Coordinator 必須核對 workspace、diff、測試、文件與執行期 evidence。長任務的 brief 必須設定 progress timing；若未覆寫，worker 須在五分鐘內先交 substantive progress，之後至少每十分鐘或到達 meaningful milestone，取先到者。

## 跨視窗交接資訊（Cross-window handoff information）

「跨視窗交接資訊」包括三類訊息：coordinator-to-worker assignments、worker-to-coordinator completion handoffs，以及 coordinator-to-worker correction／review handoffs。

Coordinator 在 dispatch 前 MUST 先讀取 current Herdr CLI help，解析一個實際支援的 assignment／completion transport 與精確 coordinator target，並將這個已解析的 transport 和 target 寫入 task-specific brief；不得把候選 subcommand 留給 worker 在完成 artifact 後探測。若 CLI 沒有 `agent prompt`，必須在 dispatch 前選定 ordinary-pane atomic `herdr pane run <target-pane> "<message>"` seam。

當目標是 ordinary interactive pane 時，三類資訊每一項都使用一次 atomic pane handoff：

```text
herdr pane run <target-pane> "<message>"
```

這個 quoted-message 形式只負責把交接資訊送入已存在的 ordinary interactive pane；它不是 shell／CLI startup，也不是 readiness、working、completion 或 runtime verification 的證據。啟動 shell／process 另使用下方的 `herdr pane run <pane-id> <command>...` command form，兩者不得混用或互相當作證據。

若目標是真正已被 Herdr 辨識且仍可用的 live agent，使用 recognized-agent atomic seam：

```text
herdr agent prompt <agent-name-or-pane-id> "<message>"
```

普通 pane 不得把 `pane send-text` 加 `pane send-keys ... Enter` 當正常路徑。只有 atomic `pane run` 與 native `agent prompt` 都不可用時，才可明確標記 compatibility recovery，對 ordinary pane 將 raw `herdr pane send-text ...` 加 `herdr pane send-keys ... Enter` split pair 嘗試一次；必須記錄失敗，不得靜默把 composer 內容視為已提交、補第二次 Enter、重送或宣稱 runtime 已驗證。

## Native dispatch 與 bounded startup

### 已辨識的 live agent

用本機 CLI help 所定義的 native atomic seam，並使用 coordinator 在 dispatch 前解析且寫入 brief 的 exact transport 與 target。`herdr agent prompt` 是 recognized live agent 的交接方式；不要把 pane label 當成 native agent identity。可先用：

```text
herdr agent rename <target> <stable-name>
```

`herdr pane rename` 只改 display label，不能取代 agent identity。

### 新 ready shell 與 process startup

當既有 pane 是互動式 shell 且 readiness 可靠時，才可使用：

```text
herdr agent start <name> --kind <kind> --pane <id>
```

只有在 start 的 ready evidence 可信後，才對該 name 發送一次 native prompt。若 native startup 不可用，確認 target 是 fresh shell，再用獨立的 process-startup form：

```text
herdr pane run <pane-id> <command>...
```

這是 shell／process startup，不是 ordinary-pane quoted handoff；worker 仍依目標以 report／review artifact 主動交接，coordinator 不靠 polling 補救缺少的 handoff。

### First-run startup recovery 與 trust

若 first-run bootstrap 自動更新／自我替換後退出，或在 misleading ready signal 後沒有活著的 agent，狀態必須記為 `startup_failed`。不要 prompt stale target，也不要把它記為 `working`；更新完成後只做一次 bounded clean restart，第二次仍不能取得 native readiness 就停止 native retry。

若 worker 在讀取 brief 前遇到 trust working directory prompt，狀態是 `blocked`，不是 `working`。先核對 exact cwd、預期 Git remote、branch 與 task scope；只有明確授權的 workspace 才能批准，否則停止並報告 blocker。不得盲目回答任意 approval prompt。

## Context reuse gate

Pane reuse 不是單純看到 `idle` 就能重派。先判斷：

1. 舊 turn 是否已安全完成，是否仍可能執行或持有未提交的 tool operation。
2. CLI 是否安全支援 `/new`，以及 reset 後是否能取得 fresh readiness。
3. 舊 context 的內容與 token 狀態是否會污染新 task。

只有舊 turn 已完成且 `/new` 安全時，才 reset、等待 fresh readiness，再派新工作。若 reset 不安全，只有在 pane 已完成且可安全關閉時才 close，之後建立／start fresh pane。不得在舊 turn 可能仍跑時重派；這是 context isolation 與 at-most-once 的必要保護。

## Bounded acknowledgement、progress 與 anomaly recovery

- `herdr agent start` 的 readiness 或任何 handoff transport 的提交證明，只表示該 seam 已接受輸入，不是 worker 完成證明。
- 只做 brief 所需的一次 bounded startup／working acknowledgement 或 liveness check；不要 completion polling、continuous polling、transcript loop、background watcher 或無界 wait。
- Worker 初次 substantive progress 必須說明目前工作、已完成的 evidence、blocker（若有）與下一個 milestone；純 `OK`／同意／確認不算 progress。
- 若錯過 progress deadline，coordinator 只做一次 bounded liveness audit，接著給一次 recovery instruction，或記錄 worker 失敗並重新安排；不得重送同一 assignment。
- startup acknowledgement timeout 只允許一次 bounded inspection；可證明 composer 尚未提交時，依該 seam 規則補一次提交動作，不能再次送 assignment text；再次失敗記為 `dispatch_failed`。
- handoff write 失敗時，在 artifact 記錄 `handoff_failed`，不聲稱 coordinator 已收到、不重送；由 coordinator 決定 safe close／fresh recovery。
- target 顯示 `idle`／`done`／`unknown` 但沒有 completion handoff 時，視為 anomaly，單次檢查 assignment 是否仍執行或持有未提交 tool operation；不得因 `unknown` 直接重派。
- 舊 turn 仍可能執行時，禁止 reuse、reset、close 或新 assignment；隔離到可證明安全的 stop point，必要時報 blocker。

## Completed worker pane cleanup

Worker 的資源生命週期在 artifact 與 handoff 完成後停止：worker 先完成 artifact 的 atomic rename，再發送一次 applicable atomic completion handoff（依目標選擇 recognized live agent 的 `herdr agent prompt` 或 ordinary interactive pane 的 `herdr pane run <target-pane> "<message>"`），接著不再發 work，也不得關閉、操作或重用自己的 pane。Worker 也不得開 subagent、background agent、watcher、second CLI、extra pane/tab、headless task 或 self-dispatch path。

Coordinator 在收到 handoff 後只做一次 bounded liveness check。確認舊 turn 不再執行且沒有未提交的 tool operation 後，才由 coordinator 執行：

```text
herdr pane close <pane-id>
```

這個 close 是 coordinator-only，目的是釋放 completed worker CLI／pane 的記憶體；不得在舊 turn 仍可能執行時關閉。完成 subtask 的 pane 預設關閉，不保留為 idle。重用只適用於未完成且仍安全，或已安全 reset 並取得 fresh readiness 的 context；若 handoff 失敗，先在 artifact 記錄失敗，讓 coordinator 決定安全 close／recovery，不重送，也不留下 watcher。

## Worker 完成與 direct handoff

Worker 必須先把 artifact 寫好並完成 marker，再依 brief 中已解析的 exact transport 與 target handoff：

1. 在 artifact 同一目錄建立 temp 檔。
2. 寫入完整 `report.md`／`review.md`、檢查內容與 marker。
3. 以 atomic rename 取代正式 artifact path。
4. 依 brief 指定的 transport 發送一次短 handoff：recognized live agent 使用 native `herdr agent prompt`；ordinary interactive pane 使用 `herdr pane run <target-pane> "<message>"`。

Handoff message 只含 task ID、精確 artifact path、marker 與請 coordinator acceptance 的指示。Native prompt 不使用 `--wait`，pane handoff 也只送一次；任一成功 API write 都不是 coordinator 已讀取、worker 已處理或 runtime 已驗證的證明，因此不要查詢回覆、輪詢、重送文字或建立 acknowledgement loop。若選定的 atomic seam 失敗，在 artifact 如實記錄失敗；不得改用第二次 Enter 或靜默宣稱 coordinator 已收到。

## Coordinator acceptance

Coordinator 只在收到已提交 handoff 後做一次 bounded liveness check，依前述閘門關閉 completed worker CLI／pane，再讀指定報告／審查一次，核對最終 workspace、精確 diff、檢查、文件同步、限制、敏感資訊與必要 runtime evidence。若有未處理 finding 或新增實質工作，回到角色閘門重新派可見 worker；不能把 worker 的完成標記直接當成 acceptance。
