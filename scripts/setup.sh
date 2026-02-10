#!/bin/bash
# ============================================
# SOVRA: One-Click Setup Script for Ubuntu 24
# ============================================
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/sovra/main/scripts/setup.sh | bash
# Or:    chmod +x scripts/setup.sh && ./scripts/setup.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SOVRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   SOVRA: A Sovereign & Self-Evolving AI Agent           ║"
echo "║   Keep your data, evolve your soul.                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# --- Helper functions ---
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_ubuntu() {
    if ! grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
        log_warn "This script is designed for Ubuntu 24.04. Proceed with caution on other distros."
    else
        log_info "Detected Ubuntu: $(lsb_release -d 2>/dev/null | cut -f2)"
    fi
}

# --- Step 1: Install Docker Engine ---
install_docker() {
    if command -v docker &>/dev/null; then
        log_info "Docker already installed: $(docker --version)"
    else
        log_info "Installing Docker Engine..."

        # Remove old/conflicting packages
        for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
            sudo apt-get remove -y $pkg 2>/dev/null || true
        done

        # Add Docker's official GPG key
        sudo apt-get update -qq
        sudo apt-get install -y -qq ca-certificates curl
        sudo install -m 0755 -d /etc/apt/keyrings
        sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        sudo chmod a+r /etc/apt/keyrings/docker.asc

        # Add Docker repository
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

        # Install Docker Engine + Compose
        sudo apt-get update -qq
        sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        log_info "Docker installed: $(docker --version)"
    fi

    # Enable Docker to start on boot (auto-restart)
    sudo systemctl enable docker 2>/dev/null || true
    sudo systemctl start docker 2>/dev/null || true

    # Add current user to docker group (no sudo needed)
    if ! groups | grep -q docker; then
        sudo usermod -aG docker $USER
        log_warn "Added $USER to docker group. You may need to log out and back in."
    fi

    log_info "Docker Compose version: $(docker compose version --short 2>/dev/null || echo 'N/A')"
    log_info "Docker setup complete!"
}

# --- Step 2: System packages ---
install_system_deps() {
    log_info "Installing system dependencies..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        git curl wget jq \
        build-essential \
        ca-certificates gnupg

    # Install Node.js 22+ via NodeSource
    if ! command -v node &>/dev/null || [[ $(node -v | cut -d'.' -f1 | tr -d 'v') -lt 22 ]]; then
        log_info "Installing Node.js 22..."
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
        sudo apt-get install -y -qq nodejs
    fi

    log_info "Node.js version: $(node -v)"
    log_info "Python version: $(python3 --version)"
}

# --- Step 3: Install Ollama ---
install_ollama() {
    if command -v ollama &>/dev/null; then
        log_info "Ollama already installed: $(ollama --version)"
    else
        log_info "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    # Start Ollama service
    log_info "Starting Ollama service..."
    sudo systemctl enable ollama 2>/dev/null || true
    sudo systemctl start ollama 2>/dev/null || true
    sleep 3

    # Pull the model
    log_info "Pulling Qwen3 4B model (this may take a few minutes)..."
    ollama pull qwen3:4b

    # Pull embedding model
    log_info "Pulling nomic-embed-text embedding model..."
    ollama pull nomic-embed-text

    # Create custom SOVRA model with Modelfile
    log_info "Creating custom SOVRA brain model..."
    ollama create sovra-brain -f "${SOVRA_DIR}/config/ollama-modelfile"

    log_info "Ollama setup complete!"
}

