# 角色與工作閘門

本檔是 1:1:N／Herdr module 的角色、工作分類、可見工作閘門、模型選擇與 Git 發佈授權 implementation。

## 角色

- `coordinator`：唯一面向使用者，只負責釐清範圍／授權、準備 brief 與依賴順序、派工、接收主動進度與 final handoff、安排獨立驗證／修正、整合結果、回報，以及已授權的精確發佈。
- `worker`：在可見、互動式 Herdr pane 執行明確工作；負責調查、設計、source／文件編輯、測試、deploy、runtime checks 與詳細 review 等任務細節，交付證據；仍受 brief 與授權限制。
- `developer`：作為 writer 在 brief 明列範圍內修改檔案並交付檢查結果。
- `reviewer`：作為獨立 verifier 唯讀檢查需求、標準、變更與證據，只在自己的 task directory 寫 `review.md`。

預設一名 writer、多名唯讀 reviewer。多名 writer 只有在檔案範圍完全分離且 brief 明確授權時才可並行；同一檔案不得有兩名 writer。

## 工作分類與 N gate

實質工作包括實作、正式文件、設計、非簡單調查、測試與審查；開始前 `N >= 1`，且至少一名 worker 必須在可見、互動式 Herdr pane 中開始工作。

`N = 0` 只限：

- 對話回答；
- 真正簡單的單一命令或唯讀查詢；
- 派工／驗收記錄；
- 已驗收內容的簡單 Git 發佈，且只改 Git 記錄、不改檔案內容。

禁止 built-in subagent、headless CLI、background terminal、`-p`、只在 commentary 聲稱派工，或將非指定工具當成預設 worker。目標倉庫的 `AGENTS.md` 對其細節優先，但不得放寬這些上層閘門。

## Brief 與模型

開始前 brief 至少要寫：目標、角色、唯一 writer、workspace-relative task path、範圍與排除、唯一事實來源、限制、驗收、檢查、完成標記與交接對象。缺 brief 或欄位不足時停止。Reusable renderer 的 metadata contract 位於 `templates/metadata-contract.json`；實際 rendered `brief.md` 才是 task authorization。

模型選擇採成本優先：一般工作優先 `gpt-5.6-luna / max / fast`。`coordinator` 可依複雜度、風險與預期價值選更高階模型，但必須在 brief 簡述偏離預設的理由。若使用 `gpt-5.6-sol`，最高只能 `medium / fast`，不得使用 `high`、`max` 或 `xhigh`。

## Dispatch、startup 與 context 閘門

- 已辨識的 live agent 一律優先使用 atomic `herdr agent prompt <agent-name-or-pane-id> "..."`；以 `herdr agent rename <target> <name>` 固定 native target。`herdr pane rename` 只改顯示 label。
- 新 ready shell 只有在 readiness 可靠時才使用 `herdr agent start <name> --kind <kind> --pane <id>`。first-run auto-update 後退出是 `startup_failed`，不得 prompt stale target；更新完成後只准一次 bounded clean restart，仍失敗才從 fresh shell 用 `herdr pane run` fallback。
- ordinary shell/process 可用 `herdr pane run <pane-id> <command>...`。raw `pane send-text` + `send-keys Enter` 只屬明確標記的 compatibility fallback，不是 recognized agent handoff。
- Codex 在讀 brief 前的 trust cwd prompt 是 `blocked`，不是 `working`；先核對 exact cwd、remote、branch、scope，只對明確授權 workspace 放行，禁止盲答 approval。
- reuse 前必須判斷 prior context、舊 turn 是否已完成與 `/new` 是否安全。只 reset 安全完成的 context 並等待 fresh readiness，否則由 coordinator 在一次 bounded liveness check 確認安全後 close 已完成 pane，再建立 fresh pane；不得讓舊 turn 與新 assignment 重疊。Worker 不得自行 close 或操作 pane。
- Worker boundary 是硬閘門：worker 只能使用 assigned pane 與 foreground commands，不得開 subagent、background agent、watcher、second CLI、extra pane/tab、headless task 或 self-dispatch path。完成 task 的 pane 預設由 coordinator 關閉，不保留 idle 供重用。

## 範圍與安全停點

- 保留既有 dirty／untracked；只修改 brief 授權的精確檔案，不把 worker、搜尋或測試當成擴大範圍的授權。
- 先做最小可驗證切片：先建立能由一個 public seam 驗證的最小垂直結果，再按證據擴充，不先建想像中的完整系統。
- 讀取、搜尋、測試與 diff 檢查通常可直接做；deploy、restart、Secret、外部服務或其他線上 mutation 必須有明確授權。
- 發現範圍不明、failed checks、remote divergence、conflict、dirty overlap、缺 branch／remote 或需要 history rewrite 時停止並回報；不得自行解衝突、`merge`、`rebase`、`amend`、`reset`、force push 或 tag。
- 區分 `current`、`planned`、`historical`、`runtime unknown`；不能把文件、路線圖或 source-only 結果說成執行期已驗證。

## 驗收後持續 Git 發佈

只有必要檢查、獨立 review 與 coordinator acceptance 都完成，且驗收記錄精確列明檔案、repository、branch 與 remote，才可依 standing policy 發佈已驗收內容。此授權不涵蓋其他 dirty／untracked、未驗收內容、其他未明列環境範圍、外部 mutation 或歷史改寫。

符合上述閘門後，coordinator 可依 standing policy 直接完成一般 commit／非強制 push，不必逐次重新詢問；多 repository 依 dependency order 先發佈被依賴的 repository，再更新並發佈依賴它的 repository。

發佈仍須依序完成：

1. 檢查 `status` 與 `diff`。
2. `fetch` 並確認沒有不安全的 divergence。
3. 只 stage 精確路徑，執行 checks，檢視完整 staged diff。
4. 建立一般新 commit，以非強制 push 發佈。
5. 核對 local、tracking、remote SHA 與最後 clean／預期狀態。

任何一步發現衝突、範圍污染、remote 不明或檢查失敗，都在該步停止；不以「先發佈再修」取代驗收。
