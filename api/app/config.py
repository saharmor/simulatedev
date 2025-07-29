from pydantic_settings import BaseSettings
from typing import Optional, List
import os
import secrets

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./simulatedev.db"
    
    # GitHub OAuth
    github_client_id: str = "Ov23liz8BDMlzkAFWI22"
    github_client_secret: str = "a14fcd914d71b0d1c106ec5d2d5f3396a4bf3293"
    github_oauth_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    
    # Frontend URL (for OAuth redirects)
    frontend_url: str = "simulatedev:/"
    
    # SimulateDev paths
    simulatedev_root: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    @property
    def execution_output_path(self) -> str:
        return os.path.join(self.simulatedev_root, "execution_output")
    
    # Task settings
    max_concurrent_tasks: int = 5
    default_task_timeout: int = 1800
    max_task_history: int = 1000
    
    # Security
    secret_key: str = secrets.token_urlsafe(32)
    session_expire_hours: int = 8
    encryption_key: Optional[str] = "hey"  # For encrypting GitHub tokens
    
    # Rate limiting
    rate_limit_requests_per_minute: int = 60
    
    # CORS settings
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = "../.env"  # Look for .env in the parent directory (project root)
        extra = "ignore"  # Ignore extra environment variables not defined in this model
        
    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert comma-separated origins to list"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    def __post_init__(self):
        """Validate required settings"""
        if not self.encryption_key:
            # Generate a key for token encryption
            self.encryption_key = secrets.token_urlsafe(32)

settings = Settings() 