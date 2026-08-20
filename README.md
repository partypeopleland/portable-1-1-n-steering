# Portable 1:1:N／Herdr steering distribution

這個 private repository 提供 reviewed、versioned 的 portable 1:1:N steering module 與保守的 `steeringctl` installer。canonical source 只有 `modules/1-1-n/` bundle；installer 與 README 是 Adapter，不會另存一份 steering 正文。使用者必須具有 `partypeopleland/portable-1-1-n-steering` 的 GitHub repository 讀取權限。

## Private-test Quick Start

支援範圍：Python 3.11+、POSIX/Linux、已存在且由你管理的 workspace directory。這個 MVP 需要 `openat`／`renameat` 等 descriptor-relative dir-fd 能力；能力不存在時會 fail closed，不宣稱跨平台。

先以 GitHub 權限 clone private repository，並固定到 coordinator／Owner 控制的 annotated test tag。private test 的 trust anchor 是受控 Git tag，而不是從未驗證的 `SHA256SUMS` 自行計算出的 digest：

```bash
set -eu
gh repo clone partypeopleland/portable-1-1-n-steering
cd portable-1-1-n-steering
TAG=v0.1.0-rc.1
git checkout --detach "$TAG"
test "$(git cat-file -t "refs/tags/$TAG")" = tag || {
  printf 'error: %s is not an annotated tag\n' "$TAG" >&2
  exit 1
}

TAG_MESSAGE="$(git for-each-ref --format='%(contents)' "refs/tags/$TAG")"
EXPECTED_SHA256SUMS_SHA256="$({
  printf '%s\n' "$TAG_MESSAGE" |
    awk '
      /^SHA256SUMS_SHA256=/ {
        count += 1
        value = substr($0, length("SHA256SUMS_SHA256=") + 1)
        if (length(value) != 64 || value ~ /[^0-9A-Fa-f]/) invalid = 1
      }
      END {
        if (count != 1 || invalid) exit 1
        print tolower(value)
      }
    '
} )" || {
  printf 'error: annotated tag message must contain exactly one SHA256SUMS_SHA256=<64hex> line\n' >&2
  exit 1
}

test "$(sha256sum SHA256SUMS | awk '{print $1}')" = "$EXPECTED_SHA256SUMS_SHA256"
sha256sum -c SHA256SUMS

# dry-run：只顯示 bounded unified diff，不寫入 workspace
TARGET=/absolute/path/to/workspace
python3 installer/steeringctl.py install 1-1-n \
  --target "$TARGET" \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256" --dry-run

# 確認 preview 後才套用
python3 installer/steeringctl.py install 1-1-n \
  --target "$TARGET" \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256" --yes
python3 installer/steeringctl.py doctor 1-1-n \
  --target "$TARGET" \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256" --json
```

CLI 在任何 plan/apply 前都會再次驗證 pinned digest、`SHA256SUMS` 的 exact allowlist、每個 release file 與 bundle manifest；缺少、錯誤或多出的 release files 都拒絕。預設是 bounded deterministic unified diff preview；確認 diff 後才使用 `--yes`。安裝完成後請重新啟動 Codex session，再執行 `doctor`；官方 AGENTS.md 文件說明 Codex 在每次 run／TUI session 建立 instruction chain，project instructions 預設 combined limit 為 32 KiB：<https://learn.chatgpt.com/docs/agent-configuration/agents-md>。

Checkout boundary：`.git/**` 是唯一排除的 checkout metadata；所有 non-`.git` paths 仍必須符合 exact release allowlist、`SHA256SUMS` checksum 與 regular non-symlink 檢查。任何 non-`.git` 額外／缺失／竄改檔案或 symlink 都 fail closed，不把 checkout metadata 當成 release content。

若 target 已安裝另一個 version，`doctor`／`update`／`uninstall` 還必須提供對應舊 release 的可信 manifest：

```bash
python3 installer/steeringctl.py update 1-1-n \
  --target /path/to/workspace \
  --release-sha256 "$NEW_RELEASE_SHA256SUMS_SHA256" \
  --installed-release-root /path/to/old-release-root \
  --installed-release-sha256 "$OLD_RELEASE_SHA256SUMS_SHA256" --yes
```

無法取得 receipt 所記 version 的 trusted release 時，CLI 會停止；不要猜測 ownership 或用 `--yes` 當 force。

## Agent prompt

```text
從 private `<repo>` 的受控 annotated tag `v0.1.0-rc.1` checkout；只接受 tag message 中唯一一行 `SHA256SUMS_SHA256=<64hex>` 作為 `--release-sha256` trust anchor。格式缺失、重複或非 64 hex 就停止，再執行 `steeringctl install 1-1-n --release-sha256 <digest> --dry-run`，顯示 bounded unified diff 後才 apply，最後 doctor。不要覆蓋既有 AGENTS.md；若 checksum、managed block 或 receipt conflict 就停止並回報。
```

