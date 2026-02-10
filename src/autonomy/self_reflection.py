"""
SOVRA Autonomy - Self-Reflection Engine
When a task fails, SOVRA analyzes why and adapts its strategy.
Stores lessons learned in RAG memory to avoid repeating mistakes.
"""

import json
import logging
from typing import Optional

from ..brain.llm_client import LLMClient
from ..brain.system_prompt import SystemPromptBuilder
from .goal_planner import GoalPlanner, Task, TaskPriority

logger = logging.getLogger(__name__)


class SelfReflection:
    """
    Analyzes task failures and generates new strategies.
    Learns from mistakes by storing reflections in memory.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_builder: SystemPromptBuilder,
        goal_planner: GoalPlanner,
        memory_store=None,
    ):
        self.llm = llm_client
        self.prompt_builder = prompt_builder
        self.planner = goal_planner
        self.memory = memory_store  # RAG memory for storing lessons
        self.reflection_history: list[dict] = []

    async def reflect(self, task: Task, error: str) -> dict:
        """
        Reflect on a failed task and generate a new strategy.
        Returns the reflection result.
        """
        logger.info(f"🪞 Reflecting on failure: task [{task.id}] - {task.action}")

        prompt = self.prompt_builder.build_reflection_prompt(
            task=task.action,
            error=error,
            attempts=task.attempts,
        )

        response = await self.llm.generate(prompt, temperature=0.3)

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            reflection = json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            reflection = {
                "root_cause": "Unable to determine root cause",
                "new_strategy": response.strip()[:500],
                "should_escalate": False,
                "escalation_reason": "",
            }

        # Log the reflection
        reflection_entry = {
            "task_id": task.id,
            "task_action": task.action,
            "error": error,
            "attempt_number": len(task.attempts),
            "root_cause": reflection.get("root_cause", ""),
            "new_strategy": reflection.get("new_strategy", ""),
            "should_escalate": reflection.get("should_escalate", False),
        }
        self.reflection_history.append(reflection_entry)

        logger.info(f"🔍 Root cause: {reflection.get('root_cause', 'unknown')}")
        logger.info(f"💡 New strategy: {reflection.get('new_strategy', 'none')}")

        # If should escalate, mark the task differently
        if reflection.get("should_escalate", False):
            logger.info(f"⬆️ Escalating task [{task.id}] to external API")
            task.task_type = "api"
            task.command = f"Escalated: {reflection.get('escalation_reason', '')}"
        else:
            # Update the task with the new strategy
            new_strategy = reflection.get("new_strategy", "")
            if new_strategy:
                task.command = new_strategy
                logger.info(f"🔄 Updated task [{task.id}] with new strategy")

        # Store lesson in RAG memory if available
        if self.memory:
            lesson = (
                f"LESSON LEARNED: When trying to '{task.action}', "
                f"it failed because: {reflection.get('root_cause', 'unknown')}. "
                f"Better approach: {reflection.get('new_strategy', 'try differently')}."
            )
            try:
                await self.memory.store(lesson, metadata={"type": "lesson", "task": task.action})
                logger.info("📝 Lesson stored in memory for future reference.")
            except Exception as e:
                logger.warning(f"Failed to store lesson in memory: {e}")

        return reflection

    async def recall_similar_failures(self, task_description: str) -> list[str]:
        """Check memory for similar past failures and their solutions."""
        if not self.memory:
            return []

        try:
            results = await self.memory.search(
                f"lesson learned about: {task_description}",
                top_k=3,
                filter_metadata={"type": "lesson"},
            )
            return [r["content"] for r in results]
        except Exception:
            return []

    def get_reflection_summary(self) -> dict:
        """Get a summary of all reflections."""
        return {
            "total_reflections": len(self.reflection_history),
            "escalations": sum(
                1 for r in self.reflection_history if r.get("should_escalate", False)
            ),
            "recent": self.reflection_history[-5:] if self.reflection_history else [],
        }
