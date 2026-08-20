# Private distribution design

## Canonical source 與 Adapters

只有一份 versioned bundle 是 canonical source：`modules/1-1-n/manifest.json` 與它宣告的 exact five-file payload。以下都是 Adapter，不能保存第二份 steering 正文：

1. **Primary：GitHub Release CLI** — private test 先 pin Owner／coordinator 控制的 annotated Git tag；從 tag message 解析唯一 `SHA256SUMS_SHA256=<64hex>` 作 trust anchor，再驗 exact file allowlist／manifest／每檔 digest、先 preview，再 descriptor-relative atomic apply。
2. **Manual：Git clone／release archive** — 給不想執行 installer 的人；使用同一 manifest／payload，手動流程必須自己驗 digest。
3. **Optional：Codex Plugin Adapter** — 只包 install／update／doctor skill，呼叫同一 CLI／release；留作 proposal，不在這次 staging 建立 plugin。

刪除任何 Adapter 不會改變 canonical payload；刪除 bundle 會使所有 Adapter 都無法安全驗證，顯示 bundle 確實是 source。

## Release exact set

Private checkout／release root 必須只包含下列 allowlist 與 `SHA256SUMS`：

```text
.gitignore
README.md
modules/1-1-n/manifest.json
modules/1-1-n/AGENTS.md
modules/1-1-n/docs/agent/1-1-n/INDEX.md
modules/1-1-n/docs/agent/1-1-n/roles-and-gates.md
modules/1-1-n/docs/agent/1-1-n/lifecycle-and-handoff.md
modules/1-1-n/docs/agent/1-1-n/delivery-and-safety.md
installer/steeringctl.py
tests/test_steeringctl.py
docs/distribution.md
SHA256SUMS
```

`__pycache__`、`.pyc`、symlink、空的非 allowlist directory 與任何額外 release file 都是 build failure。`SHA256SUMS` 不把自己列入自己的內容；release metadata 另提供它本身的 pinned SHA-256。CLI 必須同時拒絕缺少、竄改與額外 entries，不能只對已列出的行執行 `sha256sum -c`。

Checkout metadata boundary 是唯一例外：`.git/**` 是唯一排除的 checkout metadata；所有 non-`.git` paths 仍必須逐一符合 exact allowlist、`SHA256SUMS` checksum 與 regular non-symlink 檢查。任何 non-`.git` 額外／缺失／竄改 path、symlink、bytecode 或非 allowlist directory 都 fail closed；不能把其他 hidden directory 或工作檔案視為 metadata 例外。

Release tag、archive SHA-256、manifest SHA-256 與每個 payload digest 必須能在 CI 中重建並互相比對。未來 CI／release steps 應依序：由 host canonical source `cmp` 重建 payload、驗 exact allowlist、禁止 bytecode、跑 installer tests、跑 temp workspace smoke／adversarial tests、產生 deterministic archive、產生 `SHA256SUMS`、發布前由 Owner 核對 trusted release metadata，最後才另行授權 publish。

## Controlled Git tag trust anchor

Private test 必須 checkout 受控的 annotated tag，例如 `TAG=v0.1.0-rc.1`，並確認 `git cat-file -t "refs/tags/$TAG"` 回傳 `tag`。從 `git for-each-ref --format='%(contents)' "refs/tags/$TAG"` 取得 tag message，只接受唯一一行 `SHA256SUMS_SHA256=<64hex>`；缺失、重複、格式錯誤或非 annotated tag 都必須停止。解析出的值才可作為 `steeringctl --release-sha256` 的 EXPECTED；不能用未驗證的 `SHA256SUMS` 自行產生 trust root。

## CLI contract 與 trust seams

```text
install 1-1-n --target <workspace> --release-sha256 <pinned-SHA256SUMS-digest> [--dry-run] [--yes]
update 1-1-n --target <workspace> --release-sha256 <pinned-SHA256SUMS-digest> [--dry-run] [--yes]
doctor 1-1-n --target <workspace> --release-sha256 <pinned-SHA256SUMS-digest> [--json]
uninstall 1-1-n --target <workspace> --release-sha256 <pinned-SHA256SUMS-digest> [--dry-run] [--yes]
version 1-1-n
```

當 receipt 的 version 不是目前 release，`doctor`／`update`／`uninstall` 還要以 `--installed-release-root` 與 `--installed-release-sha256` 提供對應 trusted manifest；離線沒有它就停止，不猜 ownership。

