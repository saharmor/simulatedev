from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService


auth_service = AuthService()


async def get_current_user(
    session_token: str = Cookie(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Dependency to get current authenticated user (optional)"""
    if not session_token:
        return None
    
    user = auth_service.get_current_user(db, session_token)
    return user


async def require_authentication(
    session_token: str = Cookie(None),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to require authentication - raises 401 if not authenticated"""
    user = auth_service.get_current_user(db, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return user


async def get_user_github_token(
    user: User = Depends(require_authentication)
) -> str:
    """Dependency to get the authenticated user's GitHub token"""
    try:
        token = auth_service.decrypt_token(user.access_token_encrypted)
        return token
    except Exception as e:
        print(f"Failed to decrypt GitHub token for user {user.github_username}: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid or expired GitHub token: {str(e)}") 