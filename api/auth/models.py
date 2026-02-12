"""Pydantic models for authentication requests and responses."""

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class UserLogin(BaseModel):
    """User login response."""
    access_token: str
    token_type: str = "bearer"
    user_id: str


class TokenRefresh(BaseModel):
    """Token refresh response."""
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class UserInfo(BaseModel):
    """Current user information."""
    id: str
    email: str
