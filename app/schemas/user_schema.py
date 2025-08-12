from typing import Optional, List, Dict, Any
from datetime import datetime, date

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
)

from app.models.user_model import UserRole
from app.core.exceptions import ValidationError


class UserBase(BaseModel):
    """Base schema for user data."""

    first_name: str = Field(
        ...,
        min_length=2,
        max_length=25,
        description="User's first name",
        examples=["John"],
    )
    last_name: str = Field(
        ...,
        min_length=2,
        max_length=25,
        description="User's full name",
        examples=["Doe"],
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=25,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique username",
    )
    email: EmailStr = Field(
        ..., description="User's email address", examples=["user@example.com"]
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate and normalize username."""
        return v.lower().strip()

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        """Validate and clean names."""
        return " ".join(v.strip().split())


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=6,
        max_length=30,
        description="Strong password",
        examples=["SecurePass123!"],
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Basic password strength validation."""
        if not any(c.isupper() for c in v):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValidationError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=25,
        description="User's New First name",
        examples=["John"],
    )
    last_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=25,
        description="User's New Last name",
        examples=["Doe"],
    )
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=25,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique username",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize username."""
        if v:
            return v.lower().strip()
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: Optional[str]) -> Optional[str]:
        """Validate and clean names."""
        if v:
            return " ".join(v.strip().split())
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_at_least_one_field(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure at least one field is provided for update."""
        if isinstance(values, dict) and not any(v is not None for v in values.values()):
            raise ValidationError("At least one field must be provided for update")
        return values


# --- Response Schemas ---
class UserResponse(UserBase):
    """Basic user response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="User ID")
    role: UserRole = Field(..., description="User role")
    is_verified: bool = Field(..., description="Email verification status")
    is_active: bool = Field(..., description="Account active status")
    created_at: datetime = Field(..., description="Registration timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Deletion timestamp")


class UserBasicResponse(BaseModel):
    """Minimal user response for inclusion in other schemas."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")


class UserPublicResponse(BaseModel):
    """Public user information (for other users)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    is_verified: bool = Field(..., description="Verification status")
    created_at: datetime = Field(..., description="Member since")


# --- Password Management Schemas ---
class UserPasswordChange(BaseModel):
    """Schema for changing password (authenticated users)."""

    current_password: str = Field(..., description="current password")
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=30,
        description="Strong password",
        examples=["SecurePass123!"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Basic password strength validation."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def validate_new_password_is_different(self) -> "UserPasswordChange":
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current one")
        return self


# --- List and Search Schemas ---
class UserListResponse(BaseModel):
    """Response for paginated user list."""

    items: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., ge=0, description="Total number of users")
    page: int = Field(..., ge=1, description="Current page number")
    pages: int = Field(..., ge=0, description="Total number of pages")
    size: int = Field(..., ge=1, le=100, description="Number of items per page")

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.pages

    @property
    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1


class UserSearchParams(BaseModel):
    """Parameters for searching users."""

    search: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Search in email, username, full name",
    )
    role: Optional[UserRole] = Field(None, description="Filter by role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_verified: Optional[bool] = Field(
        None, description="Filter by verification status"
    )
    created_after: Optional[date] = Field(
        None, description="Filter users created after this date"
    )
    created_before: Optional[date] = Field(
        None, description="Filter users created before this date"
    )
    has_books: Optional[bool] = Field(
        None, description="Filter users who have/haven't created books"
    )
    has_reviews: Optional[bool] = Field(
        None, description="Filter users who have/haven't written reviews"
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "UserSearchParams":
        """Ensure date range is valid."""
        if self.created_after and self.created_before:
            if self.created_after > self.created_before:
                raise ValueError("created_after must be before created_before")
        return self


__all__ = [
    "UserBase",
    "UserCreate",
    "UserUpdate",
    # Response schemas
    "UserResponse",
    "UserBasicResponse",
    "UserPublicResponse",
    # List schemas
    "UserListResponse",
    # Password schemas
    "UserPasswordChange",
    # List and Search Schemas
    "UserSearchParams",
]
