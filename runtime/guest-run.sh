#!/bin/bash
set -euo pipefail
export PATH="$HOME/.opencode/bin:$PATH"
export TERM="${TERM:-xterm-256color}"
mkdir -p "$HOME/projects"
cd "$HOME/projects"
# Explicit PATH replaces `source ~/.bashrc`; no user rc file is executed.
exec "$HOME/.opencode/bin/opencode" "$@"
