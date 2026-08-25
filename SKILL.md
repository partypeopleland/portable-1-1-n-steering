---
name: herdr-1-1-n
description: Orchestrate multi-agent coordinator-worker collaboration using the 1:1:N / Herdr protocol. Use ONLY when the user explicitly requests "1:1:N", "1-1-n", "Herdr", "多 Agent 派工", or specifically asks for multi-agent dispatch with formal brief/report/review and delivery gates.
---

# 1:1:N / Herdr 協作技能（Multi-Agent Collaboration Protocol）

本技能定義高嚴謹度、多角色的 **1:1:N / Herdr 協作架構**：由單一面向使用者的 `coordinator` 負責邊界、brief 與驗收，搭配多名可見的 `worker` 執行細部工作並提供驗證證據。

## 何時啟用（When to Use）

- 使用者在對話中**明確指定**使用 `1:1:N`、`1-1-n`、`Herdr` 或「多 Agent 派工模式」。
- 任務屬於大規模跨模組專案，且明確指示需要拆分 writer / reviewer 多角色獨立協作與驗收。
- **注意（反向約束）**：常規日常修改、單一檔案編輯、單純問題排查、或常規 Git 操作（如檢查 commit）**絕不啟用此技能**，一律由主 Agent 俐落直接執行。

## 角色拓撲（Core Topology）

- **Coordinator (1)**：唯一面向使用者的協調者。只負責需求釐清、撰寫 brief、依賴順序排定、派工、接收 handoff、組織獨立審查驗收與已授權發佈。**不吸收 worker 任務細節**。
- **Workers (N >= 1)**：在可見、互動式的 Herdr pane 中執行的專屬工作者。
  - **Developer (Writer)**：依 brief 授權範圍進行修改，產出檢查結果與變更證據。
  - **Reviewer (Verifier)**：唯讀獨立審查，檢查規範、需求與 diff，撰寫 `review.md`。

## Native dispatch 與 at-most-once 交接

- 「跨視窗交接資訊」明確包括 coordinator-to-worker assignments、worker-to-coordinator completion handoffs，以及 coordinator-to-worker correction/review handoffs。
- 當目標是 ordinary interactive pane 時，上述三類資訊每一項都使用一次 atomic
  `herdr pane run <target-pane> "<message>"` seam。這個 quoted-message 形式只把
  交接資訊送入已存在的 pane；它不是 shell/CLI startup，也不是 readiness、完成或
  runtime verification 的證據。啟動 shell/process 另使用
  `herdr pane run <pane-id> <command>...`，不得把兩種形式混為一談。
- 若目標是真正已被 Herdr 辨識且仍可用的 live agent，使用
  `herdr agent prompt <agent-name-or-pane-id> "<message>"` 作 recognized-agent
  atomic seam。普通 pane 使用者不得把 `pane send-text` 加 `pane send-keys ...
  Enter` 當正常路徑。
- 只有 atomic `pane run` 與 native `agent prompt` 都不可用時，才可明確標記為
  compatibility recovery，對 ordinary pane 以 raw `herdr pane send-text ...` 加
  `herdr pane send-keys ... Enter` 嘗試一次；split pair 必須 at-most-once，並在
  artifact/report 記錄失敗。不得靜默把 composer 內容視為已提交、補第二次 Enter、
  重送或宣稱 runtime 已驗證。
