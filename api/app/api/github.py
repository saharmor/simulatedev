from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from app.services.github_service import GitHubService
from app.dependencies import require_authentication, get_user_github_token
from app.models.user import User

router = APIRouter()
github_service = GitHubService()


@router.post("/parse-repo-url")
async def parse_repo_url(request: dict):
    """Parse a GitHub repository URL to extract repository information"""
    
    repo_url = request.get("repo_url")
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")
    
    try:
        result = github_service.parse_repo_url(repo_url)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse repository URL: {str(e)}")


@router.get("/repos/{owner}/{repo}/issues")
async def get_repository_issues(
    owner: str,
    repo: str,
    state: str = Query("open", description="Issue state (open, closed, all)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Issues per page"),
    search: Optional[str] = Query(None, description="Search term for filtering issues"),
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get issues for a repository"""
    
    try:
        result = github_service.get_repository_issues(
            owner=owner,
            repo=repo,
            state=state,
            page=page,
            per_page=per_page,
            search=search,
            token=github_token
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues: {str(e)}")


@router.get("/repos/{owner}/{repo}/issues/{issue_number}")
async def get_issue_details(
    owner: str, 
    repo: str, 
    issue_number: int,
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Get detailed information about a specific issue including comments"""
    
    try:
        result = github_service.get_issue_details(owner, repo, issue_number, token=github_token)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issue details: {str(e)}")


@router.post("/synthesize-task")
async def synthesize_task_from_issue(
    request: dict,
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Synthesize a task prompt from issue data"""
    
    owner = request.get("owner")
    repo = request.get("repo") 
    issue_number = request.get("issue_number")
    
    if not all([owner, repo, issue_number]):
        raise HTTPException(status_code=400, detail="owner, repo, and issue_number are required")
    
    try:
        # Get issue details
        issue_data = github_service.get_issue_details(owner, repo, issue_number, token=github_token)
        
        # Create repo info
        repo_info = {
            'repo_url': f"https://github.com/{owner}/{repo}",
            'owner': owner,
            'repo': repo
        }
        
        # Synthesize task prompt
        task_prompt = github_service.synthesize_task_prompt(issue_data, repo_info)
        
        return {
            "task_prompt": task_prompt,
            "issue_title": issue_data.get("title"),
            "issue_url": issue_data.get("html_url"),
            "issue_number": issue_number
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to synthesize task: {str(e)}") 