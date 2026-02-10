#!/bin/bash
# ============================================
# SOVRA: Trigger Self-Evolution Cycle
# ============================================
# Run manually or via scheduler:
#   ./scripts/evolve.sh
#   crontab: 0 3 * * 0 /path/to/sovra/scripts/evolve.sh

set -euo pipefail

SOVRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SOVRA_DIR}/venv/bin/activate"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}[EVOLVE]${NC} Starting SOVRA self-evolution cycle..."

# Load environment
if [ -f "${SOVRA_DIR}/.env" ]; then
    export $(grep -v '^#' "${SOVRA_DIR}/.env" | xargs)
fi

cd "${SOVRA_DIR}"

# Step 1: Build dataset from collected interactions
echo -e "${GREEN}[EVOLVE]${NC} Step 1/5: Building training dataset..."
python3 -m src.evolution.dataset_builder
if [ $? -ne 0 ]; then
    echo -e "${RED}[EVOLVE]${NC} Dataset building failed. Aborting."
    exit 1
fi

# Step 2: Run LoRA fine-tuning
echo -e "${GREEN}[EVOLVE]${NC} Step 2/5: Running LoRA fine-tuning..."
python3 -m src.evolution.lora_trainer
if [ $? -ne 0 ]; then
    echo -e "${RED}[EVOLVE]${NC} LoRA training failed. Aborting."
    exit 1
fi

# Step 3: Merge LoRA adapters into base model
echo -e "${GREEN}[EVOLVE]${NC} Step 3/5: Merging LoRA adapters..."
python3 -m src.evolution.model_merger
if [ $? -ne 0 ]; then
    echo -e "${RED}[EVOLVE]${NC} Model merging failed. Aborting."
    exit 1
fi

# Step 4: Evaluate new model
echo -e "${GREEN}[EVOLVE]${NC} Step 4/5: Evaluating new model..."
python3 -m src.evolution.evaluator
EVAL_RESULT=$?
if [ $EVAL_RESULT -ne 0 ]; then
    echo -e "${YELLOW}[EVOLVE]${NC} Quality dropped! Rolling back to previous model."
    python3 -m src.evolution.model_merger --rollback
    exit 1
fi

# Step 5: Deploy new model to Ollama
echo -e "${GREEN}[EVOLVE]${NC} Step 5/5: Deploying evolved model to Ollama..."
ollama create sovra-brain -f "${SOVRA_DIR}/config/ollama-modelfile"

echo ""
echo -e "${GREEN}[EVOLVE]${NC} ✅ Evolution cycle complete! SOVRA has evolved."
echo -e "${GREEN}[EVOLVE]${NC} Evolution log saved to: data/evolution_history/"
