# In app/core/middleware.py
import time
import uuid
import logging

from typing import Optional, Set
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from app.core.config import settings
from app.core.security import SecurityHeaders

# Get a logger instance
logger = logging.getLogger(__name__)


class ProfessionalLoggingMiddleware(BaseHTTPMiddleware):
    """
    A professional-grade logging middleware that adds a unique request ID
    and logs structured information about each request with comprehensive error handling.
    """

    def __init__(self, app, exclude_paths: Optional[Set[str]] = None):
        super().__init__(app)
        # Exclude health check and metrics endpoints from detailed logging
        self.exclude_paths = exclude_paths or {"/health", "/metrics", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        # 1. Set up request ID and timing
        request_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()

        # 2. Decide if we should perform detailed logging
        should_log = request.url.path not in self.exclude_paths

        # 3. Log the incoming request if applicable
        if should_log:
            # Check for large requests and log a warning if needed
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > getattr(
                settings, "MAX_REQUEST_SIZE", 10 * 1024 * 1024
            ):
                logger.warning(
                    "Large request detected",
                    extra={
                        "request_id": request_id,
                        "content_length": content_length,
                        "path": request.url.path,
                    },
                )

            # The main incoming request log
            logger.info(
                "Incoming request",
                extra={
                    "request_id": request_id,
                    "client_ip": self._get_client_ip(request),
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": (
                        str(request.query_params) if request.query_params else None
                    ),
                    "user_agent": request.headers.get("user-agent", "unknown"),
                },
            )

        # 4. Process the request. Any exception here will be caught by FastAPI's
        #    dedicated exception handlers, which is the desired behavior.
        response = await call_next(request)

        # 5. Prepare and log the outgoing response
        process_time = (time.time() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id

        if should_log:
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time, 2),
                    "response_size": response.headers.get("content-length", "unknown"),
                },
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP considering proxy headers"""
        # Check for forwarded headers first (common in production behind reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses by fetching them
    from the centralized SecurityHeaders class.
    """

    async def dispatch(self, request: Request, call_next):
        # Process the request to get the response
        response = await call_next(request)

        # 1. Get the base set of security headers from our centralized class
        headers = SecurityHeaders.get_headers()

        # 2. Add context-specific headers conditionally
        # Add HSTS only for HTTPS requests
        if request.url.scheme == "https":
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Add a basic Content Security Policy only for HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            headers["Content-Security-Policy"] = "default-src 'self';"

        # 3. Apply all the collected headers to the response
        for header, value in headers.items():
            response.headers[header] = value

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request payload size
    """

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Payload Too Large",
                    "message": f"Request payload exceeds maximum size of {self.max_size} bytes",
                    "max_size": self.max_size,
                    "received_size": int(content_length),
                },
            )

        return await call_next(request)


def register_middlewares(app: FastAPI):
    """
    Registers all middlewares for the FastAPI application.
    The order of middleware is important - they are executed in reverse order of registration.
    """

    # Validate and prepare configuration
    allowed_hosts = _get_allowed_hosts()
    cors_origins = _get_cors_origins()

    # 1. Request Size Limit Middleware (should be early to reject large requests quickly)
    max_request_size = getattr(
        settings, "MAX_REQUEST_SIZE", 10 * 1024 * 1024
    )  # 10MB default
    app.add_middleware(RequestSizeLimitMiddleware, max_size=max_request_size)

    # 2. GZip Middleware (compress responses) - should be high up
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 3. Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 4. Trusted Host Middleware (protect against host header attacks)
    if allowed_hosts and "*" not in allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    else:
        logger.warning(
            "TrustedHostMiddleware disabled: ALLOWED_HOSTS contains '*' or is not configured"
        )

    # 5. CORS Middleware (allow cross-origin requests)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],  # Expose our custom header
    )

    # 6. Custom logging middleware (should be last to capture all request/response data)
    exclude_paths = getattr(
        settings, "LOGGING_EXCLUDE_PATHS", {"/health", "/metrics", "/favicon.ico"}
    )
    app.add_middleware(ProfessionalLoggingMiddleware, exclude_paths=exclude_paths)

    logger.info("All middlewares registered successfully")


def _get_allowed_hosts() -> list[str]:
    """Validate and return allowed hosts configuration"""
    if not hasattr(settings, "ALLOWED_HOSTS") or not settings.ALLOWED_HOSTS:
        logger.warning("ALLOWED_HOSTS not configured, using restrictive default")
        return ["localhost", "127.0.0.1"]

    hosts = [host.strip() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()]

    if not hosts:
        logger.warning(
            "ALLOWED_HOSTS is empty after parsing, using restrictive default"
        )
        return ["localhost", "127.0.0.1"]

    logger.info(f"Configured allowed hosts: {hosts}")
    return hosts


def _get_cors_origins() -> list[str]:
    """Validate and return CORS origins configuration"""
    if not hasattr(settings, "CORS_ORIGINS") or not settings.CORS_ORIGINS:
        logger.warning("CORS_ORIGINS not configured, using restrictive default")
        return ["http://localhost:3000", "http://localhost:8000"]

    origins = [
        origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
    ]

    if not origins:
        logger.warning("CORS_ORIGINS is empty after parsing, using restrictive default")
        return ["http://localhost:3000", "http://localhost:8000"]

    logger.info(f"Configured CORS origins: {origins}")
    return origins
