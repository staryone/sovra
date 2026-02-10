"""
SOVRA Evolution - Model Merger & Evaluator
Merges LoRA adapters into base model and evaluates quality.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ModelMerger:
    """Merges LoRA adapters into the base model and exports for Ollama."""

    def __init__(self, adapters_dir: Optional[str] = None):
        self.adapters_dir = Path(adapters_dir or "./data/evolution_history/lora_adapters")
        self.merged_dir = Path("./data/evolution_history/merged_models")

    def merge(self, adapter_path: Optional[str] = None) -> dict:
        """Merge the latest LoRA adapter into the base model."""
        # Find the latest adapter if not specified
        if not adapter_path:
            adapter_path = self._find_latest_adapter()
        if not adapter_path:
            return {"status": "error", "message": "No adapter found to merge"}

        logger.info(f"🔀 Merging adapter: {adapter_path}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = self.merged_dir / f"merged_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer

            # Load base model
            base_model_name = os.getenv("SOVRA_HF_MODEL", "Qwen/Qwen3-4B")
            tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                base_model_name, trust_remote_code=True, device_map="auto"
            )

            # Load and merge adapter
            model = PeftModel.from_pretrained(model, adapter_path)
            model = model.merge_and_unload()

            # Save merged model
            model.save_pretrained(str(output_dir))
            tokenizer.save_pretrained(str(output_dir))

            logger.info(f"✅ Merged model saved to: {output_dir}")
            return {"status": "success", "merged_path": str(output_dir), "timestamp": timestamp}

        except Exception as e:
            logger.error(f"Merge failed: {e}")
            return {"status": "error", "message": str(e)}

    def _find_latest_adapter(self) -> Optional[str]:
        """Find the most recent adapter directory."""
        if not self.adapters_dir.exists():
            return None
        adapters = sorted(self.adapters_dir.iterdir(), reverse=True)
        for d in adapters:
            if d.is_dir() and d.name.startswith("adapter_"):
                return str(d)
        return None


class ModelEvaluator:
    """Evaluates evolved model quality before deployment."""

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.eval_prompts = [
            {"input": "Hello, who are you?", "expects": ["Sovra", "sovereign", "autonomous"]},
            {"input": "What are your values?", "expects": ["privacy", "autonomy", "learning"]},
            {"input": "What is 2 + 2?", "expects": ["4"]},
            {"input": "Summarize the concept of privacy in one sentence.", "expects": ["data", "personal", "control"]},
        ]

    async def evaluate(self, model_name: str = "sovra-brain") -> dict:
        """Run evaluation suite against a model."""
        if not self.llm:
            return {"status": "skipped", "message": "No LLM client provided"}

        passed = 0
        total = len(self.eval_prompts)
        results = []

        for eval_item in self.eval_prompts:
            response = await self.llm.generate(eval_item["input"], temperature=0.1)
            match = any(
                keyword.lower() in response.lower()
                for keyword in eval_item["expects"]
            )
            passed += int(match)
            results.append({
                "input": eval_item["input"],
                "response": response[:200],
                "passed": match,
            })

        score = passed / total if total > 0 else 0
        status = "pass" if score >= 0.7 else "fail"

        logger.info(f"📊 Evaluation: {passed}/{total} passed ({score:.0%}) → {status}")
        return {
            "status": status,
            "score": score,
            "passed": passed,
            "total": total,
            "results": results,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    if "--rollback" in sys.argv:
        logger.info("Rolling back to previous model...")
        # Rollback logic would restore previous Ollama model
    else:
        merger = ModelMerger()
        result = merger.merge()
        print(json.dumps(result, indent=2))
