#!/bin/bash
# Datadog Marketplace — start all services
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🐶 Starting Datadog Marketplace..."

# ── Backend ──────────────────────────────────────────────────────────────────
echo ""
echo "📦 Setting up Python backend..."
cd "$DIR/backend"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "  Created virtualenv"
fi

source .venv/bin/activate
pip install -q -r requirements.txt

# Seed DB on first run
echo "  Seeding database..."
python3 seed.py

# Start backend with ddtrace
echo "  Starting Flask API on :8080"
DD_SERVICE=ddstore-api \
DD_ENV=demo \
DD_VERSION=1.0.0 \
DD_LOGS_INJECTION=true \
DD_RUNTIME_METRICS_ENABLED=true \
DD_PROFILING_ENABLED=true \
ddtrace-run python3 app.py &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo ""
echo "🖥️  Starting React frontend on :5173..."
cd "$DIR/frontend"
npm install -q
npm run dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "✅ Datadog Marketplace is running!"
echo ""
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8080/api/health"
echo "   Load gen:  python3 loadgen/loadgen.py"
echo ""
echo "Press Ctrl+C to stop all services."

trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
