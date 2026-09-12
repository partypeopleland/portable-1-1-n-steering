#!/bin/sh
set -eu

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

dest="${1:-$HOME/.agents/skills/plan-gated-execution}"
if [ -d "$dest" ] && [ -f "$dest/AGENTS.md" ]; then
    dest="$dest/.agents/skills/plan-gated-execution"
fi

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd) || die 'cannot resolve package directory'

files="
SKILL.md
README.md
install.sh
references/protocol.md
references/review-contract.md
references/execution-and-safety.md
scripts/render_plan.py
scripts/validate_plan_gate.py
scripts/smoke_installed_package.py
"

directories="
templates
tests
docs
"

for rel in $files; do
    source="$script_dir/$rel"
    [ -f "$source" ] || die "package file is missing: $rel"
done
for dir in $directories; do
    [ -d "$script_dir/$dir" ] || die "package directory is missing: $dir"
done

mkdir -p "$dest" "$dest/references" "$dest/scripts"
for dir in $directories; do
    mkdir -p "$dest/$dir"
done
for rel in $files; do
    cp "$script_dir/$rel" "$dest/$rel"
done
for dir in $directories; do
    cp -R "$script_dir/$dir/." "$dest/$dir/"
done

printf 'Successfully installed Plan-Gated Execution skill to: %s\n' "$dest"
