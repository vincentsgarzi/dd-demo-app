#!/bin/bash
# Datadog Marketplace — start all microservices
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🐶 Starting Datadog Marketplace (microservices)..."

# ── Backend setup ─────────────────────────────────────────────────────────────
echo ""
echo "📦 Setting up Python backend..."
cd "$DIR/backend"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "  Created virtualenv"
fi

source .venv/bin/activate
pip install -q -r requirements.txt

# ── Common ddtrace env vars ──────────────────────────────────────────────────
export DD_ENV=demo
export DD_VERSION=1.0.0
export DD_LOGS_INJECTION=true
export DD_RUNTIME_METRICS_ENABLED=true
export DD_PROFILING_ENABLED=true
export DD_TRACE_REMOVE_INTEGRATION_SERVICE_NAMES_ENABLED=true
export DD_DBM_PROPAGATION_MODE=full

# Seed DB (DD_TRACE_ENABLED=false prevents seed from sending traces as wrong service)
echo "  Seeding database..."
DD_TRACE_ENABLED=false python3 seed.py

# ── Start microservices ──────────────────────────────────────────────────────
echo ""
echo "🚀 Starting microservices..."

echo "  → Product Service on :8081"
DD_SERVICE=ddstore-products ddtrace-run python3 products/app.py &
PRODUCTS_PID=$!

echo "  → Order Service on :8082"
DD_SERVICE=ddstore-orders ddtrace-run python3 orders/app.py &
ORDERS_PID=$!

echo "  → Analytics Service on :8083"
DD_SERVICE=ddstore-analytics ddtrace-run python3 analytics/app.py &
ANALYTICS_PID=$!

# Give downstream services a moment to start before the gateway
sleep 2

echo "  → API Gateway on :8080"
DD_SERVICE=ddstore-gateway ddtrace-run python3 gateway/app.py &
GATEWAY_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
echo ""
echo "🖥️  Starting React frontend on :5173..."
cd "$DIR/frontend"
npm install -q
npm run dev &
FRONTEND_PID=$!

# ── Load generator ───────────────────────────────────────────────────────────
echo ""
echo "📊 Starting load generator..."
cd "$DIR"
source backend/.venv/bin/activate
python3 loadgen/loadgen.py 1.5 &
LOADGEN_PID=$!
echo "  Loadgen PID: $LOADGEN_PID"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "✅ Datadog Marketplace is running!"
echo ""
echo "   Frontend:   http://localhost:5173"
echo "   Gateway:    http://localhost:8080/api/health"
echo "   Products:   http://localhost:8081/api/health"
echo "   Orders:     http://localhost:8082/api/health"
echo "   Analytics:  http://localhost:8083/api/health"
echo "   Load gen:   running (PID $LOADGEN_PID)"
echo ""
echo "   Service Map: gateway → {products, orders, analytics} → postgres"
echo ""
echo "Press Ctrl+C to stop all services."

trap "echo ''; echo 'Stopping all services...'; kill $GATEWAY_PID $PRODUCTS_PID $ORDERS_PID $ANALYTICS_PID $FRONTEND_PID $LOADGEN_PID 2>/dev/null; exit" INT TERM
wait
