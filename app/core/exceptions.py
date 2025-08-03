from enum import Enum
from typing import Dict, Optional, Any, List


class ErrorCode(str, Enum):
    """Enumeration of error codes for consistent error identification."""

    # Authentication/Authorization
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    INACTIVE_USER = "INACTIVE_USER"
    UNVERIFIED_USER = "UNVERIFIED_USER"

    # Token Management
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_TYPE_INVALID = "TOKEN_TYPE_INVALID"
    TOKEN_REVOKED = "TOKEN_REVOKED"

    # Generic
    BAD_REQUEST = "BAD_REQUEST"

    # User Management
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"

    # Resource Management
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"

    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server Errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # Business Logic
    BUSINESS_LOGIC_ERROR = "BUSINESS_LOGIC_ERROR"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"


class AppException(Exception):
    """
    Base exception class for all custom application exceptions.

    This class provides a consistent interface for all application-specific
    exceptions, including HTTP status codes and structured error details.
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or self.__class__.__name__
        self.headers = headers
        self.context = context or {}
        super().__init__(detail)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.detail,
                "status_code": self.status_code,
                "context": self.context,
            }
        }


# ---- Authentication/Authorization Exceptions ----
class AuthenticationError(AppException):
    """Base class for authentication-related exceptions."""

    pass


class InvalidCredentials(AuthenticationError):
    """Raised when provided credentials are invalid."""

    def __init__(
        self,
        detail: str = "Incorrect email or password",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=ErrorCode.INVALID_CREDENTIALS,
            context=context,
        )


class NotAuthorized(AuthenticationError):
    """Raised when user lacks permission for an action."""

    def __init__(
        self,
        detail: str = "You are not authorized to perform this action.",
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:

        context = {}
        if resource:
            context["resource"] = resource
        if action:
            context[action] = action

        super().__init__(
            status_code=403,
            detail=detail,
            error_code=ErrorCode.NOT_AUTHORIZED,
            context=context,
        )


class InactiveUser(AuthenticationError):
    """Raised when an inactive user attempts to authenticate."""

    def __init__(
        self,
        detail: str = "Your account is inactive. Please contact support.",
        user_id: Optional[str] = None,
    ) -> None:
        context = {"user_id": user_id} if user_id else {}
        super().__init__(
            status_code=403,
            detail=detail,
            error_code=ErrorCode.INACTIVE_USER,
            context=context,
        )


class UnverifiedUser(AuthenticationError):
    """Raised when an unverified user attempts to access protected resources."""

    def __init__(
        self,
        detail: str = "Your account has not been verified. Please check your email.",
        user_id: Optional[str] = None,
    ) -> None:
        context = {"user_id": user_id} if user_id else {}
        super().__init__(
            status_code=403,
            detail=detail,
            error_code=ErrorCode.UNVERIFIED_USER,
            context=context,
        )


class BadRequestException(AppException):
    """Raised for general bad requests (400)."""

    def __init__(
        self,
        detail: str = "This request is invalid.",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:

        context = {}
        super().__init__(
            status_code=400,
            detail=detail,
            error_code=ErrorCode.BAD_REQUEST,
            context=context,
        )


# ---- Resource Exceptions ----
class ResourceNotFound(AppException):
    """Base class for resource not found exceptions."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        if not detail:
            detail = f"{resource_type} not found"

        context = {"resource_type": resource_type, "resource_id": resource_id}

        super().__init__(
            status_code=404,
            detail=detail,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            context=context,
        )


class ResourceAlreadyExists(AppException):
    """Base class for resource already exists exceptions."""

    def __init__(
        self,
        resource_type: str,
        detail: Optional[str] = None,
        identifier: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not detail:
            detail = f"{resource_type} already exists"

        context = {"resource_type": resource_type, "identifier": identifier or {}}

        super().__init__(
            status_code=409,
            detail=detail,
            error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
            context=context,
        )


# ---- Validation Exceptions ----
class ValidationError(AppException):
    """Raised when input validation fails."""

    def __init__(
        self,
        detail: str = "Validation failed",
        errors: Optional[List[Dict[str, Any]]] = None,
        field: Optional[str] = None,
    ) -> None:
        context = {"errors": errors or []}
        if field:
            context["field"] = field

        super().__init__(
            status_code=422,
            detail=detail,
            error_code=ErrorCode.VALIDATION_ERROR,
            context=context,
        )


class InvalidInput(AppException):
    """Raised when input is invalid but not due to validation rules."""

    def __init__(
        self, detail: str, field: Optional[str] = None, value: Optional[Any] = None
    ) -> None:
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)

        super().__init__(
            status_code=400,
            detail=detail,
            error_code=ErrorCode.INVALID_INPUT,
            context=context,
        )


