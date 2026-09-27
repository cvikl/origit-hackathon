#!/usr/bin/env bash
# Copy cached Bob output (evidence + Article 14 drafts) from a console state dir into seed/ so it ships with the image.
#   bash scripts/seed-from-state.sh [state-dir]        default: data/state
# From the server: docker cp origit-console:/data/state ./state-copy && bash scripts/seed-from-state.sh ./state-copy
# Only evidence/, drafts/ and push-evidence/ json files are copied; pushes.jsonl and everything else stay behind. Nothing is deleted.
set -euo pipefail
cd "$(dirname "$0")/.."
STATE=${1:-data/state}
[ -d "$STATE" ] || { echo "no state dir at $STATE"; exit 1; }
n=0
while IFS= read -r -d '' f; do
  rel=${f#"$STATE"/}                       # <org>/<name>/(evidence|drafts)/<file>.json
  org=${rel%%/*}; rest=${rel#*/}; name=${rest%%/*}; rest=${rest#*/}; kind=${rest%%/*}; base=${rest#*/}
  mkdir -p "seed/$kind/$org/$name"
  cp "$f" "seed/$kind/$org/$name/$base"
  n=$((n+1))
done < <(find "$STATE" -mindepth 4 -maxdepth 4 -type f -name '*.json' \( -path '*/evidence/*' -o -path '*/drafts/*' -o -path '*/push-evidence/*' \) -print0)
echo "copied $n file(s) into seed/ (evidence + drafts + push-evidence). Review with: git status seed/"
