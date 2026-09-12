# AI 文件索引

本目錄寫給要使用 Plan-Gated Execution 的 AI。它不是一般使用者的入門說明；人類請先讀
repository 根目錄的 `README.md`。

## 讀取順序

1. 讀取工作區的 `AGENTS.md`，確認本次工作的安全規則。
2. 讀取本 package 的 `SKILL.md`，確認是否屬 substantive work。
3. 讀取 [`ai-runbook.md`](ai-runbook.md)，取得 plan、review 與 close 的決策規則。
4. 依任務需要讀取 `../references/` 下的詳細規則。
5. 建立並鎖定 task-local `plan.md`，先選擇 review mode，再呼叫所需的獨立 reviewer；
   缺少授權、來源或 review evidence 時停止，不要猜測。

## 文件角色

- `../SKILL.md`：技能入口、觸發條件與 plan gate 摘要。
- `ai-runbook.md`：AI 執行時的摘要規則與停止條件。
- `../references/protocol.md`：plan、review、main execution 與狀態。
- `../references/review-contract.md`：reviewer 輸入、能力與 `LGTM` artifact。
- `../references/execution-and-safety.md`：證據、文件同步、Git 與 external mutation。

## 衝突與證據

`SKILL.md` 和 `../references/` 是 package 的 canonical operational source。若本目錄摘要與
它們不同，以 canonical source 和工作區 `AGENTS.md` 為準，並停止猜測未定義的行為。
文件內容只是操作規則；只有實際命令結果、artifact、review 和明確 runtime check，才能支持
「已完成」或「已上線」的說法。
