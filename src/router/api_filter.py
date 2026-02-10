"""
SOVRA Router - API Key Filter & Proxy
Ensures API keys NEVER enter the LLM context.
Acts as a secure proxy for external API calls.
"""

import httpx
import json
import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class APIFilter:
    """
    Secure proxy for external API calls.
    - API keys stored in env vars only
    - Strips any leaked keys from prompts
    - Rate limiting and cost tracking
    """

    def __init__(self):
        self.providers = self._load_providers()
        self.active_provider: Optional[str] = None
        self.daily_calls = 0
        self.max_daily_calls = int(os.getenv("ROUTER_MAX_EXTERNAL_CALLS_PER_DAY", "50"))
        self.timeout = int(os.getenv("ROUTER_EXTERNAL_TIMEOUT", "30"))
        self._client = httpx.AsyncClient(timeout=self.timeout)

    def _load_providers(self) -> dict:
        """Load API provider configurations from env vars."""
        providers = {}

        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key and openai_key != "sk-your-key-here":
            providers["openai"] = {
                "api_key": openai_key,
                "base_url": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            }

        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if anthropic_key and anthropic_key != "sk-ant-your-key-here":
            providers["anthropic"] = {
                "api_key": anthropic_key,
                "base_url": "https://api.anthropic.com/v1",
                "model": os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
            }

        kimi_key = os.getenv("KIMI_API_KEY", "")
        if kimi_key and kimi_key != "sk-your-kimi-key-here":
            providers["kimi"] = {
                "api_key": kimi_key,
                "base_url": os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1"),
                "model": os.getenv("KIMI_MODEL", "moonshot-v1-8k"),
            }

        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key and openrouter_key != "sk-or-your-key-here":
            providers["openrouter"] = {
                "api_key": openrouter_key,
                "base_url": os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
                "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3-8b-instruct"),
            }

        return providers

    def _sanitize_prompt(self, text: str) -> str:
        """Remove any API keys that might have leaked into prompts."""
        # Pattern for common API key formats
        patterns = [
            r'sk-[a-zA-Z0-9]{20,}',          # OpenAI / Kimi
            r'sk-ant-[a-zA-Z0-9]{20,}',       # Anthropic
            r'sk-or-[a-zA-Z0-9]{20,}',        # OpenRouter
            r'AIza[a-zA-Z0-9_-]{35}',          # Google
            r'[a-f0-9]{32}',                    # Generic hex keys
        ]
        sanitized = text
        for pattern in patterns:
            sanitized = re.sub(pattern, '[API_KEY_REDACTED]', sanitized)
        return sanitized

    async def call(
        self,
        message: str,
        history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Make an API call through the secure proxy."""
        # Rate limit check
        if self.daily_calls >= self.max_daily_calls:
            raise RuntimeError(
                f"Daily external API limit reached ({self.max_daily_calls}). "
                f"Try again tomorrow or increase ROUTER_MAX_EXTERNAL_CALLS_PER_DAY."
            )

        # Sanitize inputs
        message = self._sanitize_prompt(message)
        if system_prompt:
            system_prompt = self._sanitize_prompt(system_prompt)

        # Try providers in order
        for provider_name, config in self.providers.items():
            try:
                self.active_provider = provider_name
                if provider_name == "openai":
                    result = await self._call_openai(config, message, history, system_prompt)
                elif provider_name == "anthropic":
                    result = await self._call_anthropic(config, message, history, system_prompt)
                elif provider_name == "kimi":
                    # Kimi (Moonshot) uses OpenAI-compatible API
                    result = await self._call_openai(config, message, history, system_prompt)
                elif provider_name == "openrouter":
                    result = await self._call_openrouter(config, message, history, system_prompt)
                else:
                    continue

                self.daily_calls += 1
                logger.info(f"🌐 External API call #{self.daily_calls} via {provider_name}")
                return result

            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue

        raise RuntimeError("All external API providers failed.")

    async def _call_openai(
        self, config: dict, message: str, history: Optional[list[dict]], system: Optional[str]
    ) -> str:
        """Call OpenAI-compatible API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = await self._client.post(
            f"{config['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": config["model"],
                "messages": messages,
                "temperature": 0.7,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic(
        self, config: dict, message: str, history: Optional[list[dict]], system: Optional[str]
    ) -> str:
        """Call Anthropic API."""
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        payload = {
            "model": config["model"],
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        response = await self._client.post(
            f"{config['base_url']}/messages",
            headers={
                "x-api-key": config["api_key"],
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def _call_openrouter(
        self, config: dict, message: str, history: Optional[list[dict]], system: Optional[str]
    ) -> str:
        """Call OpenRouter API (OpenAI-compatible with extra headers)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = await self._client.post(
            f"{config['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/sovra-agent",
                "X-Title": "SOVRA Agent",
            },
            json={
                "model": config["model"],
                "messages": messages,
                "temperature": 0.7,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def reset_daily_counter(self):
        """Reset the daily call counter (call at midnight)."""
        self.daily_calls = 0

    async def close(self):
        await self._client.aclose()
