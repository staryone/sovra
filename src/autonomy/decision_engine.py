"""
SOVRA Autonomy - Decision Engine
Central hub for autonomous decision-making.
Determines: act autonomously vs. ask human, local vs. external, priority ordering.
"""

import json
import logging
import os
from typing import Optional

from ..brain.llm_client import LLMClient
from ..brain.personality import PersonalityEngine

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Makes autonomous decisions for SOVRA:
    - Should I handle this myself or ask the human?
    - Is this within my local LLM's capability?
    - What's the priority and risk level?
    """

    def __init__(
        self,
        llm_client: LLMClient,
        personality: PersonalityEngine,
    ):
        self.llm = llm_client
        self.personality = personality

    async def evaluate(self, request: str, context: str = "") -> dict:
        """
        Evaluate a request and return a decision.
        Returns:
            {
                "action": "execute" | "ask_human" | "refuse",
                "risk_level": "safe" | "moderate" | "dangerous",
                "requires_external": bool,
                "reasoning": str,
                "suggested_approach": str,
            }
        """
        # First, use the personality's risk assessment
        risk = self.personality.get_risk_level(request)

        # If the request contains dangerous commands, check confirmation
        if self.personality.requires_confirmation(request):
            return {
                "action": "ask_human",
                "risk_level": "dangerous",
                "requires_external": False,
                "reasoning": "This action requires human confirmation per safety config.",
                "suggested_approach": request,
            }

        # For safe and moderate actions, use LLM to decide the approach
        prompt = f"""You are an autonomous AI agent making a decision.

Request: "{request}"
{f'Context: {context}' if context else ''}

Your autonomy level: {self.personality.autonomy.get('level', 'full')}

Evaluate this request and decide how to handle it.
Respond with ONLY valid JSON:
{{
    "action": "execute",
    "risk_level": "{risk}",
    "requires_external": false,
    "reasoning": "brief reasoning",
    "suggested_approach": "what to do",
    "task_type": "shell|file|web|api|think",
    "estimated_steps": 1
}}

Rules:
- action "execute" = proceed autonomously
- action "ask_human" = only for truly ambiguous or personal decisions
- action "refuse" = only for clearly harmful/unethical requests
- requires_external = true only if this needs a larger LLM model"""

        response = await self.llm.generate(prompt, temperature=0.2)

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            decision = json.loads(json_str)

            # Override with personality constraints
            if risk == "dangerous" and not self.personality.is_autonomous():
                decision["action"] = "ask_human"
                decision["reasoning"] += " (overridden: autonomy not fully enabled)"

            return decision

        except (json.JSONDecodeError, IndexError):
            # Default to execute if LLM response is unparseable
            return {
                "action": "execute",
                "risk_level": risk,
                "requires_external": False,
                "reasoning": "Default decision: proceed with execution",
                "suggested_approach": request,
            }

    async def should_proactively_act(self, observation: str) -> Optional[dict]:
        """
        Given an observation (e.g., disk is full, service is down),
        decide if SOVRA should proactively take action.
        """
        if not self.personality.is_autonomous():
            return None

        prompt = f"""You observed something on the system:
"{observation}"

Should you take proactive action? If yes, what should you do?
Respond with JSON:
{{
    "should_act": true,
    "action": "what to do",
    "urgency": "immediate|soon|when_convenient",
    "reasoning": "why"
}}"""

        response = await self.llm.generate(prompt, temperature=0.3)

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            decision = json.loads(json_str)
            if decision.get("should_act", False):
                return decision
            return None
        except (json.JSONDecodeError, IndexError):
            return None

    async def classify_complexity(self, message: str) -> dict:
        """
        Classify the complexity of a user message for smart routing.
        Returns: {"level": 1|2|3, "confidence": 0.0-1.0, "needs_rag": bool}
        """
        prompt = f"""Classify the complexity of this request:
"{message}"

Level 1 = Simple (chat, basic Q&A) → local LLM
Level 2 = Medium (needs memory/context) → local LLM + RAG
Level 3 = Complex (deep reasoning, code, math) → external API

Respond with JSON only: {{"level": 1, "confidence": 0.9, "needs_rag": false, "reasoning": "brief"}}"""

        response = await self.llm.generate(prompt, temperature=0.1)

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            result = json.loads(json_str)
            threshold = float(os.getenv("ROUTER_CONFIDENCE_THRESHOLD", "0.7"))

            # If confidence is below threshold, bump up to external
            if result.get("confidence", 1.0) < threshold and result.get("level", 1) < 3:
                result["level"] = 3
                result["reasoning"] = f"Low confidence ({result.get('confidence')}), escalating to external API"

            return result

        except (json.JSONDecodeError, IndexError):
            return {"level": 1, "confidence": 0.5, "needs_rag": False, "reasoning": "parse error, defaulting to local"}
