"""
SOVRA Autonomy - Proactive Scheduler
SOVRA doesn't just react — it initiates tasks on its own.
Handles cron-like scheduling and dynamic task creation.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..brain.personality import PersonalityEngine
from .goal_planner import GoalPlanner, Task, TaskPriority

logger = logging.getLogger(__name__)


class ProactiveScheduler:
    """
    Manages scheduled and proactive tasks.
    SOVRA can create its own schedules dynamically.
    """

    def __init__(
        self,
        goal_planner: GoalPlanner,
        personality: PersonalityEngine,
    ):
        self.planner = goal_planner
        self.personality = personality
        self.scheduler = AsyncIOScheduler()
        self.custom_jobs: list[dict] = []
        self._schedule_file = Path(
            os.getenv("SCHEDULER_JOBS_PATH", "./data/scheduled_jobs.json")
        )

    def start(self):
        """Start the scheduler with default proactive behaviors."""
        behaviors = self.personality.proactive_behaviors

        # Daily system health check
        if behaviors.get("daily_health_check", True):
            interval = int(os.getenv("SCHEDULER_HEALTH_CHECK_INTERVAL_HOURS", "24"))
            self.scheduler.add_job(
                self._health_check,
                IntervalTrigger(hours=interval),
                id="health_check",
                name="System Health Check",
                replace_existing=True,
            )
            logger.info(f"📅 Scheduled: System health check every {interval}h")

        # Memory consolidation
        if behaviors.get("auto_memory_consolidation", True):
            interval = int(os.getenv("SCHEDULER_MEMORY_CONSOLIDATION_HOURS", "168"))
            self.scheduler.add_job(
                self._memory_consolidation,
                IntervalTrigger(hours=interval),
                id="memory_consolidation",
                name="Memory Consolidation",
                replace_existing=True,
            )
            logger.info(f"📅 Scheduled: Memory consolidation every {interval}h")

        # Auto-evolution trigger
        if behaviors.get("auto_evolution_trigger", True):
            evolution_hours = int(os.getenv("EVOLUTION_SCHEDULE_HOURS", "168"))
            self.scheduler.add_job(
                self._check_evolution_ready,
                IntervalTrigger(hours=evolution_hours),
                id="evolution_check",
                name="Evolution Check",
                replace_existing=True,
            )
            logger.info(f"📅 Scheduled: Evolution check every {evolution_hours}h")

        # Disk space monitoring
        if behaviors.get("monitor_disk_space", True):
            self.scheduler.add_job(
                self._monitor_disk,
                IntervalTrigger(hours=6),
                id="disk_monitor",
                name="Disk Space Monitor",
                replace_existing=True,
            )
            logger.info("📅 Scheduled: Disk space monitor every 6h")

        # Load custom jobs from disk
        self._load_custom_jobs()

        self.scheduler.start()
        logger.info("🚀 Proactive scheduler started.")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("⏹️ Proactive scheduler stopped.")

    async def add_dynamic_job(
        self,
        name: str,
        goal: str,
        schedule: str,
        priority: TaskPriority = TaskPriority.NORMAL,
    ):
        """
        SOVRA can create its own scheduled tasks dynamically.
        schedule format: cron expression (e.g., "0 3 * * *" for daily 3am)
        """
        job_id = f"dynamic_{name.lower().replace(' ', '_')}"

        self.scheduler.add_job(
            self._execute_scheduled_goal,
            CronTrigger.from_crontab(schedule),
            id=job_id,
            name=name,
            replace_existing=True,
            args=[goal, priority],
        )

        job_entry = {
            "id": job_id,
            "name": name,
            "goal": goal,
            "schedule": schedule,
            "priority": priority.value,
            "created_at": datetime.now().isoformat(),
        }
        self.custom_jobs.append(job_entry)
        self._save_custom_jobs()

        logger.info(f"📅 Dynamic job added: {name} ({schedule})")

    async def remove_dynamic_job(self, job_id: str):
        """Remove a dynamically created job."""
        try:
            self.scheduler.remove_job(job_id)
            self.custom_jobs = [j for j in self.custom_jobs if j["id"] != job_id]
            self._save_custom_jobs()
            logger.info(f"🗑️ Dynamic job removed: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")

    # --- Scheduled task implementations ---

    async def _health_check(self):
        """Proactive system health check."""
        logger.info("🏥 Running proactive health check...")
        task = Task(
            goal="System health check",
            action="Check system health: disk usage, memory usage, CPU load, service status. Report any issues.",
            task_type="shell",
            command="echo '=== DISK ===' && df -h / && echo '=== MEM ===' && free -h && echo '=== CPU ===' && uptime && echo '=== SERVICES ===' && systemctl is-active ollama",
            priority=TaskPriority.BACKGROUND,
        )
        self.planner.add_task(task)

    async def _memory_consolidation(self):
        """Trigger memory consolidation."""
        logger.info("🧠 Scheduling memory consolidation...")
        task = Task(
            goal="Memory consolidation",
            action="Consolidate and summarize old memories to free up space and improve retrieval quality.",
            task_type="think",
            priority=TaskPriority.BACKGROUND,
        )
        self.planner.add_task(task)

    async def _check_evolution_ready(self):
        """Check if enough training data has been collected for evolution."""
        logger.info("🧬 Checking if evolution cycle should be triggered...")
        min_samples = int(os.getenv("EVOLUTION_MIN_SAMPLES", "200"))
        task = Task(
            goal="Check evolution readiness",
            action=f"Check if there are at least {min_samples} quality interactions for LoRA training. If yes, trigger evolution cycle.",
            task_type="shell",
            command=f"wc -l data/training/interactions.jsonl 2>/dev/null || echo '0 lines'",
            priority=TaskPriority.BACKGROUND,
        )
        self.planner.add_task(task)

    async def _monitor_disk(self):
        """Monitor disk space proactively."""
        task = Task(
            goal="Disk space check",
            action="Check disk usage. If above 90%, clean up old logs and temporary files.",
            task_type="shell",
            command="df -h / | tail -1 | awk '{print $5}'",
            priority=TaskPriority.HIGH,
        )
        self.planner.add_task(task)

    async def _execute_scheduled_goal(self, goal: str, priority: TaskPriority):
        """Execute a scheduled goal by adding it to the planner."""
        logger.info(f"⏰ Triggered scheduled goal: {goal}")
        await self.planner.plan(goal, priority=priority)

    # --- Persistence ---

    def _save_custom_jobs(self):
        """Save custom jobs to disk."""
        self._schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._schedule_file, "w") as f:
            json.dump(self.custom_jobs, f, indent=2)

    def _load_custom_jobs(self):
        """Load and restore custom jobs from disk."""
        if self._schedule_file.exists():
            try:
                with open(self._schedule_file, "r") as f:
                    self.custom_jobs = json.load(f)
                for job in self.custom_jobs:
                    self.scheduler.add_job(
                        self._execute_scheduled_goal,
                        CronTrigger.from_crontab(job["schedule"]),
                        id=job["id"],
                        name=job["name"],
                        replace_existing=True,
                        args=[job["goal"], TaskPriority(job["priority"])],
                    )
                logger.info(f"Restored {len(self.custom_jobs)} custom scheduled jobs.")
            except Exception as e:
                logger.warning(f"Failed to load custom jobs: {e}")

    def get_all_jobs(self) -> list[dict]:
        """List all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })
        return jobs
