"""
SOVRA Gateway - OpenClaw Bridge
Bridges OpenClaw's agent runtime with SOVRA's brain, autonomy, and memory systems.
This is the glue that connects everything together.
"""

import asyncio
import json
import logging
from typing import Optional

from ..brain.llm_client import LLMClient
from ..brain.personality import PersonalityEngine
from ..brain.system_prompt import SystemPromptBuilder
from ..autonomy.goal_planner import GoalPlanner, TaskPriority
from ..autonomy.execution_loop import ExecutionLoop
from ..autonomy.decision_engine import DecisionEngine
from ..autonomy.self_reflection import SelfReflection
from ..autonomy.scheduler import ProactiveScheduler
from ..router.smart_router import SmartRouter
from ..router.api_filter import APIFilter
from ..memory.rag_pipeline import RAGPipeline
from ..memory.memory_manager import MemoryManager
from ..evolution.collector import InteractionCollector
from ..security.secret_vault import SecretVault

logger = logging.getLogger(__name__)


class OpenClawBridge:
    """
    Central bridge that connects OpenClaw with SOVRA subsystems.
    Handles incoming messages, routes them, and manages autonomy.
    """

    def __init__(self):
        # Core components
        self.llm = LLMClient()
        self.personality = PersonalityEngine()
        self.prompt_builder = SystemPromptBuilder(self.personality)

        # Memory
        self.rag = RAGPipeline(self.llm)
        self.memory = MemoryManager(self.llm, self.rag)

        # Router
        self.api_filter = APIFilter()
        self.decision_engine = DecisionEngine(self.llm, self.personality)
        self.router = SmartRouter(
            self.llm, self.decision_engine, self.prompt_builder,
            api_filter=self.api_filter, rag_pipeline=self.rag,
        )

        # Autonomy
        self.goal_planner = GoalPlanner(self.llm, self.prompt_builder)
        self.execution_loop = ExecutionLoop(
            self.llm, self.personality, self.prompt_builder, self.goal_planner
        )
        self.self_reflection = SelfReflection(
            self.llm, self.prompt_builder, self.goal_planner, memory_store=self.rag
        )
        self.scheduler = ProactiveScheduler(self.goal_planner, self.personality)

        # Wire up reflection callback
        self.execution_loop.set_reflection_callback(self.self_reflection.reflect)

        # Evolution
        self.collector = InteractionCollector()

        # Security
        self.vault = SecretVault()

        logger.info(f"🧠 SOVRA Bridge initialized: {self.personality.name}")

    async def handle_message(self, user_message: str, platform: str = "web") -> str:
        """
        Handle an incoming message from any platform.
        OpenClaw-first: single LLM call, no routing overhead.
        """
        logger.info(f"📨 [{platform}] User: {user_message[:100]}...")

        # Handle /secret commands directly
        if user_message.strip().startswith("/secret"):
            cmd_body = user_message.strip()[len("/secret"):].strip()
            return self.vault.handle_command(cmd_body)

        try:
            # Mask secrets before LLM sees the message
            masked_message = self.vault.mask(user_message)

            # Build system prompt with personality
            system_prompt = self.prompt_builder.build()

            # Get conversation history for context
            history = self.memory.get_short_term_history()
            messages = history + [{"role": "user", "content": masked_message}]

            # Single LLM call — direct to Ollama
            response = await self.llm.chat(messages, system=system_prompt)

            # Unmask secrets in response (for execution context)
            response = self.vault.unmask(response)

            if not response or not response.strip():
                response = "Hmm, aku butuh waktu sebentar untuk berpikir. Coba tanya lagi ya! 😊"

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            response = "⚠️ Maaf, ada masalah teknis. Coba lagi ya."

        logger.info(f"📤 [{platform}] Sovra: {response[:100]}...")

        # Post-process async (non-blocking — response already sent)
        asyncio.create_task(self._post_process(user_message, response, platform))

        return response

    async def _post_process(self, user_message: str, response: str, platform: str):
        """Background: save memory + log interaction. Non-blocking."""
        try:
            self.memory.add_to_short_term("user", user_message)
            self.memory.add_to_short_term("assistant", response)
            await self.memory.commit_to_long_term(user_message, response)
            self.collector.log_interaction(
                user_input=user_message,
                system_prompt="",
                llm_response=response,
                route="direct",
                metadata={"platform": platform},
            )
        except Exception as e:
            logger.warning(f"Post-process failed (non-critical): {e}")

    async def _get_rag_context(self, query: str) -> str:
        """Retrieve relevant context from RAG memory."""
        try:
            results = await self.rag.search(query, top_k=3)
            if results:
                return "\n\n".join([f"[Memory] {r['content']}" for r in results])
        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")
        return ""

    async def start(self):
        """Start all SOVRA subsystems."""
        logger.info("🚀 Starting SOVRA subsystems...")

        # Verify Ollama is available
        if not await self.llm.is_available():
            logger.error("❌ Ollama is not available! Start Ollama first.")
            raise ConnectionError("Cannot connect to Ollama")

        # Start scheduler
        self.scheduler.start()
        logger.info("✅ Proactive scheduler started")

        # Start autonomous execution loop in background
        asyncio.create_task(self.execution_loop.start())
        logger.info("✅ Autonomous execution loop started")

        logger.info("🎯 SOVRA is fully operational and autonomous!")
        logger.info(f"   Name: {self.personality.name}")
        logger.info(f"   Autonomy Level: {self.personality.autonomy.get('level', 'full')}")
        logger.info(f"   Memory: {self.rag.get_memory_count()} documents")
        logger.info(f"   Interactions: {self.collector.get_count()} collected")

    async def stop(self):
        """Gracefully stop all subsystems."""
        logger.info("⏹️ Stopping SOVRA...")
        await self.execution_loop.stop()
        self.scheduler.stop()
        await self.llm.close()
        await self.api_filter.close()
        logger.info("👋 SOVRA stopped. Goodbye.")

    def get_status(self) -> dict:
        """Get the overall status of SOVRA."""
        return {
            "name": self.personality.name,
            "autonomy_level": self.personality.autonomy.get("level", "full"),
            "memory": self.memory.get_memory_stats(),
            "router": self.router.get_stats(),
            "task_queue": self.goal_planner.get_queue_summary(),
            "interactions": self.collector.get_quality_stats(),
            "scheduler_jobs": self.scheduler.get_all_jobs(),
        }