- 用 `herdr agent rename <target> <name>` 建立穩定目標名；`herdr pane rename` 只改顯示標籤，不會建立 native agent identity。
- 新 ready shell 在 readiness 可靠時才用 `herdr agent start <name> --kind <kind> --pane <id>`。若 first-run bootstrap 自動更新後退出，標記 `startup_failed`、不要 prompt stale target，讓更新完成後只做一次 bounded clean restart；native startup 仍不可用時，才從 fresh shell 用 `herdr pane run <pane-id> <command>...` 啟動 process，這仍不是交接資訊的 handoff seam。
- Codex 在讀 brief 前若出現 trust working directory，狀態是 `blocked` 而不是 `working`；先核對精確 cwd、Git remote、branch 與 task scope，只能對明確授權 workspace 放行。
- 交接前先以 temp + atomic rename 完成 `report.md`／`review.md` 與 marker，再依目標選擇一次 native prompt 或 ordinary-pane `pane run`；不 completion polling、不 transcript loop、不 background watcher、不第二次 Enter、不 blind resend。
- 重用 pane 前先判斷舊 context 與 `/new` 是否安全；只重置已安全完成的 context 並等待 fresh readiness，否則只關閉已完成 pane 後建立 fresh pane。不得在舊 turn 可能仍執行時派新工作。
- Worker 完成 artifact、一次 handoff 並停止發出工作後，worker 不得關閉或操作 pane。Coordinator 只做一次 bounded liveness check；確認舊 turn 不再執行且沒有未提交 tool operation 後，以 `herdr pane close <pane-id>`（或當前等價命令）關閉 completed worker CLI/pane 釋放記憶體。完成 pane 預設關閉，不保留為 idle；重用只適用於未完成或已安全 reset 的 context。handoff 失敗要記錄，交由 coordinator 決定安全 close/recovery，不重送、不留 watcher。
- Worker boundary 是硬閘門：只能使用指定 pane 與 foreground commands；不得開 subagent、background agent、watcher、second CLI、extra pane/tab、headless task 或 self-dispatch path。

## Reusable brief templates

`templates/core.md.tmpl` 集中不變的 lifecycle、safety、handoff 與 acceptance prose；`profiles/` 只提供 `developer`、`reviewer`、`investigation`、`design` 的 defaults 與 profile-specific fields。用 stdlib-only renderer 產出實際 task artifact：

```sh
python3 scripts/render_brief.py --metadata templates/example-metadata.json
```

`templates/metadata-contract.json` 是 required／optional／profile-specific 欄位與 placeholder 契約。Renderer 會嚴格拒絕缺欄位、未知 profile、未解析 placeholder、不安全 task/path 與明顯 credential-like content；安裝包也包含 renderer、profiles、templates 與 deterministic tests。

## 執行流程（Execution Lifecycle）

### 1. 建立任務（Task Setup）
在 `.coordination/tasks/<task-id>/` 建立任務結構：
- `brief.md`：目標、角色、唯一 writer、範圍與排除、唯一事實來源、限制、驗收標準與完成標記。

### 2. 派工閘門與 bounded acknowledgement
- 只在 ready/idle 且沒有其他 turn 的可見 pane 派工；recognized live agent 使用 native `herdr agent prompt`，ordinary interactive pane 的交接資訊使用 atomic `herdr pane run <target-pane> "<message>"`。
- 啟動成功需有 bounded readiness evidence；不得以舊 spinner、composer 文字或 stale process 當作 `working`。
- 嚴禁 continuous polling、無界等待或 background watcher。

### 3. 進度與產出（Progress & Execution）
- Worker 到達里程碑時主動回報進度與 blocker。
- Worker 完成後先產出 `report.md`（Developer）或 `review.md`（Reviewer），再 handoff。

### 4. Direct Handoff 與 Coordinator 驗收
- Worker 只發送一次已提交的 native completion prompt，或在 ordinary interactive pane 使用一次 atomic `herdr pane run <target-pane> "<message>"`，指向精確 artifact path 與 marker。
- Coordinator 逐項核對 workspace diff、測試結果、文件與安全發佈閘門；worker completion marker 不是 acceptance。
- Handoff 完成後，coordinator 只做一次 bounded liveness check；確認舊 turn 已停止且不持有未提交 tool operation，才關閉 completed worker CLI/pane。worker 不得自行關閉 pane。

## 詳細參考文件（Detailed References）

若需查閱更完整的子協議與規則細節，請參閱：
- **角色與工作閘門**：[`references/roles-and-gates.md`](references/roles-and-gates.md) — 角色規範、模型選擇標準與工作分類。
- **版面與任務交接**：[`references/lifecycle-and-handoff.md`](references/lifecycle-and-handoff.md) — Herdr 版面管理、brief/report/review 合約與 bounded 派工。
- **交付、文件與安全**：[`references/delivery-and-safety.md`](references/delivery-and-safety.md) — 驗收證據、文件同步與安全 Git 發佈閘門。
