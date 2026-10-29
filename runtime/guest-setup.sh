#!/bin/sh
set -eu
umask 077
state="$HOME/.local/state/opencode-android"
binary="$HOME/.opencode/bin/opencode"
if [ -f "$state/ready-v1" ] && [ -x "$binary" ]; then
    exit 0
fi

printf 'Memasang Bash, curl, Git, dan dependensi Alpine...\n'
apk add --no-cache bash curl ca-certificates git ripgrep libstdc++ libgcc

mkdir -p "$state"
if [ ! -x "$binary" ]; then
    printf 'Mengunduh installer resmi OpenCode 1...\n'
    installer=$(mktemp)
    trap 'rm -f "$installer"' EXIT HUP INT TERM
    # Download first: a failed download must never execute a partial installer.
    curl --fail --show-error --location --retry 3 --connect-timeout 20 \
        https://opencode.ai/install -o "$installer"
    bash "$installer" --no-modify-path
fi
"$binary" --version
mkdir -p "$HOME/projects"
# Mark ready only after a successful runtime smoke test.
printf 'OpenCode 1; Alpine; setup revision 1\n' > "$state/ready-v1.tmp"
mv "$state/ready-v1.tmp" "$state/ready-v1"
