"""
SOVRA Memory - Memory Manager
Manages short-term and long-term memory lifecycle.
Handles conversation buffers, consolidation, and importance scoring.
"""

import json
import logging
import os
from collections import deque
from datetime import datetime
from typing import Optional

from ..brain.llm_client import LLMClient
from .rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages SOVRA's memory system:
    - Short-term: sliding window conversation buffer
    - Long-term: ChromaDB via RAG pipeline
    - Consolidation: summarize and compress old memories
    """

    def __init__(
        self,
        llm_client: LLMClient,
        rag: RAGPipeline,
        short_term_size: Optional[int] = None,
    ):
        self.llm = llm_client
        self.rag = rag
        self.short_term_size = short_term_size or int(
            os.getenv("MEMORY_SHORT_TERM_SIZE", "20")
        )
        self.short_term: deque[dict] = deque(maxlen=self.short_term_size)

    def add_to_short_term(self, role: str, content: str):
        """Add a message to short-term memory."""
        self.short_term.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_short_term_history(self) -> list[dict]:
        """Get the current conversation history."""
        return [{"role": m["role"], "content": m["content"]} for m in self.short_term]

    def get_short_term_context(self) -> str:
        """Get short-term memory as a formatted string."""
        return "\n".join(
            [f"{m['role']}: {m['content']}" for m in self.short_term]
        )

    async def commit_to_long_term(self, user_msg: str, assistant_msg: str):
        """Commit a conversation exchange to long-term memory."""
        await self.rag.store_conversation(user_msg, assistant_msg)
        logger.debug("Committed conversation to long-term memory.")

    async def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """Recall relevant memories for a query."""
        return await self.rag.search(query, top_k=top_k)

    async def consolidate(self):
        """
        Consolidate old memories: summarize and compress.
        This reduces storage and improves retrieval quality.
        """
        logger.info("🧠 Starting memory consolidation...")

        count = self.rag.get_memory_count()
        if count < 100:
            logger.info("Not enough memories to consolidate (< 100). Skipping.")
            return

        # Get oldest memories
        # Note: ChromaDB doesn't support sorting by timestamp natively,
        # so we retrieve a batch and process
        results = await self.rag.search(
            "summarize all past interactions", top_k=50
        )

        if not results:
            return

        # Group memories and create summaries
        batch_size = 10
        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            content = "\n---\n".join([r["content"] for r in batch])

            # Use LLM to summarize
            prompt = f"""Summarize the following conversation memories into a concise paragraph.
Preserve key facts, decisions, and preferences. Remove redundancy.

Memories:
{content}

Provide a concise summary:"""

            summary = await self.llm.generate(prompt, temperature=0.3)

            # Store summary and delete originals
            await self.rag.store(
                summary,
                metadata={"type": "consolidated_memory", "original_count": len(batch)},
            )

            for r in batch:
                if r.get("id"):
                    await self.rag.delete(r["id"])

        logger.info(f"🧠 Consolidated {len(results)} memories into summaries.")

    def get_memory_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "short_term_count": len(self.short_term),
            "short_term_max": self.short_term_size,
            "long_term_count": self.rag.get_memory_count(),
        }

    def clear_short_term(self):
        """Clear short-term memory."""
        self.short_term.clear()
        logger.info("Short-term memory cleared.")
