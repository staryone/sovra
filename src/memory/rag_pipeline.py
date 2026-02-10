"""
SOVRA Memory - RAG Pipeline
Ingestion, embedding, storage, and retrieval of knowledge using ChromaDB.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings

from ..brain.llm_client import LLMClient

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    RAG (Retrieval-Augmented Generation) pipeline.
    Stores and retrieves knowledge from ChromaDB using local embeddings.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        persist_path: Optional[str] = None,
        collection_name: str = "sovra_memory",
    ):
        self.llm = llm_client
        self.persist_path = persist_path or os.getenv("CHROMADB_PATH", "./data/chromadb")
        self.top_k = int(os.getenv("RAG_TOP_K", "5"))

        # Initialize ChromaDB client with persistence
        Path(self.persist_path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_path)

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "SOVRA long-term memory"},
        )

        logger.info(
            f"RAG initialized: {self.collection.count()} documents in memory, "
            f"persist_path={self.persist_path}"
        )

    async def store(
        self,
        content: str,
        metadata: Optional[dict] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """Store a piece of knowledge in ChromaDB."""
        doc_id = doc_id or str(uuid4())[:12]

        # Generate embedding using local model
        embedding = await self.llm.embeddings(content)

        meta = {
            "timestamp": datetime.now().isoformat(),
            "source": "conversation",
            **(metadata or {}),
        }

        self.collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[meta],
            ids=[doc_id],
        )

        logger.debug(f"Stored document [{doc_id}]: {content[:80]}...")
        return doc_id

    async def store_batch(
        self, documents: list[str], metadatas: Optional[list[dict]] = None
    ) -> list[str]:
        """Store multiple documents at once."""
        ids = [str(uuid4())[:12] for _ in documents]
        embeddings = [await self.llm.embeddings(doc) for doc in documents]

        if not metadatas:
            metadatas = [{"timestamp": datetime.now().isoformat()} for _ in documents]

        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Stored {len(documents)} documents in batch.")
        return ids

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """Search for relevant documents using semantic similarity."""
        k = top_k or self.top_k

        # Generate query embedding
        query_embedding = await self.llm.embeddings(query)

        where_filter = filter_metadata if filter_metadata else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter,
        )

        documents = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                documents.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "id": results["ids"][0][i] if results["ids"] else "",
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                })

        logger.debug(f"RAG search for '{query[:50]}...' returned {len(documents)} results")
        return documents

    async def store_conversation(
        self, user_message: str, assistant_response: str, context: str = ""
    ):
        """Store a conversation exchange for future retrieval."""
        content = f"User: {user_message}\nAssistant: {assistant_response}"
        if context:
            content = f"Context: {context}\n{content}"

        await self.store(
            content,
            metadata={
                "type": "conversation",
                "source": "chat",
            },
        )

    def get_memory_count(self) -> int:
        """Get the total number of stored memories."""
        return self.collection.count()

    async def delete(self, doc_id: str):
        """Delete a specific document from memory."""
        self.collection.delete(ids=[doc_id])
        logger.debug(f"Deleted document [{doc_id}]")

    async def clear_all(self):
        """Clear all memories. Use with caution!"""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name="sovra_memory",
            metadata={"description": "SOVRA long-term memory"},
        )
        logger.warning("All memories cleared!")