## Dispatch acknowledgement

派工前只選 `idle`／ready 的可見互動式 Codex pane；不要在 CLI／MCP 啟動、approval prompt 或另一個 task 進行時提交，並先用 `<task-id>` 標籤 pane。優先使用單一原子 text-plus-Enter：

```text
herdr pane run <worker-pane> "<assignment>"
herdr wait agent-status <worker-pane> --status working --timeout <bounded-ms>
```

只有 bounded wait 回報 `working` 才能記錄 `started`。若 timeout，只檢查一次；assignment 仍在 composer 時補一次 `Enter`，再做最後一次 bounded `working` wait，不重送文字。兩次都沒有 `working` 就記錄 `dispatch_failed`，不重派同一 brief，先清除 stale prompt 或證明 pane 無法啟動。每次自然進度回報或收到 handoff 時做一次輕量 liveness audit；`idle`／`done`／`unknown` 且沒有 completion handoff 是 anomaly，不能用 continuous polling 或 watcher 取代處理。

## Update、doctor、uninstall

```bash
python3 installer/steeringctl.py update 1-1-n --target /path/to/workspace \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256"
python3 installer/steeringctl.py update 1-1-n --target /path/to/workspace \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256" --yes
python3 installer/steeringctl.py doctor 1-1-n --target /path/to/workspace \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256"
python3 installer/steeringctl.py uninstall 1-1-n --target /path/to/workspace \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256" --dry-run
python3 installer/steeringctl.py uninstall 1-1-n --target /path/to/workspace \
  --release-sha256 "$EXPECTED_SHA256SUMS_SHA256" --yes
```

`AGENTS.md` 只會由自己的 exact managed block splice；user prose 與其他 module blocks 逐 byte 保留。Module files 只有在 receipt 與 trusted manifest/version/source digest map 一致，且實際 bytes 等於 trusted digest 時才會更新或移除。descriptor-relative transaction 會以同一個已驗證 parent inode 完成 check、parent create、temporary write、replace、rollback 與 delete；symlink、race、能力不足或 rollback 不安全時 fail closed。

Receipt 路徑是 target 的 `.steeringctl/1-1-n.json`，只記 module/version、外部 release digest、manifest digest、trusted source digest map、target digest map、root-created hint 與 managed-block digest；不保存 token、credential 或個資。建議不要把 receipt 加入 Git：它是 machine-local installed state，且不是 trust root；若 workspace policy 必須追蹤，仍要把它視為可變狀態並讓 CLI 以 trusted release 重新授權，不能只靠 receipt 放行。

## Manual fallback

不執行 installer 時，仍可從同一個 fixed release asset 取 exact manifest：`modules/1-1-n/manifest.json` 宣告的五個 payload path 與 SHA-256 必須逐一驗證，再手動複製到 workspace root。手動流程不會取得 installer 的 atomic rollback、descriptor transaction 或 receipt safety；不確定時停止，使用 CLI preview。

## Distribution decision

主要 Adapter 是 GitHub Release CLI：固定 tag、release asset、可信 pinned `SHA256SUMS` digest、exact allowlist、dry-run diff、atomic apply 與 doctor 適合跨 Agent／editor，且不執行 floating `main` 的 remote code。Manual clone／release archive 是同一 payload 的次要 Adapter。

不採 email／逐一 ZIP 作正式分發，因為版本、checksum、更新與撤回沒有可重現的公共索引；不採 submodule／subtree 作預設，因為使用者必須理解 Git plumbing；不採 template-only，因為既有 workspace 的 root registry 與 digest ownership 需要安全 update／uninstall；不採 plugin-only，因為 plugin 不是 steering source，且不能假設它自動合併既有 `AGENTS.md`。

Optional Codex Plugin Adapter 只應提供 install/update/doctor skill，呼叫同一個 GitHub Release CLI／asset，不能內嵌另一份 module docs。本 repository checkout 不建立 plugin scaffold、不申請 marketplace、不建立或 push public repository。官方 Plugins 文件指出 plugin 必須有 `.codex-plugin/plugin.json`，而 public plugin directory 與 local／repo marketplace 是分開來源：<https://developers.openai.com/plugins/build/plugins>。

這個 repository 維持 private，tag 與 release publication 由 Owner／coordinator 依驗收結果管理；本 checkout 不建立 public repository、不建立 plugin 或 marketplace entry，也不自行 publish。

Threat model 限定為防止意外或未核准的內容漂移、path traversal、symlink escape、release/source tamper 與 installer 自己誤刪 user content；不能防止同時擁有 workspace write、trusted release metadata 與 installer 執行權的攻擊者。
