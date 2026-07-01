"""
Database session management for API Gateway.

Provides async SQLAlchemy session factory and dependency injection
for FastAPI routes.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Create async engine with connection pooling
# NullPool is used for serverless/serverful environments where connections
# should not be held open longer than necessary
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool if settings.ENVIRONMENT == "production" else None,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.

    Yields:
        AsyncSession: SQLAlchemy async session.

    The session is automatically closed after the request completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions outside of FastAPI requests.

    Usage:
        async with get_db_context() as session:
            result = await session.execute(...)
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database connection and verify connectivity.

    Called during application startup.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute("SELECT 1"))
    except Exception as e:
        raise RuntimeError(f"Failed to initialize database connection: {e}")


async def close_db() -> None:
    """
    Close database engine and all connections.

    Called during application shutdown.
    """
    await engine.dispose()