# ---- Server Errors ----
class ServiceUnavailable(AppException):
    """Raised when a required service is unavailable."""

    def __init__(
        self,
        detail: str = "Service temporarily unavailable. Please try again later.",
        service: Optional[str] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        headers = {}
        context = {}

        if retry_after:
            headers["Retry-After"] = str(retry_after)
            context["retry_after"] = retry_after
        if service:
            context["service"] = service

        super().__init__(
            status_code=503,
            detail=detail,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            headers=headers,
            context=context,
        )


class InternalServerError(AppException):
    """Raised when an unexpected server error occurs."""

    def __init__(
        self,
        detail: str = "An unexpected error occurred. Please try again later.",
        error_id: Optional[str] = None,
    ) -> None:
        context = {"error_id": error_id} if error_id else {}
        super().__init__(
            status_code=500,
            detail=detail,
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            context=context,
        )


# ---- Token Exceptions-----
class InvalidToken(AuthenticationError):
    """Raised when a token is invalid or malformed."""

    def __init__(
        self,
        detail: str = "Token is invalid or has expired",
        token_type: Optional[str] = None,
    ) -> None:
        context = {"token_type": token_type} if token_type else {}
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=ErrorCode.INVALID_TOKEN,
            context=context,
        )


class TokenExpired(AuthenticationError):
    """Raised when a token has expired."""

    def __init__(
        self, detail: str = "Token has expired", token_type: Optional[str] = None
    ) -> None:
        context = {"token_type": token_type} if token_type else {}
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=ErrorCode.TOKEN_EXPIRED,
            context=context,
        )


class TokenTypeInvalid(AuthenticationError):
    """Raised when the token type is not the expected type for an operation."""

    def __init__(
        self,
        detail: str = "Invalid token type for this operation",
        expected: Optional[str] = None,
        received: Optional[str] = None,
    ) -> None:
        context = {}
        if expected:
            context["expected_type"] = expected
        if received:
            context["received_type"] = received

        super().__init__(
            status_code=401,
            detail=detail,
            error_code=ErrorCode.TOKEN_TYPE_INVALID,
            context=context,
            headers={"WWW-Authenticate": "Bearer"},
        )


class TokenRevoked(AuthenticationError):
    """Raised when a token has been revoked (blacklisted)."""

    def __init__(
        self, detail: str = "This token has been revoked and can no longer be used."
    ) -> None:
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=ErrorCode.TOKEN_REVOKED,  # Make sure this is in your ErrorCode enum
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---- Business Logic Exceptions ----
class BusinessLogicError(AppException):
    """Raised when business logic constraints are violated."""

    def __init__(self, detail: str, rule: Optional[str] = None) -> None:
        context = {"rule": rule} if rule else {}
        super().__init__(
            status_code=400,
            detail=detail,
            error_code=ErrorCode.BUSINESS_LOGIC_ERROR,
            context=context,
        )


class OperationNotAllowed(AppException):
    """Raised when an operation is not allowed due to business rules."""

    def __init__(
        self, detail: str, operation: Optional[str] = None, reason: Optional[str] = None
    ) -> None:
        context = {}
        if operation:
            context["operation"] = operation
        if reason:
            context["reason"] = reason

        super().__init__(
            status_code=400,
            detail=detail,
            error_code=ErrorCode.OPERATION_NOT_ALLOWED,
            context=context,
        )


# --- Rate Limiting Exceptions ---
class RateLimitExceeded(AppException):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        detail: str = "Rate limit exceeded. Please try again later.",
        retry_after: Optional[int] = None,
    ) -> None:
        headers = {}
        context = {}

        if retry_after:
            headers["Retry-After"] = str(retry_after)
            context["retry_after"] = retry_after

        super().__init__(
            status_code=429,
            detail=detail,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            headers=headers,
            context=context,
        )


# class AuthenticationError(AppException):
#     """Custom authentication error with logging"""

#     def __init__(
#         self,
#         detail: str = "",
#         request_id: Optional[str] = None,
#         user_info: Optional[str] = None,
#     ):
#         super().__init__(
#             status_code=401,
#             detail=detail,
#             headers={"WWW-Authenticate": "Bearer"},
#             error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
#             context=context,

#         )
#         # Log security event
#         logger.warning(
#             "Authentication failed",
#             extra={
#                 "detail": detail,
#                 "request_id": request_id,
#                 "user_info": user_info,
#                 "timestamp": datetime.utcnow().isoformat(),
#             },
#         )


# class AuthorizationError(AppException):
#     """Custom authorization error with logging"""

#     def __init__(
#         self,
#         detail: str,
#         user_id: Optional[str] = None,
#         required_roles: Optional[List[str]] = None,
#     ):
#         super().__init__(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=detail,
#         )
#         # Log security event
#         logger.warning(
#             "Authorization failed",
#             extra={
#                 "detail": detail,
#                 "user_id": user_id,
#                 "required_roles": required_roles,
#                 "timestamp": datetime.utcnow().isoformat(),
#             },
#         )
