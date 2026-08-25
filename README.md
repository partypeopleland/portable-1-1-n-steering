# 1:1:N / Herdr

一套讓 AI 助理協同工作的可攜式技能。它把一個複雜工作拆成幾個清楚的小任務，交給不同的 AI 工作者處理，再由一名協調者統一確認結果。

這份 README 給人閱讀；AI 執行規則請看 [`docs/ai-runbook.md`](docs/ai-runbook.md)。

## 這個專案解決什麼問題？

- 讓每個 AI 知道自己要做什麼、不能做什麼。
- 讓程式修改、審查結果和測試證據可以被追蹤。
- 降低多個 AI 同時修改同一份檔案、重複派工或誤把「已送出訊息」當成「工作已完成」的風險。
- 在需要時保留人工確認，不自動部署、重啟或修改機密資料。

## Quick start

### 需要什麼

- Python 3
- 可執行 shell script 的環境
- 一個可寫入的專案或工作區

### 安裝

在這個 repository 的根目錄執行：

```sh
./install.sh
```

預設會安裝到 `~/.agents/skills/herdr-1-1-n`。要安裝到指定工作區：

```sh
./install.sh /path/to/workspace
```

### 產生第一份工作 brief

```sh
python3 scripts/render_brief.py \
  --metadata templates/example-metadata.json
```

預設輸出到終端機；需要寫檔時加上 `--output <path>`。

### 執行檢查

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/smoke_installed_package.py
```

## 基本工作方式

1. 協調者先寫清楚目標、範圍、不能做的事和驗收方式。
2. 工作者只處理被授權的範圍，完成後留下報告與測試結果。
3. 審查者獨立檢查需求、修改內容和證據。
4. 協調者確認所有結果後，才決定是否提交、發布或進行其他外部操作。

## 工作角色

| Profile | 用途 |
| --- | --- |
| `developer` | 修改程式或文件，並回報檢查結果 |
| `reviewer` | 只讀審查需求、標準和差異 |
| `investigation` | 調查現況與可能原因，不直接修復 |
| `design` | 整理決策、替代方案和設計方向 |

## 專案結構

```text
SKILL.md                    AI 技能入口
templates/                  brief 範本與欄位規則
profiles/                   四種工作角色的預設值
scripts/                    brief renderer、流程工具與 smoke check
tests/                      deterministic tests
references/                 技能執行時使用的詳細規則
docs/                       給 AI 閱讀的操作手冊與文件索引
```

## 文件入口

- [`docs/README.md`](docs/README.md)：AI 文件閱讀順序與來源關係。
- [`docs/ai-runbook.md`](docs/ai-runbook.md)：派工、交接、驗收和安全規則。
- [`references/roles-and-gates.md`](references/roles-and-gates.md)：角色和授權閘門。
- [`references/lifecycle-and-handoff.md`](references/lifecycle-and-handoff.md)：工作生命週期和交接。
- [`references/delivery-and-safety.md`](references/delivery-and-safety.md)：證據、文件同步和 Git 安全。

## 安全提醒

這個技能只協助安排工作，不會自動取得權限。部署、重啟、Secret、Discord 或其他外部修改，都必須由使用者明確授權，並在報告中留下可查證的證據。

## License

請依 repository 的授權檔案或發布者提供的授權條款使用。
