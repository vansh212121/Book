from pydantic import BaseModel, Field, EmailStr, model_validator, field_validator
from app.core.exceptions import ValidationError


class TokenRefresh(BaseModel):
    """Schema for requesting a new token pair using a refresh token."""

    refresh_token: str = Field(..., description="A valid refresh token.")


# -------PASSWORD-------
class PasswordChange(BaseModel):
    """Schema for an authenticated user to change their password."""

    current_password: str = Field(..., description="The user's current password.")
    new_password: str = Field(
        ..., min_length=8, description="The desired new password."
    )

    confirm_password: str = Field(..., description="Confirmation of the new password.")

    @model_validator(mode="after")
    def check_passwords_match(self) -> "PasswordResetConfirm":
        """Ensures that the new password and confirmation match."""
        pw1 = self.new_password
        pw2 = self.confirm_password
        if pw1 is not None and pw2 is not None and pw1 != pw2:
            raise ValidationError("Passwords do not match")
        return self

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforces password complexity rules with specific errors."""
        if not any(c.isupper() for c in v):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValidationError("Password must contain at least one digit")
        return v


class PasswordResetRequest(BaseModel):
    """Schema for requesting a password reset email."""

    email: EmailStr = Field(
        ..., description="The email address to send the reset link to."
    )


class PasswordResetConfirm(BaseModel):
    """Schema for confirming a password reset with a token."""

    token: str = Field(..., description="The password reset token from the email.")
    new_password: str = Field(
        ..., min_length=8, description="The desired new password."
    )
    confirm_password: str = Field(..., description="Confirmation of the new password.")

    @model_validator(mode="after")
    def check_passwords_match(self) -> "PasswordResetConfirm":
        """Ensures that the new password and confirmation match."""
        pw1 = self.new_password
        pw2 = self.confirm_password
        if pw1 is not None and pw2 is not None and pw1 != pw2:
            raise ValidationError("Passwords do not match")
        return self

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforces password complexity rules with specific errors."""
        if not any(c.isupper() for c in v):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValidationError("Password must contain at least one digit")
        return v


# ------EMAIL--------
class EmailChangeRequest(BaseModel):
    """Schema for a user to request an email change."""

    new_email: EmailStr = Field(..., description="The desired new email address.")


class EmailChangeConfirm(BaseModel):
    """Schema to confirm the email change with a token."""

    token: str = Field(
        ..., description="The email change confirmation token from the email."
    )


class EmailVerificationRequest(BaseModel):
    """Schema for requesting an email verification link."""

    email: EmailStr = Field(
        ..., description="The email address to send the verification link to."
    )
