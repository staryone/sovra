"""
SOVRA Router - Smart Router
Routes requests between local LLM, local LLM + RAG, and external APIs
based on complexity classification by the decision engine.
"""

import logging
import os
from typing import Optional

from ..brain.llm_client import LLMClient
from ..brain.system_prompt import SystemPromptBuilder
from ..autonomy.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


class SmartRouter:
    """
    Routes tasks to the appropriate handler:
    - Level 1: Local LLM (simple tasks)
    - Level 2: Local LLM + RAG (memory-dependent tasks)
    - Level 3: External API (complex tasks beyond local capability)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        decision_engine: DecisionEngine,
        prompt_builder: SystemPromptBuilder,
        api_filter=None,
        rag_pipeline=None,
    ):
        self.llm = llm_client
        self.decision = decision_engine
        self.prompt_builder = prompt_builder
        self.api_filter = api_filter
        self.rag = rag_pipeline
        self.stats = {"local": 0, "local_rag": 0, "external": 0}

    async def route(
        self,
        message: str,
        conversation_history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Route a message to the appropriate handler.
        Returns: {"response": str, "route": str, "metadata": dict}
        """
        # Classify complexity
        classification = await self.decision.classify_complexity(message)
        level = classification.get("level", 1)
        needs_rag = classification.get("needs_rag", False)

        logger.info(
            f"🔀 Routing decision: Level {level}, "
            f"confidence={classification.get('confidence', 0):.2f}, "
            f"needs_rag={needs_rag}"
        )

        # Override: if level 2 or needs_rag, use RAG
        if level == 2 or needs_rag:
            return await self._route_local_rag(message, conversation_history, system_prompt)
        elif level == 3:
            return await self._route_external(message, conversation_history, system_prompt)
        else:
            return await self._route_local(message, conversation_history, system_prompt)

    async def _route_local(
        self, message: str, history: Optional[list[dict]], system: Optional[str]
    ) -> dict:
        """Handle through local LLM only."""
        self.stats["local"] += 1
        logger.info("📍 Route: LOCAL LLM")

        if not system:
            system = self.prompt_builder.build()

        if history:
            messages = history + [{"role": "user", "content": message}]
            response = await self.llm.chat(messages, system=system)
        else:
            response = await self.llm.generate(message, system=system)

        return {
            "response": response,
            "route": "local",
            "metadata": {"model": self.llm.model},
        }

    async def _route_local_rag(
        self, message: str, history: Optional[list[dict]], system: Optional[str]
    ) -> dict:
        """Handle through local LLM + RAG memory retrieval."""
        self.stats["local_rag"] += 1
        logger.info("📍 Route: LOCAL LLM + RAG")

        # Retrieve relevant context from RAG
        rag_context = ""
        if self.rag:
            try:
                results = await self.rag.search(message)
                if results:
                    rag_context = "\n\n".join(
                        [f"[Memory] {r['content']}" for r in results]
                    )
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        # Build system prompt with RAG context
        conversation_context = ""
        if history:
            recent = history[-5:]
            conversation_context = "\n".join(
                [f"{m['role']}: {m['content']}" for m in recent]
            )

        system = self.prompt_builder.build(
            rag_context=rag_context,
            conversation_context=conversation_context,
        )

        if history:
            messages = history + [{"role": "user", "content": message}]
            response = await self.llm.chat(messages, system=system)
        else:
            response = await self.llm.generate(message, system=system)

        return {
            "response": response,
            "route": "local_rag",
            "metadata": {
                "model": self.llm.model,
                "rag_results": len(rag_context.split("[Memory]")) - 1 if rag_context else 0,
            },
        }

    async def _route_external(
        self, message: str, history: Optional[list[dict]], system: Optional[str]
    ) -> dict:
        """Handle through external API (GPT/Claude)."""
        self.stats["external"] += 1
        logger.info("📍 Route: EXTERNAL API")

        if self.api_filter:
            try:
                response = await self.api_filter.call(
                    message=message,
                    history=history,
                    system_prompt=system or self.prompt_builder.build(),
                )
                return {
                    "response": response,
                    "route": "external",
                    "metadata": {"provider": self.api_filter.active_provider},
                }
            except Exception as e:
                logger.warning(f"External API failed: {e}. Falling back to local.")
                return await self._route_local(message, history, system)
        else:
            logger.warning("No API filter configured. Falling back to local.")
            return await self._route_local(message, history, system)

    def get_stats(self) -> dict:
        """Return routing statistics."""
        total = sum(self.stats.values()) or 1
        return {
            **self.stats,
            "total": total,
            "local_percentage": round(self.stats["local"] / total * 100, 1),
            "external_percentage": round(self.stats["external"] / total * 100, 1),
        }
