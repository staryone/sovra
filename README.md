# SOVRA: A Sovereign & Self-Evolving AI Agent

> **Keep your data, evolve your soul.**
> A privacy-first autonomous agent powered by Local LLM and OpenClaw.

<p align="center">
  <strong>🧠 Local LLM Brain</strong> · <strong>🔄 Self-Evolving</strong> · <strong>🔒 Privacy-First</strong> · <strong>🤖 Fully Autonomous</strong>
</p>

---

## What is SOVRA?

SOVRA (**Sov**ereign **R**untime **A**gent) is a fully autonomous AI agent that runs entirely on your own infrastructure. It thinks, decides, acts, learns, and evolves — all without sending your data to external servers.

### Key Features

| Feature | Description |
|---|---|
| 🧠 **Local LLM Brain** | Qwen3-4B running via Ollama — your data stays local |
| 🤖 **Full Autonomy** | ReAct loop + Goal Planner — SOVRA decides and acts independently |
| 🔀 **Smart Router** | Routes simple tasks locally, complex tasks to external APIs |
| 📚 **RAG Memory** | Long-term ChromaDB memory with semantic search |
| 🧬 **Self-Evolution** | LoRA fine-tuning from its own interactions |
| 🔒 **API Key Filter** | External API keys never touch the LLM context |
| ⏰ **Proactive Scheduler** | Self-initiated health checks, evolution cycles, monitoring |
| 🪞 **Self-Reflection** | Analyzes failures, learns lessons, adapts strategies |

---

## Architecture

```
┌──────────────────────────────────────────────┐
│                OpenClaw Gateway              │
│            (messaging + skills)              │
└────────────────────┬─────────────────────────┘
                     │
        ┌────────────▼─────────────┐
        │      SOVRA Brain         │
        │  (Personality + Prompt)  │
        └────────────┬─────────────┘
                     │
    ┌────────────────┼───────────────────┐
    │                │                   │
    ▼                ▼                   ▼
┌────────┐   ┌──────────────┐   ┌─────────────┐
│ Smart  │   │  Autonomy    │   │    RAG       │
│ Router │   │  Layer       │   │  Memory      │
└───┬────┘   │ ┌──────────┐ │   │ (ChromaDB)  │
    │        │ │Goal Plan  │ │   └─────────────┘
    ├──Local  │ │Exec Loop │ │
    ├──RAG    │ │Reflection│ │   ┌─────────────┐
    └──API    │ │Scheduler │ │   │ Evolution   │
   (filtered) │ │Decision  │ │   │ (LoRA)      │
              │ └──────────┘ │   └─────────────┘
              └──────────────┘
```

---

## Quick Start

### Prerequisites

- **Ubuntu 24.04 LTS** (recommended)
- **8+ CPU cores**, **16GB RAM**, **50GB storage**
- GPU optional (speeds up training)

### One-Click Install

```bash
git clone https://github.com/YOUR_USERNAME/sovra.git
cd sovra
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This will:
1. Install system dependencies (Python 3.12+, Node.js 22+)
2. Install and configure Ollama with Qwen3-4B
3. Install OpenClaw
4. Set up Python virtual environment
5. Initialize data directories

### Configure

```bash
# Edit your environment variables
cp .env.example .env
nano .env
```

### Run (Bare Metal)

```bash
./scripts/start-sovra.sh
```

---

## 🐳 Running with Docker (Recommended for Production)

Docker deployment ensures SOVRA **auto-restarts** on crash, reboot, or failure — perfect for always-on VPS.

> **💡 Docker is installed automatically by `./scripts/setup.sh`.** If you haven't run it yet, do that first (see [Quick Start](#quick-start)).

### Step 1: Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/sovra.git
cd sovra

# Create your .env from the template
cp .env.example .env
nano .env   # Edit API keys if using external routing (optional)
```

### Step 2: Build & Start All Services

```bash
# Build and start in detached mode (background)
docker compose up -d --build
```

This spins up **4 containers**:

| Container | Service | Port |
|---|---|---|
| `sovra-ollama` | Ollama LLM Server | `11434` |
| `sovra-chromadb` | ChromaDB Vector DB | `8000` |
| `sovra-brain` | SOVRA Brain (Python) | — |
| `sovra-openclaw` | OpenClaw Gateway | `3000` |

### Step 3: Pull the LLM Model (First Time Only)

```bash
# Pull Qwen3-4B into the Ollama container
docker exec -it sovra-ollama ollama pull qwen3:4b

# Pull embedding model
docker exec -it sovra-ollama ollama pull nomic-embed-text

# Create custom SOVRA brain model
docker exec -it sovra-ollama ollama create sovra-brain -f /modelfile
```

