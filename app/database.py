import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# Verify database URL availability
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in settings.")

# Create high-performance async engine for PostgreSQL
# pool_pre_ping helps detect and recycle dead connections
# pool_size and max_overflow optimize connection pooling for concurrent requests
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for verbose SQL logging in development
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Declarative base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Dependency injector to handle DB sessions safely in FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for obtaining an asynchronous database session.
    Automatically handles commit/rollback and ensures the session is closed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database transaction error, rolled back: {e}")
            raise
        finally:
            await session.close()
