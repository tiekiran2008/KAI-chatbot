import asyncio
import logging
import uuid
from typing import List, Dict, Optional

from langsmith import traceable
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.memory import Memory, MemoryType

logger = logging.getLogger(__name__)

# Maximum memories to retrieve per user per type
MAX_SEMANTIC_MEMORIES = 10
MAX_EPISODIC_MEMORIES = 3


class MemoryService:
    """
    Modular Agent Memory Service.

    Manages three layers of memory:
    - Short-term:  Handled natively by LangGraph state (conversation messages in graph run).
    - Semantic:    Long-term facts/preferences stored in Supabase (e.g. "User prefers Python").
    - Episodic:    High-level summaries of completed conversations stored in Supabase.

    Extraction is always done as a background task to guarantee zero latency on streaming responses.
    """

    # ------------------------------------------------------------------
    # Retrieve memories
    # ------------------------------------------------------------------
    @traceable(run_type="retriever")
    async def get_memories(self, user_id: uuid.UUID) -> str:
        """
        Retrieves the user's semantic and episodic memories from Supabase.
        Returns a formatted string to inject into the system prompt, or empty string if none found.
        """
        if not settings.MEMORY_ENABLED:
            return ""

        try:
            async with AsyncSessionLocal() as db:
                # Fetch semantic memories (most recent first)
                semantic_result = await db.execute(
                    select(Memory)
                    .where(Memory.user_id == user_id)
                    .where(Memory.memory_type == MemoryType.semantic)
                    .order_by(Memory.updated_at.desc())
                    .limit(MAX_SEMANTIC_MEMORIES)
                )
                semantic_memories = semantic_result.scalars().all()

                # Fetch episodic memories (most recent first)
                episodic_result = await db.execute(
                    select(Memory)
                    .where(Memory.user_id == user_id)
                    .where(Memory.memory_type == MemoryType.episodic)
                    .order_by(Memory.updated_at.desc())
                    .limit(MAX_EPISODIC_MEMORIES)
                )
                episodic_memories = episodic_result.scalars().all()

            if not semantic_memories and not episodic_memories:
                logger.info(f"[Memory] No memories found for user {user_id}")
                return ""

            parts = []
            if semantic_memories:
                facts = "\n".join(f"- {m.content}" for m in semantic_memories)
                parts.append(f"=== KNOWN FACTS ABOUT THIS USER ===\n{facts}")

            if episodic_memories:
                episodes = "\n".join(f"- {m.content}" for m in episodic_memories)
                parts.append(f"=== RECENT CONVERSATION SUMMARIES ===\n{episodes}")

            memory_context = "\n\n".join(parts)
            logger.info(f"[Memory] Retrieved {len(semantic_memories)} semantic + {len(episodic_memories)} episodic memories for user {user_id}")
            return memory_context

        except Exception as e:
            logger.error(f"[Memory] Failed to retrieve memories for user {user_id}: {e}")
            return ""

    # ------------------------------------------------------------------
    # Store a single memory
    # ------------------------------------------------------------------
    async def _store_memory(self, user_id: uuid.UUID, memory_type: MemoryType, content: str) -> None:
        """Persists a single memory to Supabase."""
        try:
            async with AsyncSessionLocal() as db:
                new_memory = Memory(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content.strip()
                )
                db.add(new_memory)
                await db.commit()
                logger.info(f"[Memory] Stored {memory_type.value} memory for user {user_id}: '{content[:80]}...'")
        except Exception as e:
            logger.error(f"[Memory] Failed to store {memory_type.value} memory for user {user_id}: {e}")

    # ------------------------------------------------------------------
    # Analyze conversation and extract memories (background task)
    # ------------------------------------------------------------------
    @traceable(run_type="tool")
    async def analyze_and_store(
        self,
        user_id: uuid.UUID,
        user_message: str,
        assistant_response: str,
        history: List[Dict[str, str]]
    ) -> None:
        """
        Uses Gemini to analyze the exchange and extract useful memories.
        Called as a background task so it never blocks the streaming response.
        Skips trivial conversations (greetings, single-word answers, etc.).
        """
        if not settings.MEMORY_ENABLED:
            return

        try:
            # Lazy import to avoid circular imports
            from app.services.gemini import gemini_service

            # 1. Extract semantic facts/preferences from the user message
            semantic_prompt = (
                f"Analyze the following user message and assistant reply. "
                f"If the user revealed a personal fact, preference, goal, or important detail about themselves, "
                f"output a single concise sentence starting with 'User' summarizing that fact. "
                f"Examples: 'User prefers Python over Java.', 'User is a student studying machine learning.', "
                f"'User dislikes overly formal language.'. "
                f"If no personal fact was revealed (e.g. general questions, greetings, simple factual queries), "
                f"output exactly: NONE\n\n"
                f"User message: {user_message}\n"
                f"Assistant reply: {assistant_response}"
            )

            semantic_fact = await gemini_service._call_lightweight_gemini(semantic_prompt)

            if semantic_fact and semantic_fact.strip().upper() != "NONE" and len(semantic_fact.strip()) > 5:
                await self._store_memory(user_id, MemoryType.semantic, semantic_fact.strip())

            # 2. Generate episodic summary only if conversation is substantial (at least 6 turns)
            if len(history) >= 6 and len(history) % 6 == 0:
                recent_turns = history[-6:]
                conv_text = "\n".join(
                    f"{m['role'].capitalize()}: {m['content'][:200]}"
                    for m in recent_turns
                )
                episodic_prompt = (
                    f"Summarize the following conversation in one concise sentence (max 50 words). "
                    f"Focus on the core topic discussed. Do not mention names or dates.\n\n{conv_text}"
                )
                episodic_summary = await gemini_service._call_lightweight_gemini(episodic_prompt)
                if episodic_summary and len(episodic_summary.strip()) > 5:
                    await self._store_memory(user_id, MemoryType.episodic, episodic_summary.strip())

        except Exception as e:
            logger.error(f"[Memory] analyze_and_store failed for user {user_id}: {e}")


# Singleton instance
memory_service = MemoryService()
