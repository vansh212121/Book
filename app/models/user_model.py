from sqlmodel import (
    SQLModel,
    Field,
    Relationship,
    Column,
    String,
    DateTime,
)
from sqlalchemy import func
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

# Using PyEnum to avoid conflict with SQLModel's Enum
class UserRole(str, PyEnum):
    USER = "user"
    MODERATOR = "moderator" # Corrected capitalization
    ADMIN = "admin"

    @property
    def priority(self) -> int:
        priorities = {self.USER: 1, self.MODERATOR: 2, self.ADMIN: 3}
        return priorities.get(self, 0)

    def __lt__(self, other: "UserRole") -> bool:
        if not isinstance(other, UserRole):
            return NotImplemented
        return self.priority < other.priority

class UserBase(SQLModel):
    first_name: str = Field(
        min_length=2,
        max_length=25,
        description="User's first name.",
        schema_extra={"example": "Jane"},
    )
    last_name: str = Field(
        min_length=2,
        max_length=25,
        description="User's last name",
        schema_extra={"example": "Doe"}, # Corrected syntax
    )
    username: str = Field(
        min_length=3,
        max_length=25,
        regex="^[a-zA-Z0-9_-]+$",
        description="User's unique username",
        schema_extra={"example": "jane_doe_123"}, # Corrected syntax
    )
    email: str = Field(
        max_length=200,
        description="User's email address",
        schema_extra={"example": "user@example.com"},
    )
    role: UserRole = Field(
        default=UserRole.USER, description="User's role in the system"
    )
    is_verified: bool = Field(default=False, description="Whether email is verified")
    is_active: bool = Field(default=True, description="Whether account is active")


class User(UserBase, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(
        default=None, primary_key=True, description="Unique Identifier"
    )
    email: str = Field(
        sa_column=Column(String(200), unique=True, nullable=False, index=True)
    )
    username: str = Field(
        sa_column=Column(String(25), nullable=False, index=True, unique=True)
    )
    hashed_password: str = Field(
        min_length=60, max_length=255, description="Hashed password", exclude=True
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
        description="Account creation timestamp",
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            server_onupdate=func.now(), # Correctly updates on every change
            nullable=False,
        ),
        description="Account last updated timestamp",
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="Timestamp for soft delete",
    )

    # --- Computed properties (data-focused) ---
    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.role >= UserRole.MODERATOR

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role.value}')>"