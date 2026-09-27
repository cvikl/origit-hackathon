#!/usr/bin/env bash
# Publish Origit Console to the shared Hetzner box → https://origit.uk
#   bash deploy/publish.sh
# Conventions: app in /opt/origit, container on the existing Caddy network, Caddy drop-in in /opt/caddy-sites,
# zero-downtime `caddy reload`. Touches nothing else on the box. Needs ./.env (see .env.example).
set -euo pipefail
HOST=${SERVER:?set SERVER=user@host of the console box}
APP_DIR=/opt/origit
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/.env" ] || { echo "missing $ROOT/.env (copy .env.example)"; exit 1; }
grep -q '^CONSOLE_TOKEN=.\+' "$ROOT/.env" || { echo "CONSOLE_TOKEN must be set in .env"; exit 1; }

echo "==> rsync sources to $HOST:$APP_DIR"
ssh "$HOST" "mkdir -p $APP_DIR /srv/origit/repos /opt/caddy-sites"
rsync -az --delete --exclude .env --exclude .venv --exclude data --exclude __pycache__ --exclude .pytest_cache --exclude '*.egg-info' --exclude .git \
  "$ROOT/app" "$ROOT/prompts" "$ROOT/seed" "$ROOT/deploy" "$ROOT/vendor" "$ROOT/pyproject.toml" "$ROOT/README.md" "$HOST:$APP_DIR/"
scp -q "$ROOT/.env" "$HOST:$APP_DIR/deploy/.env"
ssh "$HOST" "chmod 600 $APP_DIR/deploy/.env"

echo "==> build + start"
ssh "$HOST" "cd $APP_DIR/deploy && docker compose build origit-console && docker compose up -d origit-console"

echo "==> caddy drop-in + reload"
rsync -az "$ROOT/deploy/origit-uk.caddy" "$HOST:/opt/caddy-sites/origit-uk.caddy"
ssh "$HOST" "cd /opt/compass/deploy && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile"

echo "==> health"
sleep 3
ssh "$HOST" "curl -sf http://127.0.0.1:8787/api/health && echo"
curl -sS -o /dev/null -w "https://origit.uk  HTTP %{http_code}\n" --max-time 30 https://origit.uk/ || echo "  (the origit.uk A record must point at the box; the first HTTPS hit may lag while the certificate is issued)"
