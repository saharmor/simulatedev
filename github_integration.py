#!/usr/bin/env python3
"""
GitHub Integration for SimulateDev

This module handles GitHub API operations including:
- Creating pull requests
- Pushing changes to branches
- Managing repository operations
"""

import os
import subprocess
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class GitHubIntegration:
    """Handles GitHub API operations and git operations"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            print("WARNING: No GitHub token found. Pull request creation will be limited.")
        
        self.base_headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def parse_repo_info(self, repo_url: str) -> Dict[str, str]:
        """Parse repository URL to extract owner and repo name"""
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1].replace('.git', '')
            return {"owner": owner, "repo": repo}
        else:
            raise ValueError(f"Invalid repository URL: {repo_url}")
    
    def setup_git_config(self, repo_path: str):
        """Setup git configuration for the repository"""
        try:
            # Set up git user (required for commits)
            subprocess.run(
                ["git", "config", "user.name", "SimulateDev Bot"],
                cwd=repo_path,
                check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "simulatedev@example.com"],
                cwd=repo_path,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to setup git config: {e}")
            return False
    
    def create_branch(self, repo_path: str, branch_name: str) -> bool:
        """Create and checkout a new branch"""
        try:
            # Create and checkout new branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            print(f"SUCCESS: Created and checked out branch: {branch_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create branch {branch_name}: {e.stderr.decode()}")
            return False
    
    def commit_changes(self, repo_path: str, commit_message: str) -> bool:
        """Stage and commit all changes"""
        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                check=True
            )
            
            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--staged", "--quiet"],
                cwd=repo_path,
                capture_output=True
            )
            
            if result.returncode == 0:
                print("INFO: No changes to commit")
                return True
            
            # Commit changes
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            print(f"SUCCESS: Committed changes: {commit_message}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to commit changes: {e.stderr.decode()}")
            return False
    
    def push_branch(self, repo_path: str, branch_name: str, repo_url: str) -> bool:
        """Push branch to remote repository"""
        try:
            # Add remote origin if it doesn't exist
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path,
                capture_output=True
            )
            
            if result.returncode != 0:
                subprocess.run(
                    ["git", "remote", "add", "origin", repo_url],
                    cwd=repo_path,
                    check=True
                )
            
            # Push the branch
            subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            print(f"SUCCESS: Pushed branch {branch_name} to remote")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to push branch {branch_name}: {e.stderr.decode()}")
            return False
    
    def create_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        title: str,
        description: str,
        base_branch: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """Create a pull request on GitHub"""
        
        if not self.github_token:
            print("ERROR: Cannot create PR: No GitHub token configured")
            return None
        
        try:
            repo_info = self.parse_repo_info(repo_url)
            
            pr_data = {
                "title": title,
                "body": description,
                "head": branch_name,
                "base": base_branch,
                "maintainer_can_modify": True
            }
            
            url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo']}/pulls"
            
            response = requests.post(
                url,
                json=pr_data,
                headers=self.base_headers
            )
            
            if response.status_code == 201:
                pr_data = response.json()
                print(f"SUCCESS: Pull request created: {pr_data['html_url']}")
                return pr_data
            else:
                print(f"ERROR: Failed to create PR: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"ERROR: Error creating pull request: {str(e)}")
            return None
    
    def full_workflow(
        self,
        repo_path: str,
        repo_url: str,
        prompt: str,
        agent_name: str
    ) -> Optional[str]:
        """
        Complete workflow: create branch, commit changes, push, and create PR
        
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
        import time
        from datetime import datetime
        
        # Generate unique branch name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"simulatedev/{agent_name}_{timestamp}"
        
        # Setup git config
        if not self.setup_git_config(repo_path):
            return None
        
        # Create branch
        if not self.create_branch(repo_path, branch_name):
            return None
        
        # At this point, changes should already be made by the IDE
        # We just need to commit them
        commit_message = f"SimulateDev: {prompt}\n\nGenerated by {agent_name} via SimulateDev automation"
        
        if not self.commit_changes(repo_path, commit_message):
            return None
        
        # Push branch
        if not self.push_branch(repo_path, branch_name, repo_url):
            return None
        
        # Create pull request
        pr_title = f"[SimulateDev] {prompt}"
        pr_description = f"""
## Automated Changes by SimulateDev

**Agent Used:** {agent_name.title()}  
**Prompt:** {prompt}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

This pull request was automatically generated by SimulateDev using the {agent_name.title()} AI coding agent.

### What changed?
The AI agent analyzed your repository and implemented the requested changes based on the prompt: "{prompt}"

### Review Instructions
Please carefully review all changes before merging. While AI agents are powerful, human oversight is always recommended.

---
*Generated by [SimulateDev](https://github.com/your-username/simulatedev)*
        """
        
        pr = self.create_pull_request(
            repo_url=repo_url,
            branch_name=branch_name,
            title=pr_title,
            description=pr_description.strip()
        )
        
        if pr:
            return pr["html_url"]
        else:
            return None


def test_github_integration():
    """Test function for GitHub integration"""
    # This is just for testing - you can remove this function
    integration = GitHubIntegration()
    
    # Test parsing repo URL
    repo_info = integration.parse_repo_info("https://github.com/octocat/Hello-World")
    print(f"Parsed repo info: {repo_info}")


if __name__ == "__main__":
    test_github_integration() 