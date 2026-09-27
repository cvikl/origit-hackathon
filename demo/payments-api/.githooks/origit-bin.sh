#!/bin/sh
# Locate the origit CLI: $ORIGIT_BIN, git config origit.bin, PATH, then a venv inside the repo.
top=$(git rev-parse --show-toplevel 2>/dev/null)
for c in "$ORIGIT_BIN" "$(git config --get origit.bin 2>/dev/null)" "$(command -v origit 2>/dev/null)" "$top/origit/.venv/bin/origit" "$top/.venv/bin/origit"; do
  [ -n "$c" ] && [ -x "$c" ] && { echo "$c"; exit 0; }
done
exit 1
