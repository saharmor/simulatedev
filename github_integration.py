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
    
    def get_default_branch(self, repo_url: str) -> str:
        """Get the default branch of a repository
        
        Args:
            repo_url: Repository URL
            
        Returns:
            str: Default branch name (fallback to 'main' if detection fails)
        """
        if not self.github_token:
            print("WARNING: No GitHub token, assuming 'main' as default branch")
            return "main"
        
        try:
            repo_info = self.parse_repo_info(repo_url)
            url = f"https://api.github.com/repos/{repo_info['owner']}/{repo_info['repo']}"
            
            response = requests.get(url, headers=self.base_headers)
            
            if response.status_code == 200:
                repo_data = response.json()
                default_branch = repo_data.get("default_branch", "main")
                print(f"INFO: Detected default branch: {default_branch}")
                return default_branch
            else:
                print(f"WARNING: Cannot detect default branch (status: {response.status_code}), using 'main'")
                return "main"
                
        except Exception as e:
            print(f"WARNING: Error detecting default branch: {str(e)}, using 'main'")
            return "main"

    def create_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        title: str,
        description: str,
        base_branch: Optional[str] = None,
        head_repo_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a pull request on GitHub
        
        Args:
            repo_url: Target repository URL (where PR will be created)
            branch_name: Name of the branch with changes
            title: PR title
            description: PR description
            base_branch: Target branch for the PR (auto-detected if None)
            head_repo_url: Source repository URL (for cross-repo PRs), defaults to repo_url
        """
        
        if not self.github_token:
            print("ERROR: Cannot create PR: No GitHub token configured")
            return None
        
        try:
            target_repo_info = self.parse_repo_info(repo_url)
            
            # Auto-detect base branch if not provided
            if base_branch is None:
                base_branch = self.get_default_branch(repo_url)
            
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
            
            print(f"INFO: PR details - head: {head_ref}, base: {base_branch}")
            
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
            elif response.status_code == 422:
                # Handle validation errors - try common branch names
                print(f"WARNING: PR creation failed with validation error. Trying fallback branches...")
                
                fallback_branches = ["master", "develop", "dev"]
                if base_branch not in fallback_branches:
                    fallback_branches.insert(0, "main")  # Try main first if not already tried
                
                for fallback_branch in fallback_branches:
                    if fallback_branch == base_branch:
                        continue  # Skip the one we already tried
                    
                    print(f"INFO: Trying base branch: {fallback_branch}")
                    pr_data["base"] = fallback_branch
                    
                    retry_response = requests.post(
                        url,
                        json=pr_data,
                        headers=self.base_headers
                    )
                    
                    if retry_response.status_code == 201:
                        pr_data = retry_response.json()
                        print(f"SUCCESS: Pull request created with base branch '{fallback_branch}': {pr_data['html_url']}")
                        return pr_data
                
                print(f"ERROR: Failed to create PR with any base branch: {response.status_code} - {response.text}")
                return None
            else:
                print(f"ERROR: Failed to create PR: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"ERROR: Error creating pull request: {str(e)}")
            return None
    
    def generate_commit_and_pr_content_with_claude(self, agent_execution_report_summary: str, agent_name: str) -> Dict[str, Any]:
        """
        Use Claude to generate both commit message and PR content in a single API call
        
        Args:
            agent_execution_report_summary: The summary/output from the coding agent
            agent_name: Name of the agent used
            
        Returns:
            Dict with 'commit_message', 'pr_title', 'pr_description', and 'pr_changes_summary' keys
        """
        try:
            from anthropic import Anthropic
            
            # Get API key from environment
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                print("WARNING: No ANTHROPIC_API_KEY found, using default formats")
                return self._generate_default_commit_and_pr_content(agent_name)
            
            # Initialize Anthropic client
            client = Anthropic(api_key=api_key)
            
            system_prompt = """You are a technical writing assistant specializing in creating professional git commit messages and pull request descriptions from AI coding agent outputs.

