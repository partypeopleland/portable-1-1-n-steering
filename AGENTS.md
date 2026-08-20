# 工作區協作規範

本檔是啟動入口；詳細規則由下列 module registry 分流，不在根檔複製流程正文。

## 啟動

讀完本檔後，依 Module registry 載入每一個標為 `required` 的 managed module block。每個 block 都必須提供自己的唯一相對 `INDEX.md` 入口；required block、入口或 INDEX 不存在、讀不到或與任務衝突時立即停止，不猜測替代規則。目標倉庫自己的 `AGENTS.md` 仍負責該倉庫的細節，但不得放寬本檔與 module 的安全規則。

## Module registry

<!-- steeringctl:managed-module:1-1-n:start -->
## Required module activation

- 狀態：`required`。
- 何時載入：讀完根檔後、開始任何實質工作或簡單 Git 發佈前。
- 唯一入口：[`1:1:N／Herdr INDEX`](docs/agent/1-1-n/INDEX.md)。
- 若這個 required module block、相對連結或 INDEX 缺失／讀不到，立即停止並回報；不要建立替代流程。

| Module | Version | 何時需要 | 唯一入口 |
|---|---|---|---|
| `1:1:N／Herdr` | `0.1.0` | 實作、正式文件、設計、測試、調查、審查、派工、交接與驗收 | [`docs/agent/1-1-n/INDEX.md`](docs/agent/1-1-n/INDEX.md) |
<!-- steeringctl:managed-module:1-1-n:end -->

新增 module 時，只在 `docs/agent/<module-name>/` 建立自足的 `INDEX.md` 與實作文件，再在本表增加一列；不得把新 module 正文複製到根檔。刪除 module 時移除該列與資料夾即可。

## 根安全原則

- 使用者只和一名 `coordinator` 溝通；`coordinator` 只負責範圍／授權、brief／依賴順序、派工、進度與 handoff、驗收協調、回報及已授權精確發佈；worker 負責任務細節。保留既有 dirty／untracked，工作範圍不得自行擴張。
- 未完成驗收與必要審查，不得 commit／push；deploy、restart、Secret 或其他外部 mutation 仍須明確授權。
- 不能把 planned、source-only 或文件敘述說成 current 或已在執行期驗證。
