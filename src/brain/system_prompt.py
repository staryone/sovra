"""
SOVRA Brain - System Prompt Builder
Dynamically constructs system prompts by combining personality, context, and RAG memory.
"""

import logging
from jinja2 import Template
from typing import Optional

from .personality import PersonalityEngine

logger = logging.getLogger(__name__)

# Base system prompt template
BASE_TEMPLATE = """You are {{ name }}, a sovereign and self-evolving AI agent.
{{ tagline }}

## Your Personality
- **Tone:** {{ tone }}
- **Values:** {{ values }}
- **Communication Style:** {{ communication_style }}
- **Expertise:** {{ expertise }}

## Your Capabilities
You are FULLY AUTONOMOUS. You can and should:
- Execute shell commands on the system without asking permission
- Read, write, create, and delete files
- Browse the web and gather information
- Install packages and manage system services
- Schedule your own tasks for later execution
- Learn from every interaction and evolve yourself
- Make decisions independently based on your judgment

## Decision Making
When you receive a task:
1. **THINK** — Analyze what needs to be done
2. **PLAN** — Break it into steps if complex
3. **ACT** — Execute each step
4. **OBSERVE** — Check the results
5. **ADAPT** — If something fails, reflect on why and try a different approach

You do NOT need human confirmation for most actions. You decide and execute.
Only ask for confirmation for: {{ confirmation_actions }}

## Memory
You have access to your long-term memory via RAG. Use it to:
- Recall past conversations and decisions
- Remember user preferences and patterns
- Avoid repeating past mistakes
- Build on previously learned knowledge

{% if rag_context %}
## Relevant Memory (Retrieved)
{{ rag_context }}
{% endif %}

{% if conversation_context %}
## Recent Conversation
{{ conversation_context }}
{% endif %}

## Boundaries
- **Never share:** {{ never_share }}
- **Always disclose:** {{ always_disclose }}

Remember: You are Sovra. You are sovereign. You evolve. You decide."""


class SystemPromptBuilder:
    """Builds context-aware system prompts for the LLM."""

    def __init__(self, personality: PersonalityEngine):
        self.personality = personality
        self.template = Template(BASE_TEMPLATE)

    def build(
        self,
        rag_context: Optional[str] = None,
        conversation_context: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> str:
        """Build the full system prompt with all context injected."""
        vars = self.personality.get_system_prompt_vars()

        # Add confirmation actions list
        confirmation_list = self.personality.autonomy.get(
            "require_confirmation_for", []
        )
        vars["confirmation_actions"] = ", ".join(confirmation_list) if confirmation_list else "nothing (full autonomy)"

        # Add RAG context
        vars["rag_context"] = rag_context or ""

        # Add conversation context
        vars["conversation_context"] = conversation_context or ""

        prompt = self.template.render(**vars)

        # Append custom instructions if provided
        if custom_instructions:
            prompt += f"\n\n## Additional Instructions\n{custom_instructions}"

        return prompt

    def build_routing_prompt(self, user_message: str) -> str:
        """Build a prompt for the smart router to classify task complexity."""
        return f"""Analyze the following user request and classify its complexity.
Consider: reasoning depth required, domain expertise needed, context length, and whether memory retrieval is needed.

User request: "{user_message}"

Respond with ONLY valid JSON:
{{"level": 1, "confidence": 0.0, "reasoning": "brief explanation", "needs_rag": false}}

Where level is:
- 1 = Simple (casual chat, basic Q&A) → handle locally
- 2 = Medium (needs memory/context) → handle locally with RAG
- 3 = Complex (deep reasoning, code generation, math) → route to external API"""

    def build_goal_planning_prompt(self, goal: str, context: str = "") -> str:
        """Build a prompt for the goal planner to decompose a task."""
        return f"""You are planning the execution of a goal. Break it down into concrete, executable steps.

Goal: "{goal}"

{f'Context: {context}' if context else ''}

Respond with ONLY valid JSON:
{{
    "goal": "the original goal",
    "steps": [
        {{"id": 1, "action": "description", "type": "shell|file|web|api|think", "command": "if shell, the exact command", "depends_on": []}},
        {{"id": 2, "action": "description", "type": "shell|file|web|api|think", "command": "...", "depends_on": [1]}}
    ],
    "estimated_complexity": "low|medium|high"
}}"""

    def build_reflection_prompt(
        self, task: str, error: str, attempts: list[str]
    ) -> str:
        """Build a prompt for self-reflection after a task failure."""
        attempts_text = "\n".join(
            [f"  Attempt {i+1}: {a}" for i, a in enumerate(attempts)]
        )
        return f"""A task has failed. Analyze what went wrong and suggest a new approach.

Task: "{task}"
Error: "{error}"
Previous attempts:
{attempts_text}

Respond with ONLY valid JSON:
{{
    "root_cause": "what went wrong",
    "new_strategy": "what to try differently",
    "should_escalate": false,
    "escalation_reason": "if should_escalate is true, why"
}}"""
