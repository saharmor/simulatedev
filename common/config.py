#!/usr/bin/env python3
"""
Configuration Module for SimulateDev

This module handles loading and managing configuration from environment variables
with sensible defaults for all settings.
"""

import os
from dotenv import load_dotenv
from typing import Optional


class Config:
    """Configuration manager for SimulateDev"""
    
    def __init__(self):
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Cache loaded values
        self._agent_timeout_seconds: Optional[int] = None
    
    @property
    def agent_timeout_seconds(self) -> int:
        """Get the agent execution timeout in seconds"""
        if self._agent_timeout_seconds is None:
            try:
                # Try to get from environment variable
                timeout_str = os.getenv('AGENT_TIMEOUT_SECONDS', '600')
                self._agent_timeout_seconds = int(timeout_str)
                
                # Validate reasonable bounds (30 seconds to 2 hours)
                if self._agent_timeout_seconds < 30:
                    print(f"WARNING: AGENT_TIMEOUT_SECONDS ({self._agent_timeout_seconds}) is too low, using minimum of 30 seconds")
                    self._agent_timeout_seconds = 30
                elif self._agent_timeout_seconds > 7200:  # 2 hours
                    print(f"WARNING: AGENT_TIMEOUT_SECONDS ({self._agent_timeout_seconds}) is very high, using maximum of 7200 seconds (2 hours)")
                    self._agent_timeout_seconds = 7200
                    
            except ValueError:
                print(f"WARNING: Invalid AGENT_TIMEOUT_SECONDS value '{os.getenv('AGENT_TIMEOUT_SECONDS')}', using default of 600 seconds")
                self._agent_timeout_seconds = 600
        
        return self._agent_timeout_seconds
    
    @property
    def anthropic_api_key(self) -> Optional[str]:
        """Get the Anthropic API key"""
        return os.getenv('ANTHROPIC_API_KEY')
    
    @property
    def google_api_key(self) -> Optional[str]:
        """Get the Google API key"""
        return os.getenv('GOOGLE_API_KEY')
    
    @property
    def github_token(self) -> Optional[str]:
        """Get the GitHub token"""
        return os.getenv('GITHUB_TOKEN')
    
    @property
    def git_user_name(self) -> str:
        """Get the git user name"""
        return os.getenv('GIT_USER_NAME', 'SimulateDev Bot')
    
    @property
    def git_user_email(self) -> str:
        """Get the git user email"""
        return os.getenv('GIT_USER_EMAIL', 'simulatedev@example.com')
    
    def validate_required_keys(self) -> bool:
        """Validate that required API keys are present"""
        missing_keys = []
        
        if not self.anthropic_api_key:
            missing_keys.append('ANTHROPIC_API_KEY')
        
        if not self.google_api_key:
            missing_keys.append('GOOGLE_API_KEY')
        
        if missing_keys:
            print(f"ERROR: Missing required environment variables: {', '.join(missing_keys)}")
            print("Please create a .env file based on env.example and add your API keys")
            return False
        
        return True
    
    def print_config_summary(self):
        """Print a summary of the current configuration"""
        print("Configuration Summary:")
        print(f"  Agent Timeout: {self.agent_timeout_seconds} seconds ({self.agent_timeout_seconds/60:.1f} minutes)")
        print(f"  Anthropic API Key: {'✓ Set' if self.anthropic_api_key else '✗ Missing'}")
        print(f"  Google API Key: {'✓ Set' if self.google_api_key else '✗ Missing'}")
        print(f"  GitHub Token: {'✓ Set' if self.github_token else '✗ Not set (optional)'}")
        print(f"  Git User: {self.git_user_name} <{self.git_user_email}>")


# Global configuration instance
config = Config() 