"""
SOVRA Evolution - Interaction Collector
Logs all interactions for future LoRA fine-tuning.
Scores interactions based on quality signals.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class InteractionCollector:
    """
    Collects and stores all interactions in JSONL format.
    Used by the dataset builder to create training data for self-evolution.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(
            log_path or os.getenv("INTERACTION_LOG_PATH", "./data/training/interactions.jsonl")
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._count = self._get_current_count()

    def _get_current_count(self) -> int:
        """Count existing interactions."""
        if self.log_path.exists():
            with open(self.log_path, "r") as f:
                return sum(1 for _ in f)
        return 0

    def log_interaction(
        self,
        user_input: str,
        system_prompt: str,
        llm_response: str,
        route: str = "local",
        quality_score: Optional[float] = None,
        user_feedback: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Log a single interaction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "system_prompt": system_prompt[:500],  # Truncate to save space
            "llm_response": llm_response,
            "route": route,
            "quality_score": quality_score,
            "user_feedback": user_feedback,
            "metadata": metadata or {},
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._count += 1
        if self._count % 50 == 0:
            logger.info(f"📊 {self._count} interactions collected for evolution.")

    def update_feedback(self, timestamp: str, feedback: str, score: float):
        """Update feedback for a specific interaction."""
        if not self.log_path.exists():
            return

        lines = []
        with open(self.log_path, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("timestamp") == timestamp:
                    entry["user_feedback"] = feedback
                    entry["quality_score"] = score
                lines.append(json.dumps(entry, ensure_ascii=False))

        with open(self.log_path, "w") as f:
            f.write("\n".join(lines) + "\n")

    def get_count(self) -> int:
        """Get total interaction count."""
        return self._count

    def get_quality_stats(self) -> dict:
        """Get statistics on interaction quality."""
        if not self.log_path.exists():
            return {"total": 0, "scored": 0, "avg_score": 0}

        total = 0
        scored = 0
        total_score = 0.0

        with open(self.log_path, "r") as f:
            for line in f:
                entry = json.loads(line)
                total += 1
                if entry.get("quality_score") is not None:
                    scored += 1
                    total_score += entry["quality_score"]

        return {
            "total": total,
            "scored": scored,
            "avg_score": round(total_score / scored, 2) if scored > 0 else 0,
        }