Given a coding agent's execution report summary, original prompt, and agent name, generate:
1. A professional git commit message following conventional commit standards
2. A concise, descriptive PR title (max 60 characters)
3. A professional PR description 
4. A clear summary of what changed

Format your response as JSON with these exact keys:
{
    "commit_message": "Professional git commit message following conventional commit format",
    "pr_title": "Brief, descriptive PR title",
    "pr_description": "Professional description of the changes",
    "pr_changes_summary": "Clear summary of what was modified/added/removed"
}

Guidelines for commit message:
- Use conventional commit format: type(scope): description
- Keep the first line under 72 characters
- Use present tense, imperative mood ("Add feature" not "Added feature")
- Be specific about what was changed
- Include a brief body if the changes are complex
- Common types: feat, fix, refactor, docs, style, test, chore

Guidelines for PR content:
- Title should be actionable and specific (e.g., "Add user authentication system" not "Update code")
- Description should be 2-3 sentences explaining the purpose and approach
- Changes summary should list the key files/features modified
- Keep it professional and technical but accessible
- Focus on what was accomplished, not just what was requested"""

            user_message = f"""
Agent Used: {agent_name}

Agent Execution Report Summary:
{agent_execution_report_summary}

Please generate a professional git commit message and PR content based on this information.
"""

            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=2500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            
            # Parse Claude's response
            response_text = response.content[0].text.strip()
            
            try:
                # Remove any markdown code block formatting
                if response_text.startswith('```'):
                    response_text = response_text.split('\n', 1)[1]
                if response_text.endswith('```'):
                    response_text = response_text.rsplit('\n', 1)[0]
                
                import json
                parsed_response = json.loads(response_text)
                
                # Validate required keys
                required_keys = ['commit_message', 'pr_title', 'pr_description', 'pr_changes_summary']
                if all(key in parsed_response for key in required_keys):
                    # Basic validation for commit message
                    commit_msg = parsed_response['commit_message']
                    if commit_msg and len(commit_msg) > 10:
                        print("SUCCESS: Generated commit message and PR content using Claude 3.7")
                        return parsed_response
                    else:
                        print("WARNING: Claude generated invalid commit message, using default formats")
                        return self._generate_default_commit_and_pr_content(agent_name)
                else:
                    print("WARNING: Claude response missing required keys, using default formats")
                    return self._generate_default_commit_and_pr_content(agent_name)
                    
            except json.JSONDecodeError as e:
                print(f"WARNING: Failed to parse Claude response as JSON: {e}")
                print(f"Response was: {response_text}")
                return self._generate_default_commit_and_pr_content(agent_name)
                
        except Exception as e:
            print(f"WARNING: Error calling Claude for content generation: {str(e)}")
            return self._generate_default_commit_and_pr_content(agent_name)
    
    def _generate_default_commit_and_pr_content(self, agent_name: str) -> Dict[str, Any]:
        """Generate default commit message and PR content when Claude processing fails"""
        return {
            "commit_message": f"SimulateDev by {agent_name}",
            "pr_title": f"[SimulateDev] {agent_name[:50]}{'...' if len(agent_name) > 50 else ''}",
            "pr_description": f"Automated changes generated by the {agent_name.title()} AI coding agent.",
            "pr_changes_summary": f"The AI agent analyzed the repository and implemented changes according to the request: \"{agent_name}\""
        }

    def generate_pr_description(self, agent_name: str, pr_title: str, pr_description: str, pr_changes_summary: str) -> tuple[str, str]:
        """
        Generate formatted PR title and description
        
        Args:
            agent_name: Name of the agent used
            pr_title: PR title from Claude or default
            pr_description: PR description from Claude or default
            pr_changes_summary: Changes summary from Claude or default
            
        Returns:
            tuple[str, str]: (pr_title, formatted_pr_description)
        """
        from datetime import datetime
        
        formatted_pr_description = f"""
## Automated Changes by SimulateDev

**Agent Used:** {agent_name.title()}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{pr_description}

