"""
SOVRA Evolution - LoRA Trainer
Fine-tunes the local LLM using LoRA (Low-Rank Adaptation).
Supports both CPU and GPU training.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LoRATrainer:
    """
    LoRA fine-tuning pipeline for self-evolution.
    Uses PEFT/Transformers (or Unsloth for GPU-accelerated training).
    """

    def __init__(
        self,
        dataset_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        base_model: Optional[str] = None,
    ):
        self.dataset_path = Path(dataset_path or "./data/training/dataset.jsonl")
        self.output_dir = Path(output_dir or "./data/evolution_history/lora_adapters")
        self.base_model = base_model or os.getenv("SOVRA_MODEL", "qwen3:4b")

        # LoRA hyperparameters
        self.lora_r = int(os.getenv("LORA_RANK", "16"))
        self.lora_alpha = int(os.getenv("LORA_ALPHA", "32"))
        self.lora_dropout = float(os.getenv("LORA_DROPOUT", "0.05"))
        self.target_modules = os.getenv("LORA_TARGET_MODULES", "q_proj,v_proj").split(",")

    def train(self) -> dict:
        """
        Run LoRA fine-tuning.
        Returns training metadata.
        """
        if not self.dataset_path.exists():
            logger.error(f"Training dataset not found: {self.dataset_path}")
            return {"status": "error", "message": "Dataset not found"}

        # Load dataset
        dataset = []
        with open(self.dataset_path, "r") as f:
            for line in f:
                dataset.append(json.loads(line))

        logger.info(f"🧬 Starting LoRA training with {len(dataset)} samples...")
        logger.info(f"   Model: {self.base_model}")
        logger.info(f"   LoRA r={self.lora_r}, alpha={self.lora_alpha}")
        logger.info(f"   Target modules: {self.target_modules}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        adapter_dir = self.output_dir / f"adapter_{timestamp}"
        adapter_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Import training libraries
            from datasets import Dataset
            from peft import LoraConfig, get_peft_model, TaskType
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
            )
            from trl import SFTTrainer

            # Resolve model path (convert Ollama model name to HF path)
            hf_model = self._resolve_model_path()

            logger.info(f"   HuggingFace model: {hf_model}")

            # Load tokenizer and model
            tokenizer = AutoTokenizer.from_pretrained(hf_model, trust_remote_code=True)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                hf_model,
                trust_remote_code=True,
                device_map="auto",
            )

            # LoRA configuration
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=self.lora_r,
                lora_alpha=self.lora_alpha,
                lora_dropout=self.lora_dropout,
                target_modules=self.target_modules,
                bias="none",
            )

            # Apply LoRA
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()

            # Prepare dataset
            def format_sample(sample):
                text = f"### Instruction:\n{sample['instruction']}\n\n"
                if sample.get("input"):
                    text += f"### Input:\n{sample['input']}\n\n"
                text += f"### Response:\n{sample['output']}"
                return {"text": text}

            hf_dataset = Dataset.from_list(dataset)
            hf_dataset = hf_dataset.map(format_sample)

            # Training arguments (optimized for CPU/low-end GPU)
            training_args = TrainingArguments(
                output_dir=str(adapter_dir),
                num_train_epochs=3,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=4,
                learning_rate=2e-4,
                warmup_steps=10,
                logging_steps=10,
                save_steps=100,
                save_total_limit=2,
                fp16=False,  # CPU-compatible
                report_to="none",
                optim="adamw_torch",
            )

            # Train
            trainer = SFTTrainer(
                model=model,
                train_dataset=hf_dataset,
                args=training_args,
                tokenizer=tokenizer,
                dataset_text_field="text",
                max_seq_length=2048,
            )

            trainer.train()

            # Save adapter
            model.save_pretrained(str(adapter_dir))
            tokenizer.save_pretrained(str(adapter_dir))

            logger.info(f"✅ LoRA training complete! Adapter saved to: {adapter_dir}")

            return {
                "status": "success",
                "adapter_path": str(adapter_dir),
                "samples": len(dataset),
                "epochs": 3,
                "timestamp": timestamp,
            }

        except ImportError as e:
            logger.error(f"Missing training dependency: {e}")
            logger.error("Install with: pip install torch transformers peft trl datasets")
            return {"status": "error", "message": f"Missing dependency: {e}"}
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"status": "error", "message": str(e)}

    def _resolve_model_path(self) -> str:
        """Convert Ollama model name to HuggingFace model path."""
        model_mapping = {
            "qwen3:4b": "Qwen/Qwen3-4B",
            "qwen3:4b-instruct": "Qwen/Qwen3-4B-Instruct",
            "gemma3:4b": "google/gemma-3-4b-it",
            "phi4-mini": "microsoft/phi-4-mini-instruct",
        }
        base = self.base_model.split(":")[0] + ":" + self.base_model.split(":")[-1] if ":" in self.base_model else self.base_model
        return model_mapping.get(base, f"Qwen/Qwen3-4B")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trainer = LoRATrainer()
    result = trainer.train()
    print(json.dumps(result, indent=2))