`steeringctl` 是 standard-library-first prototype。它先把 release root 載入 immutable bytes snapshot，驗證外部 `SHA256SUMS` trust gate、exact allowlist、manifest 與 payload digest；plan、diff、apply 與 receipt 都只消費同一 snapshot，不會在驗證後重讀 source。任何 target mutation 都在已開啟的 workspace directory fd 與 descriptor-relative parent fd 上進行：parent inode 綁定後才 create、temp write、replace、rollback 或 delete，並以 `O_NOFOLLOW`／inode check 保護；必要能力不存在、namespace race 或 rollback 不安全時 fail closed。

Root `AGENTS.md` 是 composition seam：固定 root Interface 只要求載入每個 required managed module block；每個 module block 自己提供 required 狀態、何時載入、唯一相對 INDEX 與缺失停止行為。installer 只 splice 自己的 exact marker block，不 hash／own 整份 root，也不使用 LLM merge arbitrary prose。Receipt 是 installed state，不是 trust root；doctor/update/uninstall 要把 receipt 的 module/version/manifest/source map 與 trusted release 完整比對，並再核對 actual target bytes。

Dry-run 輸出 bounded deterministic unified diff：text files 顯示 before/after，binary／大檔只顯示固定 digest/size 摘要；fresh install、existing root、update、uninstall 的 diff 都可審查且不寫入 target。`--yes` 不是 force；managed content、receipt、root marker 或 release identity conflict 都停止。

## Dispatch liveness Adapter rule

派工 lifecycle 的 canonical text 在 payload 的 `lifecycle-and-handoff.md`；這裡只記 distribution 不可違反的 seam：ready pane 先 gate，使用 `herdr pane run <worker-pane> "<assignment>"` 原子提交，並以一次 bounded `herdr wait agent-status <worker-pane> --status working --timeout <bounded-ms>` 證明 submitted。timeout 只允許一次 pane inspection、一次獨立 Enter recovery 與最後一次 bounded wait；仍未進入 `working` 必須是 `dispatch_failed`，不可宣稱 started 或重派同一 brief。每個自然 coordinator turn／progress report／incoming handoff 做一次輕量 liveness audit；不得加 background watcher、continuous polling 或 transcript loop。Direct handoff 維持 at-most-once，成功 API write 不等於已收到。

## Receipt 與 recovery

Receipt 位於 target 的 `.steeringctl/1-1-n.json`，建議不追蹤 Git；它只記錄安裝狀態，不是 ownership authority。若 receipt 或 managed payload 被改，只有與可信 manifest/version/source digest map 完整相符才可繼續；否則提示重新取得對應 pinned release。apply 使用 target 內 temporary files 與同 parent fd 的 atomic replace；失敗會用同一 inode-bound handles rollback，rollback 也失敗就報錯並停止，不留下「看似完成」的半套。

## Optional plugin adapter

Plugin 不是 canonical steering source，也不是 installer 的必要 runtime。若未來實作，plugin 只含一個受審的 install/update/doctor skill 或 wrapper，所有 payload 與 checksum 仍來自 pinned GitHub Release CLI；不得把五份 docs 再複製一份進 plugin。

官方 Plugins 文件指出每個 plugin 的 required entry point 是 `.codex-plugin/plugin.json`，可再含 `skills/`、MCP、assets 或 hooks；public plugin directory、local marketplace 與 repo marketplace 是不同分發來源，marketplace source 可用 pinned Git ref。這支持 plugin 作 optional Adapter，而不是替代 GitHub Release：<https://developers.openai.com/plugins/build/plugins>。

本 staging 不建立 `.codex-plugin/`、不加入 marketplace、不建立 public repo、不 push。若 Owner 未來選擇 plugin Adapter，仍需另立 brief，指定 plugin owner、permissions、source pin、review、marketplace scope 與 uninstall 行為。

## README／安全與未決策

README 必須提供 30 秒 Quick Start、Agent prompt、update／doctor／uninstall、manual fallback、prerequisites、supported Python/POSIX scope、version pin、可信 checksum、restart reminder、receipt path/tracking policy 與 remote-shell tradeoff。便利 bootstrap 若未來提供，必須明示其 trust tradeoff，不能只提供 `curl | sh`。

本 staging 只保證 Python 3.11+ 與 POSIX/Linux local filesystem workspace；沒有宣稱跨平台 installer、live GitHub release、plugin publication 或 runtime deployment。Public repo owner、repo name、license（建議 MIT）仍由 Owner 決定；沒有填假姓名或建立 `LICENSE`。
