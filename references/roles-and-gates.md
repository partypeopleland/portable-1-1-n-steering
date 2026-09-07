# 角色與工作閘門

本檔是 public package 中角色、工作分類、可見工作閘門、能力導向的執行選擇、範圍授權與 Git publication gate 的唯一 normative source。dispatch、handoff、pane lifecycle 由 [`lifecycle-and-handoff.md`](lifecycle-and-handoff.md) 負責；artifact、review、acceptance evidence 與 Git safety detail 由 [`delivery-and-safety.md`](delivery-and-safety.md) 負責。

## 角色

- `coordinator`：唯一面向使用者，只負責釐清範圍／授權、準備 brief 與依賴順序、派工、接收主動進度與 final handoff、安排獨立驗證／修正、整合結果、回報，以及已授權的精確發佈。
- `worker`：在可見、互動式的 worker environment 執行明確工作；負責調查、設計、source／文件編輯、測試、deploy、runtime checks 與詳細 review 等任務細節，交付 evidence；仍受 brief 與授權限制。
- `developer`：作為 writer 在 brief 明列範圍內修改檔案並交付檢查結果。
- `reviewer`：作為獨立 verifier 唯讀檢查需求、標準、變更與 evidence，只在自己的 task directory 寫 `review.md`。

預設一名 writer、多名唯讀 reviewer。多名 writer 只有在檔案範圍完全分離且 brief 明確授權時才可並行；同一檔案不得有兩名 writer。

## 工作分類與 N gate

實質工作包括實作、正式文件、設計、非簡單調查、測試與審查；開始前 `N >= 1`，且至少一名 worker 必須在可見、互動式 environment 中開始工作。

`N = 0` 只限：

- 對話回答；
- 真正簡單的單一命令或唯讀查詢；
- 派工／驗收記錄；
- 已驗收內容的簡單 Git 發佈，且只改 Git 記錄、不改檔案內容。

禁止 built-in subagent、headless CLI、background terminal、`-p`、只在 commentary 聲稱派工，或以非指定工具取代 brief 要求的可見 worker。

## Brief 與能力選擇

開始前 brief 至少要寫：目標、角色、唯一 writer、workspace-relative task path、範圍與排除、唯一事實來源、限制、驗收、檢查、完成標記與交接對象。缺 brief 或欄位不足時停止。Reusable renderer 的 metadata contract 位於 `templates/metadata-contract.json`；實際 rendered `brief.md` 才是 task authorization。

Select execution capability by task risk, complexity, latency, and available resource signals. Prefer the least capable configuration that can reliably satisfy the acceptance gates; the coordinator may choose a stronger configuration and record the rationale in the task-local brief. Portable guidance must not encode user-specific model names or preferences, provider quota/reset values, private runtime identifiers, or other local operational details.

## 範圍與安全停點

- 保留既有 dirty／untracked；只修改 brief 授權的精確檔案，不把 worker、搜尋或測試當成擴大範圍的授權。
- 先做最小可驗證切片：先建立能由一個 public seam 驗證的最小垂直結果，再按 evidence 擴充，不先建想像中的完整系統。
- 讀取、搜尋、測試與 diff 檢查通常可直接做；deploy、restart、Secret、外部服務或其他線上 mutation 必須有明確授權。
- 發現範圍不明、failed checks、remote divergence、conflict、dirty overlap、缺 branch／remote 或需要 history rewrite 時停止並回報；不得自行解衝突、merge、rebase、amend、reset、force push 或 tag。
- 區分 `current`、`planned`、`historical`、`runtime unknown`；不能把文件、路線圖或 source-only 結果說成執行期已驗證。

## 驗收後 Git publication gate

只有必要檢查、獨立 review 與 coordinator acceptance 都完成，且驗收記錄精確列明檔案、repository、branch 與 remote，才可依 standing policy 發佈已驗收內容。此 gate 不涵蓋其他 dirty／untracked、未驗收內容、其他未明列環境範圍、外部 mutation 或歷史改寫；完整 evidence 與 no-history-rewrite safety 見 [`delivery-and-safety.md`](delivery-and-safety.md)。

多 repository 依 dependency order 發佈；任何一步發現衝突、範圍污染、remote 不明或檢查失敗，都在該步停止，不以「先發佈再修」取代驗收。
