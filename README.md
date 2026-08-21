# 1:1:N / Herdr 多角色協同協作技能（Portable Skill）

本儲存庫提供適用於 AI 程式設計助理（如 Antigravity、Claude Code、Codex 等支援 Agent Skills 規範的工具）的 **1:1:N / Herdr 協作技能**。

---

## 什麼是 1:1:N / Herdr？

**1:1:N / Herdr** 是一種專為高嚴謹度、複雜軟體工程任務設計的多 Agent 協作協議。它將高層級的「範圍釐清與驗收協調」與底層的「具體實作與審查」徹底解耦：

- **1 名 Coordinator（協調者）**：唯一面向使用者的對話窗口。負責釐清需求邊界、撰寫工作簡報（Brief）、依賴順序排定、派工與最終驗收。**不直接吸收 worker 的任務實作細節**。
- **N 名 Workers（工作者）**：在可見、互動式的視窗（Pane）中執行專屬任務的獨立工作者。
  - **Developer (Writer)**：在 Brief 授權範圍內進行程式碼修改，並產出可查證的執行證據與報告（`report.md`）。
  - **Reviewer (Verifier)**：以唯讀方式獨立審查需求、標準與 Diff，撰寫審查紀錄（`review.md`）。

---

## 為什麼採用 Skill（技能）架構？

1. **按需載入（Zero Context Pollution）**：
   - 避免將重型派工規則放在全域指令（如 `AGENTS.md`）中，導致 AI 在面對簡單指令（如 `git commit` 或單行修改）時產生「過度設計」與「小事大做」的問題。
   - 平時處於休眠狀態，**僅在明確指示時才會載入**。
2. **完全可攜與標準化**：
   - 符合標準 Agent Skills 目錄結構，可一鍵安裝至個人全域技能目錄或特定專案中。

---

## 目錄結構

```text
herdr-1-1-n/
├── SKILL.md                          # 技能主入口（包含 YAML 前言、生命週期與觸發規則）
├── install.sh                        # 跨平台一鍵安裝腳本
└── references/                       # 詳細子協議文件（由模型在執行時按需查閱）
    ├── roles-and-gates.md            # 角色職責、模型分級與 N-Gate 規則
    ├── lifecycle-and-handoff.md      # Herdr 版面管理、Brief/Report 合約與原子派工
    └── delivery-and-safety.md        # 驗收證據標準與安全 Git 發佈閘門
```

---

## 安裝方式

### 1. 安裝至個人全域技能目錄（預設：`~/.agents/skills/`）

在專案目錄下直接執行，不帶參數：

```sh
./install.sh
```
此指令會將技能安裝至 `$HOME/.agents/skills/herdr-1-1-n`。

### 2. 安裝至特定工作區（Workspace）

傳入目標工作區的路徑：

```sh
./install.sh /path/to/workspace
```
此指令會將技能安裝至 `<workspace>/.agents/skills/herdr-1-1-n`。

---

## 觸發方式與時機

本技能採模型按需調用（Model-invoked），僅在以下情況觸發：
- 使用者在對話中明確提及 **`1:1:N`**、**`1-1-n`**、**`Herdr`** 或 **`多 Agent 派工`**。
- 使用者明確指派需要進行大規模、跨模組的多角色協同開發與嚴格驗收流程。

> [!IMPORTANT]
> **日常維護規範**：常規日常修改、單檔編輯、單純問題排查或常規 Git 操作（如 `git commit`）**絕不觸發此技能**，一律由主 Agent 俐落直接執行。
