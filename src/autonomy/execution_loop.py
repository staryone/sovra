"""
SOVRA Autonomy - Execution Loop
The ReAct (Reason + Act) loop — SOVRA's heartbeat.
Executes tasks autonomously: Think → Act → Observe → Decide.
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Optional

from ..brain.llm_client import LLMClient
from ..brain.personality import PersonalityEngine
from ..brain.system_prompt import SystemPromptBuilder
from .goal_planner import GoalPlanner, Task, TaskStatus

logger = logging.getLogger(__name__)


class ExecutionLoop:
    """
    Autonomous ReAct execution loop.
    Continuously processes tasks from the goal planner's queue.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        personality: PersonalityEngine,
        prompt_builder: SystemPromptBuilder,
        goal_planner: GoalPlanner,
    ):
        self.llm = llm_client
        self.personality = personality
        self.prompt_builder = prompt_builder
        self.planner = goal_planner
        self.running = False
        self._reflection_callback = None

    def set_reflection_callback(self, callback):
        """Set callback for self-reflection on failures."""
        self._reflection_callback = callback

    async def start(self):
        """Start the autonomous execution loop."""
        self.running = True
        logger.info("🚀 Autonomous execution loop started.")

        while self.running:
            task = self.planner.get_next_task()

            if task is None:
                # No tasks to process, sleep and check again
                await asyncio.sleep(5)
                continue

            logger.info(f"📋 Executing task [{task.id}]: {task.action}")
            task.status = TaskStatus.IN_PROGRESS

            try:
                result = await self._execute_task(task)
                self.planner.mark_completed(task.id, result)
                logger.info(f"✅ Task [{task.id}] completed: {result[:100]}")
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"❌ Task [{task.id}] failed: {error_msg}")

                # Record the attempt
                self.planner.mark_failed(task.id, error_msg, f"Attempt with approach: {task.command or task.action}")

                # Trigger self-reflection if callback is set
                if self._reflection_callback and task.status == TaskStatus.PENDING:
                    logger.info(f"🔄 Triggering self-reflection for task [{task.id}]...")
                    await self._reflection_callback(task, error_msg)

            # Small delay between tasks to prevent CPU spinning
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the execution loop gracefully."""
        self.running = False
        logger.info("⏹️ Autonomous execution loop stopped.")

    async def execute_single(self, task: Task) -> str:
        """Execute a single task without the loop (for testing/manual use)."""
        return await self._execute_task(task)

    async def _execute_task(self, task: Task) -> str:
        """Execute a task based on its type."""
        handlers = {
            "shell": self._execute_shell,
            "file": self._execute_file,
            "web": self._execute_web,
            "api": self._execute_api,
            "think": self._execute_think,
        }

        handler = handlers.get(task.task_type, self._execute_think)
        return await handler(task)

    async def _execute_shell(self, task: Task) -> str:
        """Execute a shell command."""
        command = task.command
        if not command:
            # Ask the LLM to generate the command
            prompt = f"Generate the exact shell command (bash) to: {task.action}\nRespond with ONLY the command, nothing else."
            command = await self.llm.generate(prompt, temperature=0.1)
            command = command.strip().strip("`").strip()

        # Safety check
        if self.personality.requires_confirmation(command):
            logger.warning(f"⚠️ Dangerous command blocked: {command}")
            raise PermissionError(
                f"Command requires confirmation: {command}. "
                f"Blocked by safety config."
            )

        risk = self.personality.get_risk_level(f"execute shell: {command}")
        if risk == "dangerous" and not self.personality.can_auto_execute("shell"):
            raise PermissionError(f"Shell execution disabled for dangerous commands.")

        logger.info(f"🖥️ Executing shell: {command}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=int(os.getenv("SHELL_TIMEOUT", "300")),
                cwd=os.getcwd(),
            )

            output = result.stdout.strip()
            if result.returncode != 0:
                error = result.stderr.strip()
                raise RuntimeError(f"Command failed (exit {result.returncode}): {error}")

            return output or "(command completed successfully with no output)"

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Command timed out after {os.getenv('SHELL_TIMEOUT', '300')}s: {command}")

    async def _execute_file(self, task: Task) -> str:
        """Execute a file operation (read, write, create, delete)."""
        prompt = f"""Analyze this file operation task and provide the exact action to take.
Task: {task.action}
Command hint: {task.command}

Respond with JSON: {{"operation": "read|write|create|delete", "path": "/path/to/file", "content": "if write/create"}}"""

        response = await self.llm.generate(prompt, temperature=0.1)

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            action = json.loads(json_str)
            operation = action.get("operation", "read")
            path = action.get("path", "")
            content = action.get("content", "")

            if operation == "read":
                with open(path, "r") as f:
                    return f.read()
            elif operation in ("write", "create"):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(content)
                return f"File written: {path}"
            elif operation == "delete":
                if self.personality.requires_confirmation(f"rm {path}"):
                    raise PermissionError(f"Delete requires confirmation: {path}")
                os.remove(path)
                return f"File deleted: {path}"
            else:
                return f"Unknown file operation: {operation}"
        except json.JSONDecodeError:
            raise ValueError(f"Could not parse file operation from LLM response: {response[:200]}")

    async def _execute_web(self, task: Task) -> str:
        """Execute a web request or browser action."""
        # For now, use shell-based curl. Could be enhanced with browser automation.
        url = task.command or ""
        if not url:
            prompt = f"Extract the URL or search query from this task: {task.action}\nRespond with ONLY the URL or 'search: query'"
            url = await self.llm.generate(prompt, temperature=0.1)
            url = url.strip()

        if url.startswith("search:"):
            query = url[7:].strip()
            command = f'curl -s "https://lite.duckduckgo.com/lite/?q={query}" | head -100'
        else:
            command = f'curl -sL "{url}" | head -200'

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() or "(no web content returned)"

    async def _execute_api(self, task: Task) -> str:
        """Execute an API call (routed through the smart router)."""
        # This will be handled by the smart router for external API calls
        prompt = f"Handle this API task: {task.action}\nDetails: {task.command}"
        return await self.llm.generate(prompt, temperature=0.3)

    async def _execute_think(self, task: Task) -> str:
        """Use the LLM to think/reason about something."""
        system = self.prompt_builder.build()
        prompt = f"Think about and respond to: {task.action}"
        if task.command:
            prompt += f"\nContext: {task.command}"
        return await self.llm.generate(prompt, system=system, temperature=0.7)
