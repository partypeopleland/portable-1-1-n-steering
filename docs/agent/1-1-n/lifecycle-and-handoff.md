# Herdr 版面與任務交接

本檔是 1:1:N／Herdr module 的可見工作格、ready-gated dispatch、brief／report／review、direct handoff 與 coordinator acceptance implementation。

## Herdr 版面

- `coordinator` 使用獨立且易辨認的主工作格，優先重用既有或 `idle` pane。
- `workers1` 最多四格且固定 2×2；只有前一組全忙且確實需要下一位 worker，才建立下一組，並一次建滿四格 2×2。不要關閉仍在工作的 pane；完成後保留 `idle` 供重用。
- 一格只執行一個明確 worker 工作。pane ID 是動態資料；brief 可記錄當次 coordinator pane，但 portable 文件不得寫死任何 pane ID。
- 派工前先確認目標 pane 是 `idle`／ready，且不在 CLI／MCP 啟動、approval prompt 或其他 task；先以 task ID 標籤 pane，避免 stale／duplicate label 造成重派。

## 建立任務

每個 task 使用 workspace-relative `.coordination/tasks/<task-id>/`，至少有：

- `brief.md`：目標、範圍、唯一事實來源、限制、驗收、檢查、完成標記與交接對象；
- `report.md`：developer 的成果、變更、證據、檢查、限制與完成標記；
- `review.md`：獨立 reviewer 的唯讀審查與完成標記。

report／review 是證據，不是自動通過。coordinator 必須核對 workspace、diff、測試、文件與執行期證據。

## 派工提交與 bounded acknowledgement

只有 Herdr 回報目標 agent 已因這份 assignment 進入 `working`，才算 submitted／started。composer 或 history 看得到文字、send API 成功、舊 task 的 spinner 或 pane process 存在，都不是 acknowledgement。

1. 在 ready 的可見互動式 Herdr pane 使用 brief 指定的模型與範圍。
2. 優先用單一原子 text-plus-Enter 命令提交，避免 startup race：

   ```text
   herdr pane run <worker-pane> "<assignment>"
   ```

   目前介面是 `herdr pane run <pane_id> <command>`；assignment 的 literal escaping 必須安全。
3. 只做一次 bounded acknowledgement：

   ```text
   herdr wait agent-status <worker-pane> --status working --timeout <bounded-ms>
   ```

   成功才可記錄 `started`。
4. 若 timeout，只檢查 pane 一次；若 assignment 仍在 composer，補 exactly one `Enter`，再做最後一次 bounded `working` wait。這是 recovery，不得重送 assignment text。
5. 第二次 acknowledgement 仍失敗時，結果必須記為 `dispatch_failed`，不可記為 `started`；保持 pane 可見且非 active，清除 stale prompt 或證明 pane 無法啟動前不得重派同一 brief。不得讓 replacement 造成同一 assignment 執行兩次。
6. 不做 continuous polling、background watcher、transcript loop 或無界 wait。每次 coordinator 自然回合／進度回報或收到 handoff 時，只做一次輕量 liveness audit：若已標籤的 assignment 顯示 `idle`／`done`／`unknown` 卻沒有 submitted completion handoff，視為 anomaly 並檢查一次；不要把 anomaly 變成輪詢。

## Worker 完成與 direct handoff

worker 必須先寫完自己的 `report.md`／`review.md` 與完成標記，再解析名稱或標籤為 `coordinator` 的 pane。完成訊息只送一次，內容包含 task ID、`<workspace-root>/.coordination/tasks/<task-id>/report.md` 或 `review.md`、完成標記與請 coordinator 繼續驗收的指示。

direct handoff 也遵守 at-most-once：成功 API write 不是 coordinator 已收到的證明，不重送文字、不建立 acknowledgement loop；失敗要在 report 如實記錄。若 brief 指定原子交接，可用同一個 `pane run` seam；若 brief 指定 text 與 Enter 分開，必須只執行那一組明確的兩步。

使用可見 Herdr 分開執行：

```text
herdr pane send-text <coordinator-pane> "<completion-message>"
herdr pane send-keys <coordinator-pane> Enter
```

若文字仍顯示未提交，只補這一次 Enter，不重送文字。提交後不得查詢回覆、輪詢或等待，立即以 Herdr lifecycle 將自己的 pane 報為 `idle`。若 direct handoff 失敗，在 report 如實記錄；最多發一次可見人類通知，不得宣稱 coordinator 已收到。

## Coordinator acceptance

coordinator 只在收到已提交 handoff 後讀指定報告／審查一次，再核對最終 workspace、精確 diff、檢查、文件同步、限制、敏感資訊與必要 runtime evidence。若有未處理 finding 或新增實質工作，回到角色閘門重新派可見 worker；不能把 worker 的完成標記直接當成驗收。
