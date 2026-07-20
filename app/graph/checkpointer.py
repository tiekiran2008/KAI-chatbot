"""
Persistent LangGraph Checkpointer using AsyncPostgresSaver.

Initialized once at application startup (via main.py lifespan) and shared
across all graph invocations. Enables interrupt()/resume() across HTTP requests.
"""
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — set by init_checkpointer() at startup
_checkpointer = None


def get_checkpointer():
    """Return the initialized checkpointer. Raises if not yet initialized."""
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer has not been initialized. "
            "Ensure init_checkpointer() is called during app startup."
        )
    return _checkpointer


async def init_checkpointer():
    """
    Create and set up the AsyncPostgresSaver against the existing Supabase
    PostgreSQL database. Idempotent — safe to call multiple times.

    Creates the langgraph_checkpoints* tables automatically on first run.
    Must be awaited during app lifespan startup BEFORE building the graph.
    """
    global _checkpointer

    if _checkpointer is not None:
        logger.info("[HITL] Checkpointer already initialized — skipping.")
        return _checkpointer

    if not settings.HITL_ENABLED:
        logger.info("[HITL] HITL_ENABLED=false — skipping checkpointer initialization.")
        return None

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Build a psycopg3-compatible connection string
        # asyncpg uses postgresql+asyncpg:// — psycopg3 needs plain postgresql://
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

        checkpointer = await AsyncPostgresSaver.from_conn_string(db_url)
        await checkpointer.setup()  # Creates tables if they don't exist (idempotent)

        _checkpointer = checkpointer
        logger.info("[HITL] AsyncPostgresSaver initialized and tables verified.")
        return _checkpointer

    except Exception as e:
        logger.error(f"[HITL] Failed to initialize checkpointer: {e}")
        logger.warning("[HITL] Continuing without checkpointer — HITL will be disabled.")
        return None


async def close_checkpointer():
    """Clean up checkpointer connections during app shutdown."""
    global _checkpointer
    if _checkpointer is not None:
        try:
            await _checkpointer.aclose()
            logger.info("[HITL] Checkpointer connections closed.")
        except Exception as e:
            logger.warning(f"[HITL] Error closing checkpointer: {e}")
        finally:
            _checkpointer = None
