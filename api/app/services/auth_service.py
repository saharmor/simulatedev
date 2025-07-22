from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from typing import Optional
import secrets
import base64

from app.models.user import User, UserSession
from app.config import settings


class AuthService:
    """Service for handling authentication operations"""
    
    def __init__(self):
        # Initialize encryption for tokens
        if settings.encryption_key:
            # Ensure the key is properly formatted for Fernet
            try:
                # If it's a URL-safe base64 string, use it directly
                key = settings.encryption_key.encode()
                if len(key) != 44:  # Fernet keys are 44 characters when base64 encoded
                    # Generate a proper Fernet key from the provided key
                    key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
                self.cipher_suite = Fernet(key)
            except Exception:
                # If there's any issue, generate a new key
                self.cipher_suite = Fernet(Fernet.generate_key())
        else:
            self.cipher_suite = Fernet(Fernet.generate_key())
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a GitHub access token"""
        return self.cipher_suite.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a GitHub access token"""
        return self.cipher_suite.decrypt(encrypted_token.encode()).decode()
    
    def create_or_update_user(
        self,
        db: Session,
        github_user_id: int,
        github_username: str,
        github_email: Optional[str],
        avatar_url: Optional[str],
        access_token: str
    ) -> User:
        """Create a new user or update existing user with GitHub info"""
        
        # Check if user already exists
        user = db.query(User).filter(User.github_user_id == github_user_id).first()
        
        encrypted_token = self.encrypt_token(access_token)
        
        if user:
            # Update existing user
            user.github_username = github_username
            user.github_email = github_email
            user.avatar_url = avatar_url
            user.access_token_encrypted = encrypted_token
            user.last_login_at = datetime.utcnow()
            user.is_active = True
        else:
            # Create new user
            user = User(
                github_user_id=github_user_id,
                github_username=github_username,
                github_email=github_email,
                avatar_url=avatar_url,
                access_token_encrypted=encrypted_token,
                last_login_at=datetime.utcnow()
            )
            db.add(user)
        
        db.commit()
        db.refresh(user)
        return user
    
    def create_user_session(self, db: Session, user_id: str) -> UserSession:
        """Create a new user session"""
        
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        
        # Set expiration time
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        
        # Create session record
        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            last_accessed=datetime.utcnow()
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return session
    
    def get_current_user(self, db: Session, session_token: Optional[str]) -> Optional[User]:
        """Get current user from session token"""
        if not session_token:
            return None
        
        # Find session
        session = db.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
        
        if not session:
            return None
        
        # Check if session is expired
        if session.expires_at < datetime.utcnow():
            # Clean up expired session
            db.delete(session)
            db.commit()
            return None
        
        # Update last accessed
        session.last_accessed = datetime.utcnow()
        db.commit()
        
        return session.user
    
    def validate_session(self, db: Session, session_token: str) -> bool:
        """Validate if a session token is valid and not expired"""
        session = db.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
        
        if not session:
            return False
        
        if session.expires_at < datetime.utcnow():
            # Clean up expired session
            db.delete(session)
            db.commit()
            return False
        
        return True
    
    def cleanup_expired_sessions(self, db: Session):
        """Clean up expired sessions"""
        expired_sessions = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).all()
        
        for session in expired_sessions:
            db.delete(session)
        
        db.commit()
        return len(expired_sessions) 