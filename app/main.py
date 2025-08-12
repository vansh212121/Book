from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.exception_handler import register_exception_handlers
from app.core.middleware import register_middlewares
from app.db.session import db  # Import the database instance

from app.db import base

# Routers
from app.api.v1.endpoints import user, auth, admin, book, review, tag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # Startup: Connect to the database
    await db.connect()

    yield 

    # Shutdown: Disconnect from the database
    await db.disconnect()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        lifespan=lifespan,  # Register the lifespan handler
    )

    # Register all middleware
    register_middlewares(app)

    # Register all exception handlers
    register_exception_handlers(app)

    # Include your routers here later
    app.include_router(auth.router)
    app.include_router(user.router)
    app.include_router(admin.router)
    app.include_router(book.router)
    app.include_router(review.router)
    app.include_router(tag.router)

    return app


app = create_application()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
