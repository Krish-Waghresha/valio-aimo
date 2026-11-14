#!/usr/bin/env bash
# Start a clean live-data workspace for a demo run.
# Usage: scripts/demo_reset.sh [port]
# Requires VALIO_API_KEY in the environment or in an untracked .env file.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8003}"
ORIGIN="http://127.0.0.1:${PORT}"
DIR="data/gateway/demo-$(date +%Y%m%d-%H%M%S)"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
: "${VALIO_API_KEY:?Set VALIO_API_KEY (or add it to .env)}"
lsof -ti "tcp:${PORT}" -sTCP:LISTEN | xargs kill 2>/dev/null || true
uv run aimo-gateway init --mode live --database "${DIR}/gateway.sqlite" --origin "${ORIGIN}" | grep -vi token
# Hotel kitchen policy: buyer orders alone up to EUR 500; manager approves up to EUR 5,000 per order.
uv run aimo-gateway policy --mode live --database "${DIR}/gateway.sqlite" --autonomous-limit 50000 --order-limit 500000 --daily-limit 2000000 --manager-approval-limit 500000
ln -sfn "$(basename "${DIR}")" data/gateway/demo-current
echo "Login tokens: ${DIR}/credentials.json (chef = buyer, manager = approver)"
echo "Open ${ORIGIN}/"
exec uv run aimo-gateway serve --workspace --mode live --database "${DIR}/gateway.sqlite" --port "${PORT}" --origin "${ORIGIN}"
