"""
SOVRA Evolution - Dataset Builder
Filters and formats interaction logs into training data for LoRA fine-tuning.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """
    Builds training datasets from collected interactions.
    Filters for quality and formats into instructor-style pairs.
    """

    def __init__(
        self,
        interactions_path: Optional[str] = None,
        output_path: Optional[str] = None,
        min_samples: Optional[int] = None,
    ):
        self.interactions_path = Path(
            interactions_path
            or os.getenv("INTERACTION_LOG_PATH", "./data/training/interactions.jsonl")
        )
        self.output_path = Path(
            output_path or "./data/training/dataset.jsonl"
        )
        self.min_samples = min_samples or int(
            os.getenv("EVOLUTION_MIN_SAMPLES", "200")
        )

    def build(self) -> dict:
        """
        Build a training dataset from interaction logs.
        Returns metadata about the build process.
        """
        if not self.interactions_path.exists():
            logger.warning("No interaction logs found. Cannot build dataset.")
            return {"status": "no_data", "samples": 0}

        # Read and filter interactions
        raw_entries = []
        with open(self.interactions_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    raw_entries.append(entry)
                except json.JSONDecodeError:
                    continue

        logger.info(f"Loaded {len(raw_entries)} raw interactions.")

        # Filter for quality
        quality_entries = self._filter_quality(raw_entries)
        logger.info(f"After quality filter: {len(quality_entries)} entries.")

        if len(quality_entries) < self.min_samples:
            logger.warning(
                f"Not enough quality samples: {len(quality_entries)}/{self.min_samples}. "
                f"Need {self.min_samples - len(quality_entries)} more."
            )
            return {
                "status": "insufficient_data",
                "samples": len(quality_entries),
                "needed": self.min_samples,
            }

        # Format into training pairs
        training_data = self._format_training_data(quality_entries)

        # Write output
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info(f"✅ Dataset built: {len(training_data)} training samples → {self.output_path}")

        return {
            "status": "ready",
            "samples": len(training_data),
            "output_path": str(self.output_path),
            "built_at": datetime.now().isoformat(),
        }

    def _filter_quality(self, entries: list[dict]) -> list[dict]:
        """Filter for high-quality interactions suitable for training."""
        quality = []
        for entry in entries:
            # Skip entries with negative feedback
            feedback = entry.get("user_feedback", "")
            if feedback and any(bad in feedback.lower() for bad in ["bad", "wrong", "incorrect", "terrible"]):
                continue

            # Skip entries with very low quality score
            score = entry.get("quality_score")
            if score is not None and score < 0.5:
                continue

            # Skip empty responses
            response = entry.get("llm_response", "")
            if not response or len(response.strip()) < 10:
                continue

            # Skip very short inputs (likely noise)
            user_input = entry.get("user_input", "")
            if not user_input or len(user_input.strip()) < 5:
                continue

            # Skip external API responses (we want to train local model behavior)
            if entry.get("route") == "external":
                continue

            quality.append(entry)

        return quality

    def _format_training_data(self, entries: list[dict]) -> list[dict]:
        """Format filtered entries into instruction-following training pairs."""
        training_data = []
        for entry in entries:
            item = {
                "instruction": entry.get("user_input", ""),
                "input": "",  # Optional context
                "output": entry.get("llm_response", ""),
            }
            training_data.append(item)
        return training_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    builder = DatasetBuilder()
    result = builder.build()
    print(json.dumps(result, indent=2))
