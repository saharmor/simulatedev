from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import sys
import os
import importlib

# Add parent directory to path for SimulateDev imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# temp fix for dynamic import of GitHubIntegration
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "src/github_integration.py"))
spec = importlib.util.spec_from_file_location("github_integration", module_path)
github_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(github_module)
GitHubIntegration = github_module.GitHubIntegration

# try:
#     from src.github_integration import GitHubIntegration
# except ImportError:
#     GitHubIntegration = None

from app.database import get_db
from app.dependencies import require_authentication, get_user_github_token
from app.models.user import User
from app.schemas.github import RepositoryInfo, IssueInfo, RepositoryIssues, PullRequestInfo, RepositoryPullRequests, SinglePullRequestInfo

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

@router.get("/repositories/{owner}/{repo}/pulls", response_model=RepositoryPullRequests)
async def get_repository_pull_requests(
    owner: str,
    repo: str,
    state: str = Query("open", description="Pull request state: open, closed, or all"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Pull requests per page"),
    search: Optional[str] = Query(None, description="Search term for filtering pull requests"),
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get pull requests for a specific repository"""
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
        
        response = requests.get(f'https://api.github.com/repos/{owner}/{repo}/pulls', 
                              headers=headers, params=params)
        response.raise_for_status()
        
        pull_requests = response.json()
        
        # If search term provided, filter by title and body
        if search and search.strip():
            search_lower = search.lower().strip()
            filtered_prs = []
            for pr in pull_requests:
                title = pr.get('title', '').lower()
                body = pr.get('body', '') or ''
                body_lower = body.lower()
                
                if (search_lower in title or search_lower in body_lower):
                    filtered_prs.append(pr)
            pull_requests = filtered_prs
        
        pr_info_list = [PullRequestInfo(
            id=pr['id'],
            number=pr['number'],
            title=pr['title'],
            body=pr.get('body', ''),
            state=pr['state'],
            created_at=pr['created_at'],
            updated_at=pr['updated_at'],
            html_url=pr['html_url'],
            user_login=pr['user']['login'],
            head_ref=pr['head']['ref'],
            base_ref=pr['base']['ref'],
            draft=pr.get('draft', False)
        ) for pr in pull_requests]
        
        return RepositoryPullRequests(
            pull_requests=pr_info_list,
            total_count=len(pr_info_list),
            page=page,
            per_page=per_page,
            has_more=len(pull_requests) == per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pull requests: {str(e)}")

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


@router.get("/repositories/{owner}/{repo}/pulls/{pr_number}", response_model=SinglePullRequestInfo)
async def get_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get a specific pull request by number"""
    if not GitHubIntegration:
        raise HTTPException(status_code=500, detail="GitHub integration not available")
    
    try:
        import requests
        headers = {'Authorization': f'token {github_token}'}
        response = requests.get(f'https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}', headers=headers)
        response.raise_for_status()
        
        pr_data = response.json()
        return SinglePullRequestInfo(
            id=pr_data['id'],
            number=pr_data['number'],
            title=pr_data['title'],
            body=pr_data.get('body'),
            state=pr_data['state'],
            created_at=pr_data['created_at'],
            updated_at=pr_data['updated_at'],
            html_url=pr_data['html_url'],
            user_login=pr_data['user']['login'],
            head_ref=pr_data['head']['ref'],
            base_ref=pr_data['base']['ref'],
            draft=pr_data.get('draft', False),
            additions=pr_data.get('additions', 0),
            deletions=pr_data.get('deletions', 0),
            changed_files=pr_data.get('changed_files', 0),
            mergeable=pr_data.get('mergeable'),
            mergeable_state=pr_data.get('mergeable_state'),
            merged=pr_data.get('merged', False),
            merged_at=pr_data.get('merged_at'),
            merged_by=pr_data.get('merged_by', {}).get('login') if pr_data.get('merged_by') else None,
            comments=pr_data.get('comments', 0),
            review_comments=pr_data.get('review_comments', 0),
            commits=pr_data.get('commits', 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pull request: {str(e)}") 