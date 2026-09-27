#!/usr/bin/env bash
# Push the demo fintech repo (branch + Origit notes) to the console. Creates the hosted repo first if needed.
#   CONSOLE_TOKEN=... bash scripts/push-demo.sh [path-to-demo-repo] [org] [name]
set -euo pipefail
DEMO=${1:-$HOME/Documents/bcco/code/origit-demo-payments-api}
ORG=${2:-acme-payments}; NAME=${3:-payments-api}
BASE=${CONSOLE_URL:-https://origit.uk}; HOST=${SERVER:?set SERVER=user@host of the console box}
: "${CONSOLE_TOKEN:?set CONSOLE_TOKEN}"
curl -sf -X POST "$BASE/api/repos" -H "Content-Type: application/json" -H "X-Origit-Token: $CONSOLE_TOKEN" \
  -d "{\"org\":\"$ORG\",\"name\":\"$NAME\",\"description\":\"Payments API of a fictional EU fintech, built with IBM Bob under Origit. Synthetic data only.\"}" && echo || echo "(repo exists or console unreachable, continuing)"
cd "$DEMO"
git remote remove origit 2>/dev/null || true
git remote add origit "$HOST:/srv/origit/repos/$ORG/$NAME.git"
BR=$(git rev-parse --abbrev-ref HEAD)
git push -f origit "$BR" "refs/notes/origit:refs/notes/origit"
echo "→ $BASE/$ORG/$NAME"
