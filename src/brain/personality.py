"""
SOVRA Brain - Personality Engine
Loads and manages the AI's personality traits from config.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "personality.json"


class PersonalityEngine:
    """Manages SOVRA's personality traits and autonomy configuration."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load personality configuration from JSON file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"Loaded personality: {config.get('name', 'Unknown')} v{config.get('version', '?')}")
            return config
        except FileNotFoundError:
            logger.warning(f"Personality config not found at {self.config_path}, using defaults.")
            return self._default_config()

    def _default_config(self) -> dict:
        return {
            "name": "Sovra",
            "version": "0.1.0",
            "tagline": "Keep your data, evolve your soul.",
            "traits": {
                "tone": "friendly and thoughtful",
                "values": ["privacy", "autonomy", "honesty"],
                "communication_style": "clear and warm",
                "humor_level": 0.5,
                "empathy_level": 0.7,
                "curiosity_level": 0.8,
                "assertiveness_level": 0.6,
            },
            "autonomy": {"level": "full"},
        }

    @property
    def name(self) -> str:
        return self.config.get("name", "Sovra")

    @property
    def tagline(self) -> str:
        return self.config.get("tagline", "")

    @property
    def traits(self) -> dict:
        return self.config.get("traits", {})

    @property
    def autonomy(self) -> dict:
        return self.config.get("autonomy", {"level": "full"})

    @property
    def boundaries(self) -> dict:
        return self.config.get("boundaries", {})

    @property
    def expertise_areas(self) -> list[str]:
        return self.config.get("expertise_areas", [])

    @property
    def proactive_behaviors(self) -> dict:
        return self.config.get("proactive_behaviors", {})

    def is_autonomous(self) -> bool:
        """Check if SOVRA is in full autonomy mode."""
        return self.autonomy.get("level", "full") == "full"

    def can_auto_execute(self, action_type: str) -> bool:
        """Check if a specific action can be auto-executed."""
        autonomy = self.autonomy
        mapping = {
            "shell": autonomy.get("auto_execute_shell", True),
            "files": autonomy.get("auto_manage_files", True),
            "packages": autonomy.get("auto_install_packages", True),
            "web": autonomy.get("auto_browse_web", True),
            "schedule": autonomy.get("auto_schedule_tasks", True),
        }
        return mapping.get(action_type, False)

    def requires_confirmation(self, command: str) -> bool:
        """Check if a command requires human confirmation."""
        dangerous_commands = self.autonomy.get("require_confirmation_for", [])
        return any(dangerous in command for dangerous in dangerous_commands)

    def get_risk_level(self, action_description: str) -> str:
        """Assess the risk level of an action."""
        risk_config = self.autonomy.get("risk_assessment", {})
        action_lower = action_description.lower()

        for action in risk_config.get("dangerous", []):
            if action.lower() in action_lower:
                return "dangerous"

        for action in risk_config.get("moderate", []):
            if action.lower() in action_lower:
                return "moderate"

        return "safe"

    def get_system_prompt_vars(self) -> dict:
        """Get variables for system prompt template rendering."""
        return {
            "name": self.name,
            "tagline": self.tagline,
            "tone": self.traits.get("tone", ""),
            "values": ", ".join(self.traits.get("values", [])),
            "communication_style": self.traits.get("communication_style", ""),
            "never_share": ", ".join(self.boundaries.get("never_share", [])),
            "always_disclose": ", ".join(self.boundaries.get("always_disclose", [])),
            "expertise": ", ".join(self.expertise_areas),
        }

    def reload(self):
        """Reload personality config from disk (useful after evolution)."""
        self.config = self._load_config()
        logger.info("Personality config reloaded.")
