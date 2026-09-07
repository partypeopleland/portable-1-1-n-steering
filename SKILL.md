---
name: herdr-1-1-n
description: Orchestrate multi-agent coordinator-worker collaboration using the 1:1:N / Herdr protocol. Use ONLY when the user explicitly requests "1:1:N", "1-1-n", "Herdr", "多 Agent 派工", or specifically asks for multi-agent dispatch with formal brief/report/review and delivery gates.
---

# 1:1:N / Herdr 協作技能

本技能是可攜的入口與觸發 contract：由一名面向使用者的 `coordinator` 管理範圍、授權、依賴、handoff 與驗收；一名或多名可見 worker 在 brief 授權內執行細節並提供 evidence。完整 active rules 不在本檔複製，請依下列 canonical references 路由。

## 何時啟用

- 使用者明確指定 `1:1:N`、`1-1-n`、`Herdr` 或「多 Agent 派工」。
- 任務明確要求 writer／reviewer 的多角色協同、正式 brief/report/review 與 delivery gates。

常規單檔修改、單純問題排查與不需要多角色 evidence 的工作不因本檔存在而自動啟用。

## Canonical guidance

- [角色與工作閘門](references/roles-and-gates.md)：角色、N gate、能力導向的模型選擇與 Git publication gate。
- [版面與任務交接](references/lifecycle-and-handoff.md)：唯一的 dispatch、bounded acknowledgement、anomaly recovery、handoff 與 pane cleanup 規則。
- [交付、文件與安全](references/delivery-and-safety.md)：唯一的 artifact/review evidence、acceptance、resource checkpoint hook 與 Git safety 規則。

README 與本檔只作 route、觸發、安裝與短摘要；`references/` 是 normative source。`templates/core.md.tmpl` 是 renderer 所需的 rendered safety contract，並由 package tests 保持 semantic markers 同步，不是另一套自由 policy。

## Brief renderer 與 package contract

```sh
python3 scripts/render_brief.py --metadata templates/example-metadata.json
```

Renderer 使用 stdlib-only strict contract，拒絕缺欄位、未知 profile、未解析 placeholder、不安全 path 與 credential-like content。`profiles/` 只提供 role defaults 與 profile-specific fields；artifact path、completion marker 與 handoff target 由 metadata contract／profile defaults 解析。

安裝與有限 smoke：

```sh
./install.sh
python3 scripts/smoke_installed_package.py
```

Package tests 與 smoke 是 source/package evidence，不代表 live Herdr、部署或外部服務已驗證。