### Step 4: Verify Everything is Running

```bash
# Check all containers are up and healthy
docker compose ps

# Check logs
docker compose logs -f sovra-brain

# Test Ollama is responding
curl http://localhost:11434/api/tags
```

### 🔄 Auto-Restart Behavior

All services use `restart: unless-stopped`, which means:

| Scenario | Behavior |
|---|---|
| Container crashes | ✅ Auto-restarts immediately |
| VPS reboots | ✅ Auto-restarts on boot (Docker daemon starts automatically) |
| `docker compose stop` | ❌ Stays stopped (manual stop is respected) |
| `docker compose down` | ❌ Stays stopped (containers removed) |

> **💡 Tip:** To make SOVRA truly survive any reboot, ensure Docker starts on boot:
> ```bash
> sudo systemctl enable docker
> ```

### 🛠️ Useful Docker Commands

```bash
# Start all services
docker compose up -d

# Stop all services (will NOT auto-restart)
docker compose stop

# Restart a specific service
docker compose restart sovra-brain

# View live logs
docker compose logs -f

# View logs for specific service
docker compose logs -f sovra-brain

# Check resource usage
docker stats

# Rebuild after code changes
docker compose up -d --build sovra-brain

# Full reset (removes all containers + data volumes)
docker compose down -v

# Enter a container shell for debugging
docker exec -it sovra-brain bash
docker exec -it sovra-ollama bash
```

### 🎮 GPU Support (Optional)

If your VPS has an NVIDIA GPU, install the NVIDIA Container Toolkit:

```bash
# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

The `docker-compose.yml` already has GPU passthrough configured — it just works.

> **Without GPU:** Remove the `deploy.resources` section from the `ollama` service in `docker-compose.yml`:
> ```yaml
> # Delete or comment out these lines in docker-compose.yml:
> deploy:
>   resources:
>     reservations:
>       devices:
>         - driver: nvidia
>           count: all
>           capabilities: [gpu]
> ```

---

## Project Structure

```
sovra/
├── config/                    # Configuration files
│   ├── personality.json       # Agent personality & autonomy rules
│   ├── router-rules.json      # Smart routing configuration
│   ├── ollama-modelfile       # Custom Ollama model config
│   └── openclaw.json          # OpenClaw gateway config
├── src/                       # Python source code
│   ├── brain/                 # LLM client, personality, prompts
│   ├── autonomy/              # Goal planner, execution, reflection
│   ├── router/                # Smart router, API filter
│   ├── memory/                # RAG pipeline, memory manager
│   ├── evolution/             # LoRA training, dataset building
│   ├── gateway/               # OpenClaw bridge
│   └── main.py                # Entry point
├── scripts/                   # Setup and management scripts
│   ├── setup.sh               # One-click setup
│   ├── start-sovra.sh         # Start all services
│   └── evolve.sh              # Trigger self-evolution
├── docs/                      # Documentation (EN + ID)
├── tests/                     # Test suite
├── requirements.txt           # Python dependencies
└── docker-compose.yml         # Docker orchestration
```

---

## Self-Evolution

SOVRA learns from every interaction and periodically fine-tunes itself:

1. **Collect** — All conversations are logged in JSONL format
2. **Filter** — Quality filtering removes bad/short interactions
3. **Train** — LoRA fine-tuning on high-quality data
4. **Evaluate** — Quality checks ensure the model didn't degrade
5. **Deploy** — New model is deployed to Ollama automatically

Trigger manually:
```bash
./scripts/evolve.sh
```

Or let SOVRA's proactive scheduler handle it automatically (default: weekly).

---

## Configuration

### Personality (`config/personality.json`)

Customize SOVRA's tone, values, autonomy level, and safety boundaries.

### Autonomy Levels

| Level | Behavior |
|---|---|
| `full` | SOVRA decides and acts independently |
| `supervised` | SOVRA proposes, human confirms dangerous actions |
| `restricted` | SOVRA only acts on explicit instructions |

### Router Rules (`config/router-rules.json`)

Control when tasks are handled locally vs. sent to external APIs.

---

## Security

- 🔒 All data stays on your VPS
- 🔑 API keys never enter LLM context (filtered by proxy)
- 🛡️ Dangerous commands require confirmation
- 📝 All actions are logged and auditable
- 🚫 Configurable blocked commands list

---

## Documentation

- 📖 [English Documentation](docs/en/)
- 📖 [Dokumentasi Bahasa Indonesia](docs/id/)

---

## License

MIT License — see [LICENSE](LICENSE)

---

<p align="center">
  <strong>SOVRA</strong> — Built to be sovereign. Designed to evolve.<br>
  <em>Keep your data, evolve your soul.</em>
</p>