### What changed?
{pr_changes_summary}

### Review Instructions
Please carefully review all changes before merging. While AI agents are powerful, human oversight is always recommended.

---
*Generated by [SimulateDev](https://github.com/saharmor/simulatedev)*
        """
        
        return pr_title, formatted_pr_description.strip()

    def full_workflow(
        self,
        repo_path: str,
        repo_url: str,
        agent_name: str,
        agent_execution_report_summary: Optional[str] = None
    ) -> Optional[str]:
        """
        Complete workflow: create branch, commit changes, push, and create PR
        
        Args:
            agent_execution_report_summary: Optional summary/output from the coding agent for better content generation
        
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
        
        # Generate commit message and PR content using Claude (single API call)
        if agent_execution_report_summary:
            content = self.generate_commit_and_pr_content_with_claude(agent_execution_report_summary, agent_name)
            commit_message = content["commit_message"]
            pr_title, pr_description = self.generate_pr_description(
                agent_name,
                content["pr_title"],
                content["pr_description"],
                content["pr_changes_summary"]
            )
        else:
            # Use default formats when no agent output is provided
            default_content = self._generate_default_commit_and_pr_content(agent_name)
            commit_message = default_content["commit_message"]
            pr_title, pr_description = self.generate_pr_description(
                agent_name,
                default_content["pr_title"],
                default_content["pr_description"],
                default_content["pr_changes_summary"]
            )
        
        if not self.commit_changes(repo_path, commit_message):
            return None
        
        # Push branch
        if not self.push_branch(repo_path, branch_name, repo_url):
            return None
        
        pr = self.create_pull_request(
            repo_url=repo_url,
            branch_name=branch_name,
            title=pr_title,
            description=pr_description
        )
        
        if pr:
            return pr["html_url"]
        else:
            return None
    
    def smart_workflow(
        self,
        repo_path: str,
        original_repo_url: str,
        agent_name: str,
        agent_execution_report_summary: Optional[str] = None
    ) -> Optional[str]:
        """
        Smart workflow that handles permissions automatically:
        - If we have push permissions: work directly on original repo
        - If we don't have push permissions: fork, work on fork, create cross-repo PR
        
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
        print("INFO: Checking repository permissions...")
        has_push_permissions = self.check_push_permissions(original_repo_url)
        
        if has_push_permissions:
            print("SUCCESS: Have push permissions, working directly on original repository")
            return self.full_workflow(repo_path, original_repo_url, agent_name, agent_execution_report_summary)
        else:
            print("INFO: No push permissions, using fork workflow...")
            return self.fork_workflow(repo_path, original_repo_url, agent_name, agent_execution_report_summary)
    
    def fork_workflow(
        self,
        repo_path: str,
        original_repo_url: str,
        agent_name: str,
        agent_execution_report_summary: Optional[str] = None
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
        
        # Step 5: Generate commit message and PR content using Claude (single API call)
        if agent_execution_report_summary:
            content = self.generate_commit_and_pr_content_with_claude(agent_execution_report_summary, agent_name)
            commit_message = content["commit_message"]
            pr_title, pr_description = self.generate_pr_description(
                agent_name,
                content["pr_title"],
                content["pr_description"],
                content["pr_changes_summary"]
            )
        else:
            # Use default formats when no agent output is provided
            default_content = self._generate_default_commit_and_pr_content(agent_name)
            commit_message = default_content["commit_message"]
            pr_title, pr_description = self.generate_pr_description(
                agent_name,
                default_content["pr_title"],
                default_content["pr_description"],
                default_content["pr_changes_summary"]
            )
        
        if not self.commit_changes(repo_path, commit_message):
            return None
        
        # Step 6: Push to fork
        if not self.push_branch(repo_path, branch_name, fork_git_url):
            return None
        
        # Step 7: Create cross-repository pull request
        pr = self.create_pull_request(
            repo_url=original_repo_url,  # Target: original repo
            branch_name=branch_name,
            title=pr_title,
            description=pr_description,
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