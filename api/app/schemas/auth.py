from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """Response schema for user information"""
    id: str
    github_username: str
    github_email: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserSessionCreate(BaseModel):
    """Request schema for creating a user session"""
    session_code: str = Field(..., description="Temporary session identifier from OAuth callback")


class UserSessionResponse(BaseModel):
    """Response schema for user session information"""
    user: UserResponse
    session_expires_at: datetime
    
    class Config:
        from_attributes = True 