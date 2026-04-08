#!/bin/bash
# Datadog Marketplace — stop all services
echo "🛑 Stopping Datadog Marketplace..."

# Kill by known ports
for port in 8080 8081 8082 8083 5173; do
  pids=$(lsof -ti:$port 2>/dev/null)
  if [ -n "$pids" ]; then
    echo "  Stopping port $port (PID $pids)"
    echo "$pids" | xargs kill 2>/dev/null
  fi
done

# Kill loadgen (python3 loadgen.py)
pkill -f "loadgen/loadgen.py" 2>/dev/null && echo "  Stopped loadgen"
pkill -f "rum_loadgen.py" 2>/dev/null && echo "  Stopped RUM loadgen"

echo "✅ All services stopped."
