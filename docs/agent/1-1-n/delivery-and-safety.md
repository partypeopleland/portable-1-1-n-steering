# 交付、文件與安全

本檔是 1:1:N／Herdr module 的文件產出、唯一事實來源、操作授權、驗收證據與 Git safety implementation。

## 文件與唯一事實來源

- `AGENTS.md` 與 module INDEX 只放治理、Interface 與路由；方案、架構、流程與術語正文只放在一個 canonical home。
- 正式文件由 writer 草擬，coordinator 查證，獨立 reviewer 唯讀複核。重要敘述要能追溯到程式、設定、測試、執行期證據或已接受決策；清楚標示 `current`、`planned`、`historical`、`runtime unknown`。
- 受影響的程式、設定、CLI、部署流程或穩定架構變更，要檢查相應的 `AGENTS.md`、唯一事實來源與文件同步；不能只寫「文件未變更」。
- 不寫 Secret、credential、個資、一次性錯誤或未查證的永久設計；掃描路徑、術語、命令、Markdown links 與跨文件一致性。
- 舊入口可以是 wrapper，但只能轉接到 canonical home；不能在 wrapper 保留會漂移的 active rule。

## 授權與保守操作

- 讀取、搜尋、測試與 diff 檢查通常可直接做；工作者不能用 brief、worker 或持續 Git 發佈授權擴張範圍。
- 保留既有 dirty／untracked，精確處理 brief 列出的檔案；若 dirty overlap、範圍不明、檢查失敗或來源衝突，停止並回報。
- `deploy`、`restart`、Secret、外部服務、線上 mutation 與不可逆操作都需要明確授權；文件或 source-only 檢查不代表執行期已更新。
- 不自行執行 headless、background、built-in subagent、歷史改寫或強制 Git 操作；缺工具時停止，不以較弱安全流程替代。

## 驗收 evidence

完成前逐項核對：

1. 需求、範圍、排除與唯一事實來源都被涵蓋。
2. 所有必要 checks、tests、`git diff --check`、link closure、敏感資訊 scan 與文件同步檢查都有實際結果。
3. 變更只落在授權檔案；報告列出檔案、檢查命令、結果、限制與尚未做的 runtime／外部操作。
4. report／review 有完成標記，但仍需 coordinator 對 workspace、diff、文件與執行期證據做 acceptance。
5. 重要 claim 不把 planned、source-only 或 offline test 說成 current、deployed 或 runtime verified。

## 驗收後 Git 發佈

通過必要 checks、獨立 review 與 coordinator acceptance 後，才可針對驗收記錄精確列明的檔案、repository、branch 與 remote 進行一般 commit／非強制 push。仍須：先看 status／diff，fetch 並確認 divergence，精確 stage，執行 staged checks 並檢視完整 staged diff，建立一般新 commit，非強制 push，最後核對 local／tracking／remote SHA 與工作區狀態。

這項持續授權不涵蓋其他 dirty／untracked、未驗收內容、merge、rebase、amend、reset、force push、tag、deploy、restart、Secret 或其他外部 mutation。遇到 conflict、remote divergence、缺 branch／remote、檢查失敗或範圍污染，立即安全停點。
