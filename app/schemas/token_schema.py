# In app/schemas/token_schema.py

from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    """
    Defines the response model for a successful token request (e.g., login).
    """
    access_token: str = Field(..., description="The JWT access token.")
    refresh_token: str = Field(..., description="The JWT refresh token.")
    token_type: str = Field("bearer", description="The type of token, typically 'bearer'.")
