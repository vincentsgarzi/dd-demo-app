#!/bin/bash
# Register all service catalog entries with Datadog.
# Requires DD_API_KEY and DD_APP_KEY environment variables.
# Usage: source backend/.env && bash service-catalog/register.sh

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$DD_API_KEY" ] || [ -z "$DD_APP_KEY" ]; then
  echo "Error: DD_API_KEY and DD_APP_KEY must be set."
  echo "  export DD_API_KEY=your_api_key"
  echo "  export DD_APP_KEY=your_app_key"
  exit 1
fi

DD_SITE="${DD_SITE:-datadoghq.com}"

echo "Registering service catalog entries with Datadog ($DD_SITE)..."

for file in "$DIR"/*.yaml; do
  service=$(basename "$file" .yaml)
  echo -n "  → $service ... "

  response=$(curl -s -w "\n%{http_code}" \
    -X POST "https://api.${DD_SITE}/api/v2/services/definitions" \
    -H "DD-API-KEY: ${DD_API_KEY}" \
    -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import yaml, json, sys
with open('$file') as f:
    data = yaml.safe_load(f)
print(json.dumps(data))
")")

  http_code=$(echo "$response" | tail -1)
  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
    echo "✓ registered"
  else
    echo "✗ HTTP $http_code"
    echo "$response" | head -1 | python3 -m json.tool 2>/dev/null || echo "$response" | head -1
  fi
done

echo ""
echo "Done. View in Datadog: https://app.${DD_SITE}/services"
