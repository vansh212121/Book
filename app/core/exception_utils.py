from typing import Optional, Type, TypeVar, Callable, Any
from functools import wraps
import asyncio

from app.core.exceptions import AppException, InternalServerError

T = TypeVar("T")


def handle_exceptions(
    default_exception: Type[AppException] = InternalServerError,
    message: Optional[str] = None,
) -> Callable:

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except AppException:
                # Re-raise our custom exceptions
                raise
            except Exception as e:
                # Convert other exceptions to our custom exception
                error_message = message or f"Error in {func.__name__}"
                raise default_exception(detail=error_message) from e

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except AppException:
                # Re-raise our custom exceptions
                raise
            except Exception as e:
                # Convert other exceptions to our custom exception
                error_message = message or f"Error in {func.__name__}"
                raise default_exception(detail=error_message) from e

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator

def raise_for_status(
    condition: bool,
    exception: Type[AppException],
    detail: Optional[str] = None,
    **kwargs: Any
) -> None:
    """
    Raise an exception if condition is True.
    
    Args:
        condition: If True, raise the exception
        exception: Exception class to raise
        detail: Custom error message
        **kwargs: Additional arguments for the exception
    
    Example:
        raise_for_status(
            user is None,
            ResourceNotFound,
            resource_name="User",
            resource_id=user_id
        )
    """
    if condition:
        if detail:
            kwargs['detail'] = detail
        raise exception(**kwargs)
