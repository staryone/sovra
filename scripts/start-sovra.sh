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
    export $(grep -v '^#' "${SOVRA_DIR}/.env" | xargs)
fi

# Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo -e "${GREEN}[INFO]${NC} Starting Ollama..."
    sudo systemctl start ollama
    sleep 3
fi

# Start SOVRA Brain (main Python process)
echo -e "${GREEN}[INFO]${NC} Starting SOVRA Brain..."
cd "${SOVRA_DIR}"
python3 -m src.main &
SOVRA_PID=$!

# Start OpenClaw Gateway
echo -e "${GREEN}[INFO]${NC} Starting OpenClaw Gateway..."
openclaw start --config "${SOVRA_DIR}/config/openclaw.json" &
OPENCLAW_PID=$!

echo ""
echo -e "${GREEN}[INFO]${NC} SOVRA is now running!"
echo -e "${GREEN}[INFO]${NC} SOVRA Brain PID: ${SOVRA_PID}"
echo -e "${GREEN}[INFO]${NC} OpenClaw PID: ${OPENCLAW_PID}"
echo -e "${GREEN}[INFO]${NC} OpenClaw Web UI: http://localhost:${OPENCLAW_PORT:-3000}"
echo ""
echo -e "${GREEN}[INFO]${NC} Press Ctrl+C to stop all services."

# Trap Ctrl+C to clean up
cleanup() {
    echo ""
    echo -e "${GREEN}[INFO]${NC} Shutting down SOVRA..."
    kill $SOVRA_PID 2>/dev/null || true
    kill $OPENCLAW_PID 2>/dev/null || true
    echo -e "${GREEN}[INFO]${NC} SOVRA stopped. Goodbye."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for processes
wait
