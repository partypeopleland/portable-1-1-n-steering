#!/bin/sh
set -eu

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

# Default destination is the global personal skills directory
dest="${1:-$HOME/.agents/skills/herdr-1-1-n}"

# If an existing workspace directory was passed (e.g. ./install.sh /path/to/workspace)
if [ -d "$dest" ] && [ -f "$dest/AGENTS.md" ]; then
    dest="$dest/.agents/skills/herdr-1-1-n"
fi

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd) || die 'cannot resolve package directory'

files="
SKILL.md
references/roles-and-gates.md
references/lifecycle-and-handoff.md
references/delivery-and-safety.md
"

for rel in $files; do
    source="$script_dir/$rel"
    [ -f "$source" ] || die "package file is missing: $rel"
done

mkdir -p "$dest/references"

for rel in $files; do
    cp "$script_dir/$rel" "$dest/$rel"
done

printf 'Successfully installed 1:1:N / Herdr skill to: %s\n' "$dest"
