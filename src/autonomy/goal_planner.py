"""
SOVRA Autonomy - Goal Planner
Decomposes high-level goals into executable steps using chain-of-thought reasoning.
Maintains a persistent task queue that survives restarts.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from ..brain.llm_client import LLMClient
from ..brain.system_prompt import SystemPromptBuilder

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    BACKGROUND = "background"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class Task:
    """Represents a single executable task in the queue."""

    def __init__(
        self,
        goal: str,
        action: str = "",
        task_type: str = "think",
        command: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        parent_id: Optional[str] = None,
        depends_on: Optional[list[str]] = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.goal = goal
        self.action = action
        self.task_type = task_type  # shell, file, web, api, think
        self.command = command
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.parent_id = parent_id
        self.depends_on = depends_on or []
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.attempts: list[str] = []
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "action": self.action,
            "task_type": self.task_type,
            "command": self.command,
            "priority": self.priority.value,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        task = cls(
            goal=data["goal"],
            action=data.get("action", ""),
            task_type=data.get("task_type", "think"),
            command=data.get("command", ""),
            priority=TaskPriority(data.get("priority", "normal")),
            parent_id=data.get("parent_id"),
            depends_on=data.get("depends_on", []),
        )
        task.id = data["id"]
        task.status = TaskStatus(data.get("status", "pending"))
        task.result = data.get("result")
        task.error = data.get("error")
        task.attempts = data.get("attempts", [])
        task.created_at = data.get("created_at", datetime.now().isoformat())
        task.completed_at = data.get("completed_at")
        return task


class GoalPlanner:
    """Decomposes goals into executable tasks and manages the task queue."""

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_builder: SystemPromptBuilder,
        queue_path: Optional[str] = None,
    ):
        self.llm = llm_client
        self.prompt_builder = prompt_builder
        self.queue_path = Path(
            queue_path or os.getenv("AUTONOMY_TASK_QUEUE_PATH", "./data/task_queue.json")
        )
        self.tasks: list[Task] = []
        self._load_queue()

    def _load_queue(self):
        """Load persistent task queue from disk."""
        if self.queue_path.exists():
            try:
                with open(self.queue_path, "r") as f:
                    data = json.load(f)
                self.tasks = [Task.from_dict(t) for t in data]
                pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)
                logger.info(f"Loaded task queue: {len(self.tasks)} total, {pending} pending")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load task queue: {e}")
                self.tasks = []
        else:
            self.tasks = []

    def _save_queue(self):
        """Persist task queue to disk."""
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_path, "w") as f:
            json.dump([t.to_dict() for t in self.tasks], f, indent=2)

    async def plan(
        self,
        goal: str,
        context: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> list[Task]:
        """Decompose a high-level goal into executable tasks using the LLM."""
        logger.info(f"Planning goal: {goal}")

        prompt = self.prompt_builder.build_goal_planning_prompt(goal, context)
        system = self.prompt_builder.build()

        response = await self.llm.generate(prompt, system=system, temperature=0.3)

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            plan = json.loads(json_str)
            steps = plan.get("steps", [])
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse goal plan, creating single task: {response[:200]}")
            steps = [{"id": 1, "action": goal, "type": "think", "command": "", "depends_on": []}]

        # Create Task objects
        new_tasks = []
        id_mapping = {}
        for step in steps:
            task = Task(
                goal=goal,
                action=step.get("action", ""),
                task_type=step.get("type", "think"),
                command=step.get("command", ""),
                priority=priority,
                depends_on=[],
            )
            id_mapping[step.get("id", len(id_mapping) + 1)] = task.id
            new_tasks.append(task)

        # Resolve dependencies
        for i, step in enumerate(steps):
            deps = step.get("depends_on", [])
            new_tasks[i].depends_on = [id_mapping[d] for d in deps if d in id_mapping]

        self.tasks.extend(new_tasks)
        self._save_queue()

        logger.info(f"Created {len(new_tasks)} tasks for goal: {goal}")
        return new_tasks

    def add_task(self, task: Task):
        """Manually add a task to the queue."""
        self.tasks.append(task)
        self._save_queue()

    def get_next_task(self) -> Optional[Task]:
        """Get the next executable task based on priority and dependencies."""
        # Priority order
        priority_order = [
            TaskPriority.CRITICAL,
            TaskPriority.HIGH,
            TaskPriority.NORMAL,
            TaskPriority.BACKGROUND,
        ]

        for priority in priority_order:
            for task in self.tasks:
                if task.status != TaskStatus.PENDING:
                    continue
                if task.priority != priority:
                    continue
                # Check if all dependencies are completed
                deps_met = all(
                    any(t.id == dep and t.status == TaskStatus.COMPLETED for t in self.tasks)
                    for dep in task.depends_on
                )
                if deps_met:
                    return task

        return None

    def mark_completed(self, task_id: str, result: str = ""):
        """Mark a task as completed."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now().isoformat()
                break
        self._save_queue()

    def mark_failed(self, task_id: str, error: str, attempt: str = ""):
        """Mark a task as failed."""
        for task in self.tasks:
            if task.id == task_id:
                task.error = error
                task.attempts.append(attempt or error)
                max_retries = int(os.getenv("AUTONOMY_MAX_RETRIES", "3"))
                if len(task.attempts) >= max_retries:
                    task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.PENDING  # Will be retried
                break
        self._save_queue()

    def get_pending_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)

    def get_queue_summary(self) -> dict:
        """Get a summary of the task queue."""
        return {
            "total": len(self.tasks),
            "pending": sum(1 for t in self.tasks if t.status == TaskStatus.PENDING),
            "in_progress": sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS),
            "completed": sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self.tasks if t.status == TaskStatus.FAILED),
        }

    def clear_completed(self):
        """Remove completed tasks from the queue."""
        self.tasks = [t for t in self.tasks if t.status != TaskStatus.COMPLETED]
        self._save_queue()
