from fastapi import APIRouter, HTTPException, Response, Cookie, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import requests
from datetime import datetime

from app.database import get_db
from app.models.user import UserSession
from app.schemas.auth import UserResponse, UserSessionCreate, UserSessionResponse
from app.services.auth_service import AuthService
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_service = AuthService()


@router.get("/github")
async def github_auth_redirect():
    """Redirect user to GitHub OAuth authorization page"""
    if not settings.github_client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    
    # Request repo scope for both public and private repository access
    auth_url = f"https://github.com/login/oauth/authorize?client_id={settings.github_client_id}&scope=repo,user:email"
    return RedirectResponse(auth_url)


@router.get("/github/callback")
async def github_auth_callback(
    code: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    """Handle GitHub OAuth callback and exchange code for token"""
    if error:
        return RedirectResponse(f"{settings.frontend_url}/login?error={error}")
    
    if not code:
        return RedirectResponse(f"{settings.frontend_url}/login?error=missing_code")
    
    try:
        # Exchange code for access token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")
        
        token_data = token_response.json()
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="No access token received")
        
        access_token = token_data["access_token"]
        
        # Get user info from GitHub
        user_response = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info from GitHub")
        
        github_user = user_response.json()
        
        # Get user email (might be private)
        email_response = requests.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"token {access_token}"}
        )
        
        primary_email = None
        if email_response.status_code == 200:
            emails = email_response.json()
            for email in emails:
                if email.get("primary", False):
                    primary_email = email.get("email")
                    break
        
        # Create or update user
        user = auth_service.create_or_update_user(
            db=db,
            github_user_id=github_user["id"],
            github_username=github_user["login"],
            github_email=primary_email,
            avatar_url=github_user.get("avatar_url"),
            access_token=access_token
        )
        
        # Create session
        session = auth_service.create_user_session(db, user.id)
        
        # Redirect to frontend with session code
        return RedirectResponse(f"{settings.frontend_url}?auth_success=true&session_code={session.id}")
        
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        return RedirectResponse(f"{settings.frontend_url}/login?error=oauth_failed")


@router.post("/session", response_model=UserSessionResponse)
async def create_session(
    session_request: UserSessionCreate,
    response: Response,
    db: Session = Depends(get_db)
):
    """Exchange session code for authenticated session"""
    try:
        # Find the session by ID (session_code)
        session = db.query(UserSession).filter(
            UserSession.id == session_request.session_code
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check if session is expired
        if session.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Session expired")
        
        # Update last accessed
        session.last_accessed = datetime.utcnow()
        db.commit()
        
        # Set secure cookie with development-friendly settings
        cookie_value = session.session_token
        print(f"Setting session cookie: {cookie_value[:10]}... for user {session.user.github_username}")
        
        response.set_cookie(
            key="session_token",
            value=cookie_value,
            httponly=True,
            max_age=settings.session_expire_hours * 3600,
            samesite="lax",  # Lax is more compatible than None for HTTP
            secure=False,  # Set to True in production with HTTPS
            domain=None,  # Let browser determine the domain
            path="/"  # Ensure cookie is available for all paths
        )
        
        return UserSessionResponse(
            user=UserResponse.model_validate(session.user),
            session_expires_at=session.expires_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    session_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Get current authenticated user"""
    user = auth_service.get_current_user(db, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Logout user and invalidate session"""
    if session_token:
        # Find and delete session
        session = db.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
        
        if session:
            db.delete(session)
            db.commit()
    
    # Clear cookie
    response.delete_cookie(key="session_token")
    
    return {"message": "Logged out successfully"}


@router.get("/debug/session")
async def debug_session(
    request: Request,
    session_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Debug endpoint to check session status"""
    return {
        "cookie_received": session_token is not None,
        "cookie_value": session_token[:10] + "..." if session_token else None,
        "headers": dict(request.headers),
        "cookies": dict(request.cookies) if hasattr(request, 'cookies') else None
    }


@router.get("/repositories")
async def get_user_repositories(
    session_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Fetch user's accessible repositories"""
    user = auth_service.get_current_user(db, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Decrypt access token
        access_token = auth_service.decrypt_token(user.access_token_encrypted)
        
        # Fetch repositories from GitHub API (both public and private)
        repos_response = requests.get(
            "https://api.github.com/user/repos?visibility=all&sort=updated&per_page=100",
            headers={"Authorization": f"token {access_token}"}
        )
        
        if repos_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch repositories from GitHub")
        
        repos = repos_response.json()
        
        formatted_repos = [
            {
                "owner": repo["owner"]["login"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "url": repo["html_url"],
                "description": repo.get("description"),
                "private": repo["private"],
                "language": repo.get("language"),
                "updated_at": repo.get("updated_at")
            }
            for repo in repos
        ]
        
        return {"repositories": formatted_repos}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}") 