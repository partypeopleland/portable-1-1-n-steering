# 1:1:N / Herdr 多角色協同協作技能（Portable Skill）

本儲存庫提供適用於 AI 程式設計助理（如 Antigravity、Claude Code、Codex 等支援 Agent Skills 規範的工具）的 **1:1:N / Herdr 協作技能**，並附帶可重用的 task brief renderer。

## 什麼是 1:1:N / Herdr？

**1:1:N / Herdr** 是一種專為高嚴謹度、複雜軟體工程任務設計的多 Agent 協作協議。它將高層級的「範圍釐清與驗收協調」與底層的「具體實作與審查」徹底解耦：

- **1 名 Coordinator（協調者）**：唯一面向使用者的對話窗口。負責釐清需求邊界、撰寫工作簡報（Brief）、依賴順序排定、派工與最終驗收。**不直接吸收 worker 的任務實作細節**。
- **N 名 Workers（工作者）**：在可見、互動式的視窗（Pane）中執行專屬任務的獨立工作者。
  - **Developer (Writer)**：在 Brief 授權範圍內進行程式碼／文件修改，並產出可查證的執行證據與 `report.md`。
  - **Reviewer (Verifier)**：以唯讀方式獨立審查需求、標準與 Diff，撰寫 `review.md`。

## Native dispatch 與 at-most-once handoff

已被 Herdr 辨識的 live agent 使用 atomic seam：

```text
herdr agent prompt <agent-name-or-pane-id> "<assignment>"
```

用 `herdr agent rename <target> <stable-name>` 建立 native 穩定名稱；`herdr pane rename` 只改 display label。新 ready shell 只有在 readiness 可靠時才使用：

```text
herdr agent start <name> --kind <kind> --pane <id>
```

若 first-run bootstrap 自動更新後退出，分類為 `startup_failed`，不要 prompt stale target；讓更新完成後只做一次 bounded clean restart。Native startup 仍不可用時，才從 fresh shell 用 ordinary-process fallback：

```text
herdr pane run <pane-id> <command>...
```

Codex 在讀取 brief 前的 trust cwd prompt 是 `blocked`，不是 `working`；先核對 exact cwd、預期 Git remote、branch 與 task scope。Artifact 必須先以 temp + atomic rename 完成，再對 coordinator 發送一次 native prompt；不 completion polling、transcript loop、background watcher、第二次 Enter 或 blind resend。完整規則見 [`references/lifecycle-and-handoff.md`](references/lifecycle-and-handoff.md)。

Worker 完成 `report.md`／`review.md`、發送一次 handoff 並停止後，不得關閉或操作自己的 pane。Coordinator 只做一次 bounded liveness check；確認舊 turn 已停止且沒有未提交 tool operation，才用 `herdr pane close <pane-id>`（或當前等價命令）關閉 completed worker CLI/pane。完成 pane 預設關閉，不保留 idle；重用只適用於未完成或已安全 reset 的 context。handoff 失敗要記錄並由 coordinator 決定安全 close/recovery，不重送或留下 watcher。Worker 不得開 subagent、background agent、watcher、second CLI、extra pane/tab、headless task 或 self-dispatch path。

## Reusable brief templates

套件把 invariant lifecycle prose 與角色差異拆開，避免相似 task 重複複製流程文字：

```text
templates/core.md.tmpl             # 唯一核心 lifecycle/safety/handoff/acceptance prose
templates/metadata-contract.json   # 欄位、placeholder、path 與 safety contract
templates/example-metadata.json    # 無 secret、無本機絕對路徑的範例
profiles/*.json                     # developer/reviewer/investigation/design defaults
scripts/render_brief.py             # stdlib-only strict renderer
tests/test_render_brief.py          # deterministic renderer/install tests
```

四個 profile 都共用同一個 core template，只定義自己的 role、completion marker、artifact default、instructions 與 profile-specific fields：

- `developer`：`changes`（required）、`implementation_notes`（optional）
- `reviewer`：`review_focus`（required）、`findings`（optional）
- `investigation`：`questions`（required）、`hypotheses`（optional）
- `design`：`decisions`（required）、`alternatives`（optional）

必要 metadata 包含 task ID、profile、objective、workspace/repo、role、sources、scope、exclusions、allowed mutations、checks、artifact path、completion marker 與 handoff target。Renderer 會嚴格拒絕缺少 required values、unknown profile、unknown/unresolved placeholders、不安全 task/path、未知 profile fields 與明顯 credential-like content。

範例只使用公開描述與 repository-relative paths，可直接在套件根目錄執行：

```sh
python3 scripts/render_brief.py --metadata templates/example-metadata.json
```

預設輸出到 stdout；需要寫檔時可加 `--output <repository-relative-or-explicit-output-path>`，renderer 會在同一目錄使用 temp file 後 atomic replace。

## 目錄結構

```text
herdr-1-1-n/
├── SKILL.md
├── README.md
├── install.sh
├── templates/
│   ├── core.md.tmpl
│   ├── metadata-contract.json
│   └── example-metadata.json
├── profiles/
│   ├── developer.json
│   ├── reviewer.json
│   ├── investigation.json
│   └── design.json
├── scripts/
│   ├── render_brief.py
│   ├── bounded_process.py
│   └── smoke_installed_package.py
├── tests/
│   └── test_render_brief.py
└── references/
    ├── roles-and-gates.md
    ├── lifecycle-and-handoff.md
    └── delivery-and-safety.md
```

## 安裝方式

### 1. 安裝至個人全域技能目錄（預設：`~/.agents/skills/`）

在專案目錄下直接執行，不帶參數：

```sh
./install.sh
```

此指令會將完整 package（core template、四個 profiles、renderer 與 tests）安裝至 `$HOME/.agents/skills/herdr-1-1-n`。

### 2. 安裝至特定工作區（Workspace）

傳入目標工作區的路徑：

```sh
./install.sh /path/to/workspace
```

若目標是含有 `AGENTS.md` 的既有 workspace，package 會安裝至 `<workspace>/.agents/skills/herdr-1-1-n`；否則把參數視為精確安裝目錄。

Source checkout 可執行 renderer 與 deterministic tests：

```sh
python3 scripts/render_brief.py --metadata templates/example-metadata.json
python3 -m unittest discover -s tests -p 'test_*.py'
```

Fresh-install validation 只從 temporary destination 執行有限 smoke entrypoint，不在 installed copy 啟動 complete suite：

```sh
python3 scripts/smoke_installed_package.py
```

## 觸發方式與時機

本技能採模型按需調用（Model-invoked），僅在以下情況觸發：

- 使用者在對話中明確提及 **`1:1:N`**、**`1-1-n`**、**`Herdr`** 或 **`多 Agent 派工`**。
- 使用者明確指派需要進行大規模、跨模組的多角色協同開發與嚴格驗收流程。

> [!IMPORTANT]
> **日常維護規範**：常規日常修改、單檔編輯、單純問題排查或常規 Git 操作（如 `git commit`）**絕不觸發此技能**，一律由主 Agent 俐落直接執行。
