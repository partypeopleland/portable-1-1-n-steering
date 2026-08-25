# AI 文件索引

本目錄寫給要執行 1:1:N／Herdr 的 AI。它不是一般使用者的入門說明；人類請先讀 repository 根目錄的 `README.md`。

## 讀取順序

1. 讀取工作區的 `AGENTS.md`，確認本次工作的安全規則。
2. 讀取本 package 的 `SKILL.md`，確認是否應啟用 1:1:N。
3. 讀取 [`ai-runbook.md`](ai-runbook.md)，取得本次派工和交接的決策規則。
4. 依任務需要讀取 `../references/` 下的詳細規則。
5. 讀取 coordinator brief 指定的唯一事實來源；缺少來源時停止，不要猜測。

## 文件角色

- `../SKILL.md`：技能入口、觸發條件和 reusable brief 介面。
- `ai-runbook.md`：AI 執行時的摘要規則和決策表。
- `../references/roles-and-gates.md`：角色、模型、範圍和信任閘門的詳細規則。
- `../references/lifecycle-and-handoff.md`：pane、brief、report、review 和 handoff 的詳細規則。
- `../references/delivery-and-safety.md`：證據、文件同步、Git 和外部 mutation 的詳細規則。

## 衝突處理

`SKILL.md` 和 `../references/` 是 package 的 canonical operational source。若本目錄的摘要與它們不同，以 canonical source 和工作區 `AGENTS.md` 為準，並停止猜測未定義的行為。

## 證據界線

文件內容只是操作規則，不是執行期證據。只有實際命令結果、artifact、review 和明確的 runtime check，才能支持「已完成」或「已上線」的說法。
