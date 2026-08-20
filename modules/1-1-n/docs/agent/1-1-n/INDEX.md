# 1:1:N／Herdr module

本檔是這個 module 的唯一 public Interface。讀完根 [`AGENTS.md`](../../../AGENTS.md) 後先讀本檔，再依任務路由讀必要的 detail docs；caller 不需要先理解整個資料夾。

## Responsibility

本 module 定義可攜的 1:1:N 協作：一名 `coordinator` 面向使用者，多名可見、互動式 Herdr worker 提供實作與證據，最後由 coordinator 整合、獨立審查與驗收。它也定義模型選擇、任務檔案、ready-gated dispatch、direct handoff、文件驗收與安全 Git 發佈閘門。

Module 的 Interface 包含這些不變條件：

- 實作、正式文件、設計、測試、非簡單調查與審查都必須先有至少一名可見、互動式 worker；`N = 0` 只適用於本 module 明列的簡單例外。
- worker 是證據來源，不是權威；report／review 不能替代 coordinator 對 workspace、diff、檢查、文件與執行期證據的驗收。
- 每個任務有 bounded 的 `brief.md`、`report.md`、獨立 `review.md` 與完成標記；派工與交接依 lifecycle 的 ready gate、bounded working acknowledgement 與 at-most-once 規則。
- 不得使用 built-in subagent、headless CLI、background terminal 或以 commentary 冒充派工。

## Exact portable manifest

只複製下列五個檔案即可取得本 module 的相同協作規則；相對結構必須保留：

1. `AGENTS.md`
2. `docs/agent/1-1-n/INDEX.md`
3. `docs/agent/1-1-n/roles-and-gates.md`
4. `docs/agent/1-1-n/lifecycle-and-handoff.md`
5. `docs/agent/1-1-n/delivery-and-safety.md`

這五檔內的必要 Markdown links 必須只指向 manifest 內檔案。這個 module 沒有另一個 required steering module dependency；若未來確實依賴另一個 module，必須在此明列其名稱、INDEX 入口、觸發條件與缺失時的停止行為，不得暗中跨資料夾引用或形成 circular dependency。

## Prerequisites

- workspace root：能讀取根 `AGENTS.md` 與 `docs/agent/1-1-n/`。
- 實質工作：可見、互動式 Herdr 與互動式 Codex CLI。
- 需要 Git 發佈：Git、已確認的 branch／tracking／remote，且先通過本 module 的驗收閘門。

缺少必要工具、manifest 檔案、入口或規則無法解析時停止並回報；不能自行改成 headless、background 或內建 subagent 流程。

## Task routing

| 任務 | 先讀 | 再讀 |
|---|---|---|
| 實作、設定、測試、遷移、執行期工作 | [`roles-and-gates.md`](roles-and-gates.md) | 目標倉庫的 `AGENTS.md`；本次 brief 指定的唯一事實來源 |
| 正式文件、設計、驗收 | [`roles-and-gates.md`](roles-and-gates.md) | [`delivery-and-safety.md`](delivery-and-safety.md) |
| 非簡單調查或審查 | [`roles-and-gates.md`](roles-and-gates.md) | [`delivery-and-safety.md`](delivery-and-safety.md)；brief 指定的來源 |
| Herdr、brief／report／review、完成交接、idle | [`lifecycle-and-handoff.md`](lifecycle-and-handoff.md) | 角色文件若任務也涉及派工閘門 |
| 簡單 Git 發佈 | [`roles-and-gates.md`](roles-and-gates.md) | [`delivery-and-safety.md`](delivery-and-safety.md) |

detail docs 的責任互斥：角色與模型只在 `roles-and-gates.md`；版面、提交與交接只在 `lifecycle-and-handoff.md`；文件證據、安全、驗收與 Git 發佈細節只在 `delivery-and-safety.md`。根檔與本 INDEX 只做摘要與路由，不複製正文。

## Portability and deletion tests

- **Temp-copy test：** 只把 exact manifest 複製到乾淨 workspace root，仍應能由根檔讀到本 INDEX，再由 INDEX 路由三份 detail docs；link closure 與 forbidden-string scan 必須通過。
- **Second-module test：** 新增第二個 module 只需增加自己的資料夾／`INDEX.md` 與根 registry 一列，不得修改本 module 的任何檔案。
- **Deletion test：** 刪除本 module 會讓 1:1:N 複雜度回散到所有任務；刪除任一 detail doc 會失去一個不可由轉接文字替代的完整責任，因此三份 detail docs 都是 implementation，不是淺 wrapper。

遇到缺檔、連結未閉合、重複 canonical 規則、規則衝突、範圍不明或驗收失敗，停止，不以猜測補規則。
