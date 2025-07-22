from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import sys
import os

# Add parent directory to path for SimulateDev imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

try:
    from src.github_integration import GitHubIntegration
except ImportError:
    GitHubIntegration = None

from app.database import get_db
from app.dependencies import require_authentication, get_user_github_token
from app.models.user import User
from app.schemas.github import RepositoryInfo, IssueInfo, RepositoryIssues

router = APIRouter()

@router.get("/repositories", response_model=List[RepositoryInfo])
async def get_user_repositories(
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get repositories accessible to the authenticated user"""
    if not GitHubIntegration:
        raise HTTPException(status_code=500, detail="GitHub integration not available")
    
    try:
        github_integration = GitHubIntegration(github_token)
        # GitHubIntegration doesn't have list_user_repositories, so we'll use a basic API call
        import requests
        headers = {'Authorization': f'token {github_token}'}
        response = requests.get('https://api.github.com/user/repos', headers=headers, params={'per_page': 100})
        response.raise_for_status()
        
        repositories = response.json()
        return [RepositoryInfo(
            id=repo['id'],
            name=repo['name'],
            full_name=repo['full_name'],
            description=repo['description'],
            html_url=repo['html_url'],
            private=repo['private'],
            language=repo['language'],
            updated_at=repo['updated_at']
        ) for repo in repositories]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")

@router.get("/repositories/{owner}/{repo}/issues", response_model=RepositoryIssues)
async def get_repository_issues(
    owner: str,
    repo: str,
    state: str = Query("open", description="Issue state: open, closed, or all"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Issues per page"),
    search: Optional[str] = Query(None, description="Search term for filtering issues"),
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get issues for a specific repository"""
    if not GitHubIntegration:
        raise HTTPException(status_code=500, detail="GitHub integration not available")
    
    try:
        # Use direct API call since GitHubIntegration doesn't have this method
        import requests
        headers = {'Authorization': f'token {github_token}'}
        params = {
            "state": state,
            "page": page,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc"
        }
        
        response = requests.get(f'https://api.github.com/repos/{owner}/{repo}/issues', 
                              headers=headers, params=params)
        response.raise_for_status()
        
        issues = response.json()
        
        # Filter out pull requests (they appear in issues API)
        issues = [issue for issue in issues if not issue.get('pull_request')]
        
        # If search term provided, filter by title and body
        if search and search.strip():
            search_lower = search.lower().strip()
            filtered_issues = []
            for issue in issues:
                title = issue.get('title', '').lower()
                body = issue.get('body', '') or ''
                body_lower = body.lower()
                
                if (search_lower in title or search_lower in body_lower):
                    filtered_issues.append(issue)
            issues = filtered_issues
        
        issue_info_list = [IssueInfo(
            id=issue['id'],
            number=issue['number'],
            title=issue['title'],
            body=issue.get('body', ''),
            state=issue['state'],
            created_at=issue['created_at'],
            updated_at=issue['updated_at'],
            html_url=issue['html_url'],
            user_login=issue['user']['login']
        ) for issue in issues]
        
        return RepositoryIssues(
            issues=issue_info_list,
            total_count=len(issue_info_list),
            page=page,
            per_page=per_page,
            has_more=len(issues) == per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues: {str(e)}")

@router.get("/repositories/{owner}/{repo}")
async def get_repository_info(
    owner: str,
    repo: str,
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get information about a specific repository"""
    if not GitHubIntegration:
        raise HTTPException(status_code=500, detail="GitHub integration not available")
    
    try:
        import requests
        headers = {'Authorization': f'token {github_token}'}
        response = requests.get(f'https://api.github.com/repos/{owner}/{repo}', headers=headers)
        response.raise_for_status()
        
        repo_data = response.json()
        return RepositoryInfo(
            id=repo_data['id'],
            name=repo_data['name'],
            full_name=repo_data['full_name'],
            description=repo_data['description'],
            html_url=repo_data['html_url'],
            private=repo_data['private'],
            language=repo_data['language'],
            updated_at=repo_data['updated_at']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repository info: {str(e)}") 