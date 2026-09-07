# 1:1:N / Herdr 多角色協同協作技能（Portable Skill）

本儲存庫提供適用於支援 Agent Skills 規範的 AI 程式設計助理之 1:1:N / Herdr 協作技能，以及可重用的 task brief renderer。套件本身不依賴特定 provider、模型名稱或工作區服務。

## 用途與觸發

在需要一名 coordinator 管理範圍、授權、依賴與驗收，並由可見 worker 執行細節與交付 evidence 的多角色任務時使用。明確提及 `1:1:N`、`1-1-n`、`Herdr` 或多 Agent 派工時，也可由模型按需啟用。

本 README 只負責入口、安裝與 package contract。可攜規則的唯一 normative source 是下列三份 reference：

- [角色與工作閘門](references/roles-and-gates.md)：角色、N gate、能力導向的執行選擇、範圍與 Git publication gate。
- [版面與任務交接](references/lifecycle-and-handoff.md)：ready-gated dispatch、一次 bounded check、異常 recovery、artifact-first handoff 與 completed-pane cleanup。
- [交付、文件與安全](references/delivery-and-safety.md)：canonical responsibility、artifact/review evidence、resource checkpoint prose hook、acceptance 與 Git safety。

README 不承載上述責任域的第二份 active lifecycle；請依 reference link 讀取完整規則。

## AI 文件入口

- [`docs/README.md`](docs/README.md)：AI 文件閱讀順序與來源關係。
- [`docs/ai-runbook.md`](docs/ai-runbook.md)：派工前 preflight 與 canonical reference route 摘要。

## Package contract

```text
templates/core.md.tmpl             # rendered task-brief safety contract
templates/metadata-contract.json   # metadata and path contract
templates/example-metadata.json    # generic example without local paths
profiles/*.json                     # role defaults and profile fields
scripts/render_brief.py             # stdlib-only strict renderer
scripts/bounded_process.py          # finite process helper
scripts/smoke_installed_package.py  # finite fresh-install smoke
tests/test_render_brief.py          # deterministic package tests
```

四個 profile 共用同一個 core template，只提供各自的 role、completion marker、artifact default、instructions 與 profile-specific fields：

- `developer`：`changes`（required）、`implementation_notes`（optional）
- `reviewer`：`review_focus`（required）、`findings`（optional）
- `investigation`：`questions`（required）、`hypotheses`（optional）
- `design`：`decisions`（required）、`alternatives`（optional）

Renderer 會嚴格拒絕缺少 required values、unknown profile、unknown/unresolved placeholders、不安全 task/path、未知 profile fields 與 credential-like content。Rendered brief 是該 task 的唯一 execution authorization；profile 不會另立全域 lifecycle 規則。

## 安裝

### 安裝至個人全域技能目錄

在 package 目錄執行：

```sh
./install.sh
```

預設會安裝至 `$HOME/.agents/skills/herdr-1-1-n`。

### 安裝至特定工作區

傳入目標工作區或精確安裝目錄：

```sh
./install.sh /path/to/workspace
```

含有 `AGENTS.md` 的既有 workspace 會使用 `<workspace>/.agents/skills/herdr-1-1-n`；其他參數會被視為精確安裝目錄。

## 本地驗證

```sh
python3 scripts/render_brief.py --metadata templates/example-metadata.json
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/smoke_installed_package.py
```

`smoke_installed_package.py` 只做有限 fresh-install contract check，不啟動 recursive test runner、background watcher 或 live deployment。

## 邊界

公開 package 只描述 provider-neutral 的能力、風險、複雜度與可用資源訊號；個人模型、quota/reset、私有路徑、pane/session instance、服務、repository 與 credentials 不屬於 package contract。若 local brief 需要更具體的操作選擇，應留在 task-local authorization，不回填 public guidance。
