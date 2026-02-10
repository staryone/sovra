#!/bin/bash
# ============================================
# SOVRA: Start All Services
# ============================================

set -euo pipefail

SOVRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SOVRA_DIR}/venv/bin/activate"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Starting SOVRA: A Sovereign & Self-Evolving AI Agent  ║"
echo "║   Keep your data, evolve your soul.                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Load environment
if [ -f "${SOVRA_DIR}/.env" ]; then
    set -a
    source "${SOVRA_DIR}/.env"
    set +a
fi

# Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo -e "${GREEN}[INFO]${NC} Starting Ollama..."
    sudo systemctl start ollama
    sleep 3
fi

# Trap Ctrl+C to clean up
cleanup() {
    echo ""
    echo -e "${GREEN}[INFO]${NC} Shutting down SOVRA..."
    kill $SOVRA_PID 2>/dev/null || true
    echo -e "${GREEN}[INFO]${NC} SOVRA stopped. Goodbye."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start SOVRA Brain (foreground — it handles its own daemon mode)
echo -e "${GREEN}[INFO]${NC} Starting SOVRA Brain..."
cd "${SOVRA_DIR}"

# Check if OpenClaw gateway is already managed as a system service
if command -v openclaw &>/dev/null; then
    # OpenClaw runs as its own daemon via `openclaw gateway`
    # It reads config from ~/.openclaw/openclaw.json automatically
    OPENCLAW_STATUS=$(openclaw status 2>&1 || true)
    if echo "$OPENCLAW_STATUS" | grep -qi "running"; then
        echo -e "${GREEN}[INFO]${NC} OpenClaw gateway is already running."
    else
        echo -e "${GREEN}[INFO]${NC} Starting OpenClaw gateway..."
        openclaw gateway &>/dev/null &
        sleep 2
    fi
    echo -e "${GREEN}[INFO]${NC} OpenClaw Web UI: http://localhost:${OPENCLAW_PORT:-3000}"
fi

echo ""
echo -e "${GREEN}[INFO]${NC} Starting SOVRA Brain (foreground)..."
echo -e "${GREEN}[INFO]${NC} Press Ctrl+C to stop."
echo ""

# Run SOVRA Brain in foreground so it can accept interactive input
python3 -m src.main
SOVRA_PID=$!

wait $SOVRA_PID 2>/dev/null || true
