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

## 執行流程（Execution Lifecycle）

### 1. 建立任務（Task Setup）
在 `.coordination/tasks/<task-id>/` 建立任務結構：
- `brief.md`：目標、角色、唯一 writer、範圍與排除、唯一事實來源、限制、驗收標準與完成標記。

### 2. 派工閘門與 Bounded Acknowledgement
- 在 ready/idle 的 Herdr pane 提交工作：
  ```sh
  herdr pane run <worker-pane> "<assignment>"
  ```
- 執行單次 bounded acknowledgement 等待 `working` 狀態：
  ```sh
  herdr wait agent-status <worker-pane> --status working --timeout <bounded-ms>
  ```
- 嚴禁 continuous polling、無界等待或 background watcher。

### 3. 進度與產出（Progress & Execution）
- Worker 到達里程碑時主動回報進度與 blocker。
- Worker 完成後產出 `report.md`（Developer）或 `review.md`（Reviewer）。

### 4. Direct Handoff 與 Coordinator 驗收
- Worker 發送單次完成交接通知，指向產出的 report / review。
- Coordinator 逐項核對 workspace diff、測試結果、文件與安全發佈閘門。

## 詳細參考文件（Detailed References）

若需查閱更完整的子協議與規則細節，請參閱：
- **角色與工作閘門**：[`references/roles-and-gates.md`](references/roles-and-gates.md) — 角色規範、模型選擇標準與工作分類。
- **版面與任務交接**：[`references/lifecycle-and-handoff.md`](references/lifecycle-and-handoff.md) — Herdr 版面管理、brief/report/review 合約與 bounded 派工。
- **交付、文件與安全**：[`references/delivery-and-safety.md`](references/delivery-and-safety.md) — 驗收證據、文件同步與安全 Git 發佈閘門。
