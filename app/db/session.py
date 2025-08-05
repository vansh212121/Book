# In app/db/session.py
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# ** THE FIX IS HERE: Import the 'text' function **
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings

# Setup logging
logger = logging.getLogger(__name__)

class Database:
    """
    Manages the database connection, session creation, and engine lifecycle.
    """
    def __init__(self, db_url: str):
        # --- Tuneable connection pool settings for production performance ---
        self._engine = create_async_engine(
            db_url,
            echo=settings.DB_ECHO,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_timeout=settings.DB_POOL_TIMEOUT,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def connect(self) -> None:
        """
        Establishes and tests the database connection on application startup.
        This ensures the application fails fast if the database is unavailable.
        """
        logger.info("Initializing database connection...")
        try:
            async with self._engine.begin() as conn:
                # ** THE FIX IS HERE: Wrap the raw SQL in text() **
                await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SELECT 1")))
            logger.info("Database connection successful.")
        except (SQLAlchemyError, OSError) as e:
            logger.critical(f"Database connection failed: {e}", exc_info=True)
            # Re-raise to prevent the application from starting
            raise

    async def disconnect(self) -> None:
        """Closes the database connection pool on application shutdown."""
        logger.info("Closing database connection pool.")
        await self._engine.dispose()

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provides a session within a context manager for use outside of FastAPI
        dependencies (e.g., in background tasks or scripts).
        """
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Session commit failed, rolling back.", exc_info=True)
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency to get a database session.
        Yields a session and handles rollback on exceptions automatically.
        """
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

# --- Create a single, reusable database instance ---
db = Database(str(settings.DATABASE_URL))

# --- Dependency for use in FastAPI routes ---
get_session = db.get_session
