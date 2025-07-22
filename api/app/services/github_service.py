import re
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse


class GitHubService:
    """Service for GitHub API interactions and repository operations"""
    
    def __init__(self):
        self.api_base = "https://api.github.com"
    
    def parse_repo_url(self, url: str) -> Dict[str, Any]:
        """Parse a GitHub repository URL to extract owner, repo, and issue information"""
        if not url:
            raise ValueError("Repository URL is required")
        
        # Clean up the URL
        url = url.strip()
        
        # Handle different GitHub URL formats
        patterns = [
            # Full issue URL: https://github.com/owner/repo/issues/123
            r'github\.com/([^/]+)/([^/]+)/issues/(\d+)',
            # Repository URL: https://github.com/owner/repo
            r'github\.com/([^/]+)/([^/]+)/?$',
            # Repository URL with .git: https://github.com/owner/repo.git
            r'github\.com/([^/]+)/([^/]+)\.git/?$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner = match.group(1)
                repo = match.group(2)
                
                result = {
                    'owner': owner,
                    'repo': repo,
                    'repo_url': f"https://github.com/{owner}/{repo}",
                    'type': 'repository'
                }
                
                # If it's an issue URL, extract issue number
                if len(match.groups()) >= 3:
                    issue_number = int(match.group(3))
                    result.update({
                        'issue_number': issue_number,
                        'issue_url': url,
                        'type': 'issue'
                    })
                
                return result
        
        raise ValueError(f"Invalid GitHub repository URL: {url}")
    
    def get_repository_info(self, owner: str, repo: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Get repository information from GitHub API"""
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'
        
        try:
            response = requests.get(f"{self.api_base}/repos/{owner}/{repo}", headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch repository info: {str(e)}")
    
    def get_issue_details(self, owner: str, repo: str, issue_number: int, token: Optional[str] = None) -> Dict[str, Any]:
        """Get issue details from GitHub API"""
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'
        
        try:
            response = requests.get(f"{self.api_base}/repos/{owner}/{repo}/issues/{issue_number}", headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch issue details: {str(e)}")
    
    def list_user_repositories(self, token: str) -> List[Dict[str, Any]]:
        """List repositories accessible to the authenticated user"""
        headers = {'Authorization': f'token {token}'}
        
        try:
            response = requests.get(f"{self.api_base}/user/repos", headers=headers, params={'per_page': 100})
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch user repositories: {str(e)}")
    
    def get_repository_issues(self, owner: str, repo: str, state: str = "open", 
                            page: int = 1, per_page: int = 30, search: str = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Get issues for a repository"""
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'
        
        params = {
            "state": state,
            "page": page,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc"
        }
        
        try:
            response = requests.get(f"{self.api_base}/repos/{owner}/{repo}/issues", headers=headers, params=params)
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
            
            return {
                "issues": issues,
                "total_count": len(issues),
                "page": page,
                "per_page": per_page,
                "has_more": len(issues) == per_page
            }
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch issues: {str(e)}")
    
    def synthesize_task_prompt(self, issue_data: Dict[str, Any], repo_info: Dict[str, Any]) -> str:
        """Synthesize a detailed task prompt from GitHub issue data"""
        
        # Extract issue information
        issue_title = issue_data.get('title', 'Unknown Issue')
        issue_body = issue_data.get('body', '')
        issue_number = issue_data.get('number')
        issue_url = issue_data.get('html_url', '')
        issue_labels = [label['name'] for label in issue_data.get('labels', [])]
        
        # Get issue comments if available
        comments_data = []
        if 'comments' in issue_data and issue_data['comments'] > 0:
            # This would require an additional API call in a full implementation
            pass
        
        # Build comprehensive task prompt
        task_prompt = f"""# GitHub Issue Resolution Task

## Issue Information
- **Repository**: {repo_info.get('repo_url', 'Unknown')}
- **Issue**: #{issue_number} - {issue_title}
- **URL**: {issue_url}
- **Type**: {'Bug Report' if 'bug' in [label.lower() for label in issue_labels] else 'Feature Request' if 'enhancement' in [label.lower() for label in issue_labels] else 'General Issue'}
- **Labels**: {', '.join(issue_labels) if issue_labels else 'None'}

## Issue Description
{issue_body or 'No description provided'}

"""
        
        # Add comments section if available
        if comments_data:
            task_prompt += "## Discussion from Issue Comments:\n\n"
            for i, comment in enumerate(comments_data, 1):
                author = comment.get('user', {}).get('login', 'Unknown')
                body = comment.get('body', '')
                task_prompt += f"**Comment {i} by @{author}:**\n{body}\n\n"
        
        task_prompt += """
## Task Instructions

Based on the issue description above, please:

1. **Analyze the Problem**: Carefully read through the issue description and any discussion to understand the root cause and requirements.

2. **Investigate the Codebase**: Examine the relevant parts of the codebase to understand the current implementation and identify where changes are needed.

3. **Implement the Solution**: 
   - Fix the bug, implement the feature, or address the issue as described
   - Follow the project's coding standards and patterns
   - Ensure your solution is robust and handles edge cases
   - Add appropriate error handling where needed

4. **Test Your Changes**: 
   - Verify that your solution works as expected
   - Test edge cases and potential failure scenarios
   - Ensure existing functionality is not broken

5. **Document Your Work**:
   - Add or update comments in the code where necessary
   - Update documentation if the changes affect user-facing functionality
   - Include a clear explanation of what was changed and why

## Success Criteria
- The issue described in #{issue_number} is resolved
- No existing functionality is broken
- Code follows project conventions
- Changes are well-tested and documented

Please implement a complete solution that addresses all aspects of the issue. Focus on creating a production-ready fix that can be safely merged.
"""
        
        return task_prompt 