# --- Step 4: Install OpenClaw & Auto-Configure ---
install_openclaw() {
    if command -v openclaw &>/dev/null; then
        log_info "OpenClaw already installed."
    else
        log_info "Installing OpenClaw..."
        curl -fsSL https://openclaw.ai/install.sh | bash
    fi

    # --- Skip interactive onboarding, generate config directly ---
    OPENCLAW_DIR="$HOME/.openclaw"
    OPENCLAW_CONFIG="$OPENCLAW_DIR/config.json"
    mkdir -p "$OPENCLAW_DIR/workspace"
    mkdir -p "$OPENCLAW_DIR/memory"

    if [ -f "$OPENCLAW_CONFIG" ]; then
        log_info "OpenClaw config already exists at $OPENCLAW_CONFIG"
        log_info "Skipping auto-config. Edit manually if needed."
    else
        # Generate a random auth token
        AUTH_TOKEN=$(openssl rand -hex 24)

        log_info "Generating OpenClaw config (skipping interactive onboard)..."
        cat > "$OPENCLAW_CONFIG" << OCEOF
{
  "messages": {
    "ackReactionScope": "group-mentions"
  },
  "agents": {
    "defaults": {
      "maxConcurrent": 4,
      "model": "ollama/sovra-brain",
      "subagents": {
        "maxConcurrent": 8
      },
      "compaction": {
        "mode": "safeguard"
      },
      "workspace": "$OPENCLAW_DIR/workspace"
    }
  },
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434"
    }
  },
  "gateway": {
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "$AUTH_TOKEN"
    },
    "port": 3000,
    "bind": "loopback",
    "tailscale": {
      "mode": "off",
      "resetOnExit": false
    },
    "nodes": {
      "denyCommands": [
        "camera.snap", "camera.clip", "screen.record",
        "calendar.add", "contacts.add", "reminders.add"
      ]
    }
  },
  "security": {
    "sandbox_mode": false,
    "blocked_commands": ["rm -rf /", ":(){ :|:& };:", "dd if=/dev/zero of=/dev/sda"]
  },
  "memory": {
    "enabled": true,
    "persistence_path": "$OPENCLAW_DIR/memory"
  }
}
OCEOF
        log_info "✅ OpenClaw config written to $OPENCLAW_CONFIG"
        log_info "🔑 Auth token: $AUTH_TOKEN"
        log_info "   (Save this token — you'll need it to access the gateway)"

        # Save token to .env for reference
        if [ -f "${SOVRA_DIR}/.env" ]; then
            if ! grep -q "OPENCLAW_AUTH_TOKEN" "${SOVRA_DIR}/.env"; then
                echo "" >> "${SOVRA_DIR}/.env"
                echo "# --- OpenClaw Auth (auto-generated) ---" >> "${SOVRA_DIR}/.env"
                echo "OPENCLAW_AUTH_TOKEN=$AUTH_TOKEN" >> "${SOVRA_DIR}/.env"
            fi
        fi
    fi

    log_info "OpenClaw setup complete!"
}

# --- Step 5: Python virtual environment & dependencies ---
setup_python() {
    log_info "Setting up Python virtual environment..."
    cd "${SOVRA_DIR}"

    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    source venv/bin/activate

    log_info "Installing Python dependencies..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q

    log_info "Python environment ready!"
}

# --- Step 6: Initialize data directories ---
init_data() {
    log_info "Initializing data directories..."
    mkdir -p "${SOVRA_DIR}/data/chromadb"
    mkdir -p "${SOVRA_DIR}/data/personality"
    mkdir -p "${SOVRA_DIR}/data/training"
    mkdir -p "${SOVRA_DIR}/data/logs"
    mkdir -p "${SOVRA_DIR}/data/openclaw_memory"
    mkdir -p "${SOVRA_DIR}/data/evolution_history"
    mkdir -p "${SOVRA_DIR}/data/task_queue"

    # Create .env from .env.example if not exists
    if [ ! -f "${SOVRA_DIR}/.env" ]; then
        cp "${SOVRA_DIR}/.env.example" "${SOVRA_DIR}/.env"
        log_warn "Created .env from .env.example — please edit with your actual API keys!"
    fi

    log_info "Data directories initialized!"
}

# --- Step 7: Verify installation ---
verify() {
    echo ""
    log_info "=== Verification ==="

    # Check Docker
    if command -v docker &>/dev/null; then
        log_info "✅ Docker $(docker --version | cut -d' ' -f3 | tr -d ','): OK"
    else
        log_error "❌ Docker not found"
    fi

    # Check Docker auto-start
    if systemctl is-enabled docker &>/dev/null; then
        log_info "✅ Docker auto-start on boot: OK"
    else
        log_warn "⚠️  Docker is NOT set to auto-start on boot"
    fi

    # Check Ollama
    if curl -s http://localhost:11434/api/tags | jq -e '.models[] | select(.name | contains("sovra-brain"))' &>/dev/null; then
        log_info "✅ Ollama + sovra-brain model: OK"
    else
        log_error "❌ Ollama sovra-brain model not found"
    fi

    # Check Node.js
    if command -v node &>/dev/null; then
        log_info "✅ Node.js $(node -v): OK"
    else
        log_error "❌ Node.js not found"
    fi

    # Check OpenClaw
    if command -v openclaw &>/dev/null; then
        log_info "✅ OpenClaw: OK"
    else
        log_warn "⚠️  OpenClaw not found in PATH (may need manual config)"
    fi

    # Check Python venv
    if [ -f "${SOVRA_DIR}/venv/bin/python3" ]; then
        log_info "✅ Python venv: OK"
    else
        log_error "❌ Python venv not found"
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   SOVRA setup complete!                                 ║${NC}"
    echo -e "${GREEN}║                                                         ║${NC}"
    echo -e "${GREEN}║   Run bare metal: ./scripts/start-sovra.sh              ║${NC}"
    echo -e "${GREEN}║   Run via Docker: docker compose up -d --build          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
}

# --- Main ---
main() {
    check_ubuntu
    install_docker
    install_system_deps
    install_ollama
    install_openclaw
    setup_python
    init_data
    verify
}

main "$@"
