#!/usr/bin/env bash
# Shared entry point: no seed or environment replacement during normal updates.
set -euo pipefail

initialize=false
case "${1:-}" in
  "") ;;
  --initialize) initialize=true ;;
  *) echo "Usage: $0 [--initialize]" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
test -s backend/.env || { echo "Missing reviewed backend/.env" >&2; exit 1; }
test -s .env.docker || { echo "Missing existing .env.docker" >&2; exit 1; }

compose=(docker compose -f docker-compose.prod.yml --env-file .env.docker)
"${compose[@]}" build api
# Run the image's production validation before replacing any running containers.
"${compose[@]}" run --rm --no-deps api python scripts/deploy_check.py
"${compose[@]}" up -d --wait mysql redis
if "$initialize"; then
  "${compose[@]}" run --rm --no-deps api python scripts/init_production.py
fi
"${compose[@]}" up -d --no-build api

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health
echo
"${compose[@]}" exec -T api python scripts/deploy_check.py
