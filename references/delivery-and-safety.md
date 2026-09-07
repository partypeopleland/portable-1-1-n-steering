# 交付、文件與安全

本檔是 public package 中 source-of-truth、artifact／review evidence、操作授權、resource checkpoint prose hook、coordinator acceptance 與 Git safety 的唯一 normative source。角色與範圍見 [`roles-and-gates.md`](roles-and-gates.md)；dispatch、handoff 與 pane cleanup 的 exact sequence 見 [`lifecycle-and-handoff.md`](lifecycle-and-handoff.md)。

## 文件與唯一事實來源

- `AGENTS.md` 與 module INDEX 只放治理、Interface 與 route；方案、架構、流程與術語正文只放在一個 canonical home。
- 正式文件由 writer 草擬，coordinator 查證，獨立 reviewer 唯讀複核。重要敘述要能追溯到程式、設定、測試、執行期 evidence 或已接受決策；清楚標示 `current`、`planned`、`historical`、`runtime unknown`。
- 受影響的程式、設定、CLI、部署流程或穩定架構變更，要檢查相應的 `AGENTS.md`、唯一事實來源與文件同步；不能只寫「文件未變更」。
- `templates/core.md.tmpl` 是 renderer 的 rendered safety contract；它不是第二套自由 policy。`profiles/*.json` 只放角色 defaults 與 profile-specific fields，`templates/metadata-contract.json` 只定義 metadata／placeholder／path validation。
- 舊入口可以是 wrapper，但只能轉接到 canonical home；不能在 wrapper 保留會漂移的 active rule。
- 不寫 Secret、credential、個資、一次性錯誤、具體 pane／session instance 或未查證的永久設計；掃描路徑、術語、命令、Markdown links 與跨文件一致性。

## 授權與保守操作

- 讀取、搜尋、測試與 diff 檢查通常可直接做；worker 不能用 brief、worker 或持續 Git 發佈授權擴張範圍。
- 保留既有 dirty／untracked，精確處理 brief 列出的檔案；若 dirty overlap、範圍不明、檢查失敗或來源衝突，停止並回報。
- `deploy`、`restart`、Secret、外部服務、線上 mutation 與不可逆操作都需要明確授權；文件或 source-only 檢查不代表執行期已更新。
- 不自行執行 headless、background、built-in subagent、歷史改寫或強制 Git 操作；缺工具時停止，不以較弱安全流程替代。

## Artifact 與 review evidence

- Worker 先在 artifact 同一目錄建立 temp 檔，寫入完整 report／review、命令結果、限制與 completion marker，再依 [`lifecycle-and-handoff.md`](lifecycle-and-handoff.md) 的 artifact-first sequence atomic rename 至正式 path。
- `report`／`review` 是可追溯 evidence，不是自動通過；reviewer 必須獨立且唯讀，不能修改 writer artifact 或把判斷寫回 canonical/public。
- Native handoff、bounded liveness、pane cleanup 與 raw-terminal fallback 的唯一 active wording 在 lifecycle reference；本檔只定義 evidence、限制與 acceptance boundary。

## Provider-neutral resource checkpoint（prose hook only）

Task brief 可以用 provider-neutral prose 宣告 optional resource checkpoint：在 milestone、safe boundary 或外部 resource signal 變低／未知時，完成目前 artifact 的 atomic safe boundary，記錄已完成與未完成，停止新 work，交由 coordinator 依 ready gate 決定後續。這個 hook 不新增 metadata key、profile field、renderer behavior、daemon、watcher、second CLI 或自動續跑；不記錄 provider、quota/reset 值或個人資源偏好。checkpoint 只表示可從 artifact 恢復，不表示 runtime 完成或 acceptance 通過。

## Coordinator evidence boundary 與 acceptance

coordinator 只核對 scope、required evidence、review disposition、dependencies、documentation sync、sensitive scan 與 publication gates 是否完整；詳細 re-execution 屬 worker 工作，不由 coordinator 吸收。

完成前逐項核對：

1. 需求、範圍、排除與唯一事實來源都被涵蓋。
2. 所有必要 checks、tests、`git diff --check`、link closure、敏感資訊 scan 與文件同步檢查都有實際結果。
3. 變更只落在授權檔案；報告列出檔案、檢查命令、結果、限制與尚未做的 runtime／外部操作。
4. report／review 有完成標記，但仍需 coordinator 對 workspace、diff、文件與執行期 evidence 做 acceptance。
5. 重要 claim 不把 planned、source-only 或 offline test 說成 current、deployed 或 runtime verified。

## Git safety 與 publication gate

只有必要 checks、獨立 review 與 coordinator acceptance 完成，且驗收記錄精確列明檔案、repository、branch 與 remote，才可針對已驗收內容進行一般 commit／非強制 push。發佈前依序檢查 status／diff、確認沒有不安全 divergence、只 stage 精確路徑、執行 staged checks、檢視完整 staged diff，再建立一般新 commit、非強制 push，最後核對 local／tracking／remote SHA 與預期狀態。

Git history 不得被重寫：不得 `merge`、`rebase`、`amend`、`reset`、force push 或 tag 來繞過驗收；遇到 conflict、remote divergence、缺 branch／remote、檢查失敗或範圍污染，立即安全停點。此 publication gate 不涵蓋其他 dirty／untracked、未驗收內容、未明列環境、deploy、restart、Secret 或其他外部 mutation。
