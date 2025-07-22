from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class GitHubUser(BaseModel):
    """Schema for GitHub user information"""
    login: str
    avatar_url: str


class GitHubLabel(BaseModel):
    """Schema for GitHub issue labels"""
    name: str
    color: str


class GitHubPermissions(BaseModel):
    """Schema for GitHub repository permissions"""
    admin: bool
    push: bool
    pull: bool


class GitHubRepository(BaseModel):
    """Schema for GitHub repository information"""
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    language: Optional[str] = None
    stargazers_count: int = 0
    updated_at: datetime
    open_issues_count: int = 0
    has_issues: bool = True
    permissions: Optional[GitHubPermissions] = None


class GitHubRepositoryList(BaseModel):
    """Schema for paginated GitHub repository list"""
    repositories: List[GitHubRepository]
    total_count: int
    page: int
    per_page: int
    has_next: bool


class GitHubIssue(BaseModel):
    """Schema for GitHub issue information"""
    number: int
    title: str
    body: Optional[str] = None
    html_url: str
    state: str
    created_at: datetime
    updated_at: datetime
    comments: int = 0
    labels: List[GitHubLabel] = []
    user: GitHubUser


class GitHubIssueList(BaseModel):
    """Schema for paginated GitHub issue list"""
    issues: List[GitHubIssue]
    total_count: int
    page: int
    per_page: int 