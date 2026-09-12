# Plan-Gated Execution（Portable Skill）

本儲存庫提供給支援 Agent Skills 規範的 AI 程式設計助理使用的 plan-first、review-gated
執行規範與可重用工具。主工作視窗直接與 Owner 溝通並執行，先選擇審查模式，再由獨立
reviewer 審核計畫，最後才進入實質工作。

## 用途與觸發條件

需要實作、除錯、設計、正式文件、測試、部署、資料、權限、Git 或外部 mutation 時使用。
單純對話或 bounded read-only lookup 可跳過 plan；一旦轉成 substantive mutation，必須先
建立 plan。

本 README 只負責入口、安裝與 package contract。唯一 normative source 是：

- [Protocol](references/protocol.md)：plan gate、主視窗責任、subagent review 與狀態。
- [Review contract](references/review-contract.md)：模式選擇、能力門檻、read-only review、digest 與 `LGTM`。
- [Execution and safety](references/execution-and-safety.md)：執行、證據、驗收、Git 與安全停點。

## AI 文件入口

- [`docs/README.md`](docs/README.md)：AI 文件閱讀順序與來源關係。
- [`docs/ai-runbook.md`](docs/ai-runbook.md)：plan、review、執行與停止條件摘要。

## Package 內容

```text
templates/plan.md.tmpl             # plan shape
templates/example-plan.json        # generic safe example
scripts/render_plan.py             # deterministic stdlib-only renderer
scripts/validate_plan_gate.py      # digest/model/LGTM gate validator
scripts/smoke_installed_package.py # finite fresh-install smoke
tests/test_plan_contract.py        # deterministic package tests
```

Renderer 要求 task id、revision、Owner authorization、objective、risk tier、review mode、
review rationale、scope、排除、來源、依賴、步驟、風險／授權、驗證、rollback、交付物與
acceptance；會拒絕缺欄位、未知欄位、未解析 placeholder、控制字元與 credential-like
content。Gate validator 會比對 plan SHA-256、reviewer identity／能力／provider（且與
dispatch 逐欄一致）、read-only scope、零 blocker／high finding 與精確 `LGTM`。

審查模式有三種：`frontier-single` 是一名可核對的 `gpt-6-astra` 或 `gpt-5.6-sol`；
`dual-fallback` 是低／中風險時至少兩名不同 identity 與 provider 的核准 fallback；
`owner-choice` 只是等待 Owner 指定，不能通過 gate。高風險或風險未知不可用 fallback
猜過，必須取得 frontier 或回問 Owner。

frontier dispatch 必須使用 `provider: openai` 與 `capability: frontier-plan-review`。

Reviewer 的 `LGTM` 只解除 exact plan revision 的 execution gate，不代表 Owner 授權、runtime
完成或最終 acceptance。

## 安裝（不自動移除既有安裝）

在 package 目錄執行：

```sh
./install.sh
```

預設安裝至 `$HOME/.agents/skills/plan-gated-execution`。傳入 workspace 或精確目錄時，
安裝器只複製新 package，不刪除其他技能或舊安裝。

## 本地驗證

```sh
python3 scripts/render_plan.py --metadata templates/example-plan.json
python3 scripts/validate_plan_gate.py --plan plan.md \
  --review plan-review.md --dispatch dispatch.json
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/smoke_installed_package.py
```

`dual-fallback` 以重複的 `--review` 與 `--dispatch` 傳入每一份配對 artifact；validator
要求至少兩份且逐份核對 identity、provider、capability、digest 與模式。

Smoke 只做有限 fresh-install contract check，不啟動 recursive runner、background watcher
或 live deployment。

## 邊界

公開 package 描述可驗證的能力級別、風險、複雜度與 evidence。fallback allowlist 目前
提供 Host adapter `agy`（目前核准 model label `gemini-3.8-flash-high`、capability
`agy-high-plan-review`）與 `devin`／`swe-2-high`（capability `SWE-2 high`）；兩者都必須由實際 dispatch 證據提供，不能只填字串冒充能力。新增 adapter、模型或更高模型必須先做獨立 allowlist
review。個人 quota/reset、私有路徑、pane/session instance、服務、repository 與
credentials 不屬於 package contract。
