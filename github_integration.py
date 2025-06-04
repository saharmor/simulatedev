#!/usr/bin/env python3
"""
GitHub Integration for SimulateDev

This module handles GitHub API operations including:
- Creating pull requests
- Pushing changes to branches
- Managing repository operations
- Checking permissions and forking when needed
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
    
    def get_authenticated_user(self) -> Optional[str]:
        """Get the authenticated user's username"""
        if not self.github_token:
            return None
        
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers=self.base_headers
            )
            
            if response.status_code == 200:
                return response.json().get("login")
            else:
                print(f"ERROR: Failed to get authenticated user: {response.status_code}")
                return None
        except Exception as e:
            print(f"ERROR: Error getting authenticated user: {str(e)}")
            return None
    
    def check_push_permissions(self, repo_url: str) -> bool:
        """Check if we have push permissions to the repository"""
        if not self.github_token:
            print("INFO: No GitHub token, assuming no push permissions")
            return False
        
        try:
            repo_info = self.parse_repo_info(repo_url)
            url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo']}"
            
            response = requests.get(url, headers=self.base_headers)
            
            if response.status_code == 200:
                repo_data = response.json()
                permissions = repo_data.get("permissions", {})
                can_push = permissions.get("push", False)
                
                print(f"INFO: Push permissions for {repo_info['owner']}/{repo_info['repo']}: {can_push}")
                return can_push
            else:
                print(f"INFO: Cannot access repository permissions (status: {response.status_code}), assuming no push access")
                return False
                
        except Exception as e:
            print(f"WARNING: Error checking permissions: {str(e)}, assuming no push access")
            return False
    
    def fork_repository(self, repo_url: str) -> Optional[str]:
        """Fork the repository to the authenticated user's account"""
        if not self.github_token:
            print("ERROR: Cannot fork repository: No GitHub token configured")
            return None
        
        try:
            repo_info = self.parse_repo_info(repo_url)
            username = self.get_authenticated_user()
            
            if not username:
                print("ERROR: Cannot determine authenticated user for forking")
                return None
            
            # Check if fork already exists
            fork_url = f"https://github.com/{username}/{repo_info['repo']}"
            fork_api_url = f"https://api.github.com/repos/{username}/{repo_info['repo']}"
            
            response = requests.get(fork_api_url, headers=self.base_headers)
            if response.status_code == 200:
                print(f"INFO: Fork already exists: {fork_url}")
                return fork_url
            
            # Create fork
            fork_api_url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo']}/forks"
            response = requests.post(fork_api_url, headers=self.base_headers)
            
            if response.status_code == 202:  # 202 Accepted for fork creation
                fork_data = response.json()
                fork_url = fork_data["html_url"]
                print(f"SUCCESS: Repository forked: {fork_url}")
                
                # Wait a moment for fork to be ready
                import time
                print("INFO: Waiting for fork to be ready...")
                time.sleep(3)
                
                return fork_url
            else:
                print(f"ERROR: Failed to fork repository: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"ERROR: Error forking repository: {str(e)}")
            return None
    
    def update_remote_origin(self, repo_path: str, new_origin_url: str) -> bool:
        """Update the remote origin URL"""
        try:
            # Remove existing origin
            subprocess.run(
                ["git", "remote", "remove", "origin"],
                cwd=repo_path,
                capture_output=True
            )
            
            # Add new origin
            subprocess.run(
                ["git", "remote", "add", "origin", new_origin_url],
                cwd=repo_path,
                check=True
            )
            
            print(f"SUCCESS: Updated remote origin to: {new_origin_url}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to update remote origin: {e.stderr.decode()}")
            return False
    
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
        base_branch: str = "main",
        head_repo_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a pull request on GitHub
        
        Args:
            repo_url: Target repository URL (where PR will be created)
            branch_name: Name of the branch with changes
            title: PR title
            description: PR description
            base_branch: Target branch for the PR
            head_repo_url: Source repository URL (for cross-repo PRs), defaults to repo_url
        """
        
        if not self.github_token:
            print("ERROR: Cannot create PR: No GitHub token configured")
            return None
        
        try:
            target_repo_info = self.parse_repo_info(repo_url)
            
            # Determine head reference
            if head_repo_url and head_repo_url != repo_url:
                # Cross-repository PR (from fork to original)
                head_repo_info = self.parse_repo_info(head_repo_url)
                head_ref = f"{head_repo_info['owner']}:{branch_name}"
                print(f"INFO: Creating cross-repository PR from {head_repo_info['owner']}/{head_repo_info['repo']} to {target_repo_info['owner']}/{target_repo_info['repo']}")
            else:
                # Same repository PR
                head_ref = branch_name
                print(f"INFO: Creating PR within {target_repo_info['owner']}/{target_repo_info['repo']}")
            
            pr_data = {
                "title": title,
                "body": description,
                "head": head_ref,
                "base": base_branch,
                "maintainer_can_modify": True
            }
            
            url = f"https://api.github.com/repos/{target_repo_info['owner']}/{target_repo_info['repo']}/pulls"
            
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
    
    def smart_workflow(
        self,
        repo_path: str,
        original_repo_url: str,
        prompt: str,
        agent_name: str
    ) -> Optional[str]:
        """
        Smart workflow that handles permissions automatically:
        - If we have push permissions: work directly on original repo
        - If we don't have push permissions: fork, work on fork, create cross-repo PR
        
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
        import time
        from datetime import datetime
        
        print("INFO: Checking repository permissions...")
        has_push_permissions = self.check_push_permissions(original_repo_url)
        
        if has_push_permissions:
            print("SUCCESS: Have push permissions, working directly on original repository")
            return self.full_workflow(repo_path, original_repo_url, prompt, agent_name)
        else:
            print("INFO: No push permissions, using fork workflow...")
            return self.fork_workflow(repo_path, original_repo_url, prompt, agent_name)
    
    def fork_workflow(
        self,
        repo_path: str,
        original_repo_url: str,
        prompt: str,
        agent_name: str
    ) -> Optional[str]:
        """
        Fork-based workflow for repositories where we don't have push permissions
        
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
        import time
        from datetime import datetime
        
        # Step 1: Fork the repository
        print("INFO: Forking repository...")
        fork_url = self.fork_repository(original_repo_url)
        if not fork_url:
            print("ERROR: Failed to fork repository")
            return None
        
        # Step 2: Update remote origin to point to fork
        print("INFO: Updating remote origin to fork...")
        fork_git_url = fork_url + ".git"
        if not self.update_remote_origin(repo_path, fork_git_url):
            print("ERROR: Failed to update remote origin")
            return None
        
        # Step 3: Setup git config
        if not self.setup_git_config(repo_path):
            return None
        
        # Step 4: Create branch
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"simulatedev/{agent_name}_{timestamp}"
        
        if not self.create_branch(repo_path, branch_name):
            return None
        
        # Step 5: Commit changes
        commit_message = f"SimulateDev: {prompt}\n\nGenerated by {agent_name} via SimulateDev automation"
        
        if not self.commit_changes(repo_path, commit_message):
            return None
        
        # Step 6: Push to fork
        if not self.push_branch(repo_path, branch_name, fork_git_url):
            return None
        
        # Step 7: Create cross-repository pull request
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
            repo_url=original_repo_url,  # Target: original repo
            branch_name=branch_name,
            title=pr_title,
            description=pr_description.strip(),
            head_repo_url=fork_url  # Source: our fork
        )
        
        if pr:
            return pr["html_url"]
        else:
            return None


def test_github_integration():
    """Test function for GitHub integration"""
    integration = GitHubIntegration()
    
    # Test authentication
    print("Testing GitHub authentication...")
    username = integration.get_authenticated_user()
    if username:
        print(f"SUCCESS: Authenticated as: {username}")
    else:
        print("WARNING: Not authenticated or no token provided")
    
    # Test parsing repo URL
    test_repo_url = "https://github.com/octocat/Hello-World"
    print(f"\nTesting repo URL parsing: {test_repo_url}")
    repo_info = integration.parse_repo_info(test_repo_url)
    print(f"Parsed repo info: {repo_info}")
    
    # Test permission checking
    print(f"\nTesting permission checking for: {test_repo_url}")
    has_permissions = integration.check_push_permissions(test_repo_url)
    print(f"Push permissions: {has_permissions}")


if __name__ == "__main__":
    test_github_integration() 