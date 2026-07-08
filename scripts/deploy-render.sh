#!/usr/bin/env bash
# Create or update the stock-trader web service on Render via API.
# Requires RENDER_API_KEY in the environment (Account Settings → API Keys).
set -euo pipefail

if [[ -z "${RENDER_API_KEY:-}" ]]; then
  echo "ERROR: Set RENDER_API_KEY (Render Dashboard → Account Settings → API Keys)." >&2
  exit 1
fi

API="https://api.render.com/v1"
REPO="https://github.com/cai40/stock-trader"
BRANCH="main"
SERVICE_NAME="stock-trader"

auth_header() {
  curl -fsS -H "Authorization: Bearer ${RENDER_API_KEY}" -H "Accept: application/json" "$@"
}

echo "Looking for existing service '${SERVICE_NAME}'..."
SERVICES=$(auth_header "${API}/services?limit=100")
SERVICE_ID=$(echo "$SERVICES" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data:
    s = item.get('service') or item
    if s.get('name') == '${SERVICE_NAME}':
        print(s['id'])
        break
")

if [[ -n "${SERVICE_ID}" ]]; then
  echo "Found service ${SERVICE_ID}. Triggering deploy..."
  auth_header -X POST "${API}/services/${SERVICE_ID}/deploys" \
    -H "Content-Type: application/json" \
    -d '{"clearCache":"clear"}' >/dev/null
  URL=$(auth_header "${API}/services/${SERVICE_ID}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('serviceDetails',{}).get('url',''))")
  echo "Deploy started. URL: ${URL:-https://${SERVICE_NAME}.onrender.com}"
  exit 0
fi

echo "No service found. Creating from blueprint settings..."
OWNER_ID=$(auth_header "${API}/owners?limit=20" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not data:
    sys.exit('No Render owner/workspace found for this API key.')
print(data[0]['owner']['id'])
")

PAYLOAD=$(python3 - <<PY
import json
print(json.dumps({
    "type": "web_service",
    "name": "${SERVICE_NAME}",
    "ownerId": "${OWNER_ID}",
    "repo": "${REPO}",
    "branch": "${BRANCH}",
    "autoDeploy": "yes",
    "serviceDetails": {
        "env": "python",
        "plan": "free",
        "region": "oregon",
        "buildCommand": "pip install --no-cache-dir -r requirements.txt",
        "startCommand": "PYTHONPATH=src streamlit run streamlit_app.py --server.port \$PORT --server.address 0.0.0.0 --server.headless true",
        "healthCheckPath": "/",
        "envVars": [{"key": "PYTHON_VERSION", "value": "12.12.0"}],
    },
}))
PY
)

RESP=$(auth_header -X POST "${API}/services" -H "Content-Type: application/json" -d "$PAYLOAD")
URL=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('serviceDetails',{}).get('url',''))")
echo "Service created. URL: ${URL:-https://${SERVICE_NAME}.onrender.com}"
echo "First deploy may take 3–5 minutes."
