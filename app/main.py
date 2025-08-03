# # main.py or app.py
# from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.middleware.trustedhost import TrustedHostMiddleware

# from app.core.exception_handler import register_exception_handlers
# from app.core.config import settings
# from app.core.middleware import register_middlewares

# def create_application() -> FastAPI:
#     """Create and configure the FastAPI application."""

#     app = FastAPI(
#         title=settings.PROJECT_NAME,
#         version=settings.VERSION,
#         description=settings.DESCRIPTION,
#         docs_url="/api/docs",
#         redoc_url="/api/redoc",
#         openapi_url="/api/openapi.json"
#     )
#     # Register all middleware
#     register_middlewares(app)
#     # Register exception handlers
#     register_exception_handlers(app)

#     # Add middleware
#     # app.add_middleware(
#     #     CORSMiddleware,
#     #     allow_origins=settings.ALLOWED_ORIGINS,
#     #     allow_credentials=True,
#     #     allow_methods=["*"],
#     #     allow_headers=["*"],
#     # )

#     # if settings.ALLOWED_HOSTS:
#     #     app.add_middleware(
#     #         TrustedHostMiddleware,
#     #         allowed_hosts=settings.ALLOWED_HOSTS
#     #     )

#     # Include routers
#     # app.include_router(auth_router, prefix="/api/auth")
#     # app.include_router(users_router, prefix="/api/users")
#     # app.include_router(books_router, prefix="/api/books")

#     return app


# app = create_application()


# @app.get("/health")
# async def health_check():
#     """Health check endpoint."""
#     return {"status": "healthy"}
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.exception_handler import register_exception_handlers
from app.core.middleware import register_middlewares
from app.db.session import db  # Import the database instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # Startup: Connect to the database
    await db.connect()

    yield  # The application runs here

    # Shutdown: Disconnect from the database
    await db.disconnect()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,  # Register the lifespan handler
    )

    # Register all middleware
    register_middlewares(app)

    # Register all exception handlers
    register_exception_handlers(app)

    # Include your routers here later
    # app.include_router(...)

    return app


app = create_application()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
