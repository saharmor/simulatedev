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


class RepositoryInfo(BaseModel):
    """Schema for GitHub repository information"""
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    private: bool
    language: Optional[str] = None
    updated_at: str


class IssueInfo(BaseModel):
    """Schema for GitHub issue information"""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    created_at: str
    updated_at: str
    html_url: str
    user_login: str


class RepositoryIssues(BaseModel):
    """Schema for paginated GitHub issue list"""
    issues: List[IssueInfo]
    total_count: int
    page: int
    per_page: int
    has_more: bool


class PullRequestInfo(BaseModel):
    """Schema for GitHub pull request information"""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    created_at: str
    updated_at: str
    html_url: str
    user_login: str
    head_ref: str
    base_ref: str
    draft: bool = False


class RepositoryPullRequests(BaseModel):
    """Schema for paginated GitHub pull request list"""
    pull_requests: List[PullRequestInfo]
    total_count: int
    page: int
    per_page: int
    has_more: bool


class SinglePullRequestInfo(BaseModel):
    """Schema for detailed GitHub pull request information"""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    created_at: str
    updated_at: str
    html_url: str
    user_login: str
    head_ref: str
    base_ref: str
    draft: bool = False
    # Additional fields for single PR
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    merged: bool = False
    merged_at: Optional[str] = None
    merged_by: Optional[str] = None
    comments: int = 0
    review_comments: int = 0
    commits: int = 0


# Keep legacy schemas for backward compatibility
class GitHubRepository(BaseModel):
    """Legacy schema for GitHub repository information"""
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


class GitHubIssue(BaseModel):
    """Legacy schema for GitHub issue information"""
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