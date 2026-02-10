"""
SOVRA Brain - LLM Client
Interfaces with Ollama for local LLM inference.
"""

import httpx
import json
import logging
import os
from typing import AsyncIterator, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """Client for communicating with Ollama's local LLM API."""

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        context_length: Optional[int] = None,
    ):
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = model or os.getenv("SOVRA_MODEL", "sovra-brain")
        self.context_length = context_length or int(
            os.getenv("SOVRA_CONTEXT_LENGTH", "16384")
        )
        # Increase timeout for CPU inference (default 10m)
        self._timeout = float(os.getenv("OLLAMA_TIMEOUT", "600"))
        self._client = httpx.AsyncClient(base_url=self.host, timeout=self._timeout)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str:
        """Generate a completion from the local LLM."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": self.context_length,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }
        if system:
            payload["system"] = system

        try:
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except httpx.ReadTimeout:
            logger.warning(f"LLM response timed out after {self._timeout}s. Model too slow.")
            return "⏱️ [Timeout] My thought process took too long. Please try again."
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.host}. Is it running?")
            raise

    async def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Chat completion with message history."""
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": chat_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": self.context_length,
            },
        }

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except httpx.ReadTimeout:
            logger.warning(f"LLM chat timed out after {self._timeout}s.")
            return "⏱️ [Timeout] I took too long to respond."
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM chat error: {e.response.status_code}")
            raise

    async def generate_stream(
        self, prompt: str, system: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"num_ctx": self.context_length},
        }
        if system:
            payload["system"] = system

        async with self._client.stream(
            "POST", "/api/generate", json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break

    async def embeddings(self, text: str, model: Optional[str] = None) -> list[float]:
        """Generate embeddings using local embedding model."""
        embed_model = model or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        payload = {"model": embed_model, "prompt": text}

        response = await self._client.post("/api/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])

    async def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models in Ollama."""
        response = await self._client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
