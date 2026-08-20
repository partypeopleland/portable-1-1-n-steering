#!/bin/sh
set -eu

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

if [ "$#" -ne 1 ]; then
    printf 'usage: %s WORKSPACE\n' "$0" >&2
    exit 64
fi

input=$1
[ -d "$input" ] || die 'workspace must be an existing directory'
[ ! -L "$input" ] || die 'workspace must not be a symlink'
workspace=$(CDPATH= cd "$input" && pwd) || die 'cannot resolve workspace'
script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd) || die 'cannot resolve package'

files='
AGENTS.md
docs/agent/1-1-n/INDEX.md
docs/agent/1-1-n/roles-and-gates.md
docs/agent/1-1-n/lifecycle-and-handoff.md
docs/agent/1-1-n/delivery-and-safety.md
'

for rel in $files; do
    source=$script_dir/$rel
    [ -f "$source" ] || die "package file is missing: $rel"
    [ ! -L "$source" ] || die "package file is a symlink: $rel"
done

for dir in "$workspace/docs" "$workspace/docs/agent" "$workspace/docs/agent/1-1-n"; do
    if [ -L "$dir" ]; then
        die "workspace path is a symlink: $dir"
    fi
    if [ -e "$dir" ] && [ ! -d "$dir" ]; then
        die "workspace path is not a directory: $dir"
    fi
done

for rel in $files; do
    destination=$workspace/$rel
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        die "refusing to overwrite existing file: $rel"
    fi
done

mkdir -p "$workspace/docs/agent/1-1-n"
for rel in $files; do
    cp "$script_dir/$rel" "$workspace/$rel"
done

printf 'installed 1:1:N steering files in %s; restart the Agent session before work.\n' "$workspace"
