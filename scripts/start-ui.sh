#!/usr/bin/env bash
# Start Streamlit UI and expose via bore.pub tunnel (works from iPhone browser).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

python3 -m pip install -q -e ".[ui]"

# Start Streamlit if not already running
if ! curl -sf http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
  SESSION_NAME="stock-trader-ui"
  if ! tmux -f /exec-daemon/tmux.portal.conf has-session -t "=$SESSION_NAME" 2>/dev/null; then
    tmux -f /exec-daemon/tmux.portal.conf new-session -d -s "$SESSION_NAME" -c "$ROOT" -- "${SHELL:-bash}" -l
  fi
  tmux -f /exec-daemon/tmux.portal.conf send-keys -t "$SESSION_NAME:0.0" \
    "python3 -m streamlit run src/stock_trader/ui.py --server.headless=true --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=false" C-m
  echo "Starting Streamlit..."
  for _ in $(seq 1 30); do
    curl -sf http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1 && break
    sleep 1
  done
fi

# Download bore if needed
if [[ ! -x /tmp/bore ]]; then
  curl -fsSL -o /tmp/bore.tar.gz \
    https://github.com/ekzhang/bore/releases/download/v0.5.1/bore-v0.5.1-x86_64-unknown-linux-musl.tar.gz
  tar -xzf /tmp/bore.tar.gz -C /tmp bore
  chmod +x /tmp/bore
fi

# Start tunnel
SESSION_NAME="ui-tunnel"
if ! tmux -f /exec-daemon/tmux.portal.conf has-session -t "=$SESSION_NAME" 2>/dev/null; then
  tmux -f /exec-daemon/tmux.portal.conf new-session -d -s "$SESSION_NAME" -c "$ROOT" -- "${SHELL:-bash}" -l
fi
tmux -f /exec-daemon/tmux.portal.conf send-keys -t "$SESSION_NAME:0.0" \
  "/tmp/bore local 8501 --to bore.pub 2>&1 | tee /tmp/bore.log" C-m

echo "Waiting for public URL..."
for _ in $(seq 1 20); do
  if grep -q "listening at bore.pub" /tmp/bore.log 2>/dev/null; then
  URL=$(grep -o 'bore.pub:[0-9]*' /tmp/bore.log | tail -1)
  echo ""
  echo "============================================"
  echo "  Open on your iPhone:"
  echo "  http://$URL"
  echo "============================================"
  exit 0
  fi
  sleep 1
done

echo "Tunnel starting — check: tmux attach -t ui-tunnel"
cat /tmp/bore.log 2>/dev/null || true
