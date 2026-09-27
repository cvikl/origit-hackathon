#!/usr/bin/env bash
# Local dev: import the local demo repo into ./data and serve on :8787.
set -euo pipefail
cd "$(dirname "$0")/.."
export ORIGIT_DATA_DIR=./data CONSOLE_TOKEN=${CONSOLE_TOKEN:-dev} PUBLIC_URL=http://localhost:8787 GIT_SSH_HOST=localhost GIT_SSH_ROOT=$(pwd)/data/repos
DEMO=${1:-$HOME/Documents/bcco/code/origit-demo-payments-api}
if [ ! -d data/repos/acme-payments/payments-api.git ]; then
  .venv/bin/python - "$DEMO" <<'PY'
import sys; from app import gitrepo as G
print(G.import_from_url("acme-payments", "payments-api", sys.argv[1], "Payments API of a fictional EU fintech, built with IBM Bob under Origit. Synthetic data only."))
PY
fi
exec .venv/bin/uvicorn app.main:app --port 8787 --reload
