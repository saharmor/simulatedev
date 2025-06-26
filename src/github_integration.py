#!/usr/bin/env python3
"""
GitHub Integration for SimulateDev

This module handles GitHub API operations including:
- Creating pull requests
- Pushing changes to branches
- Managing repository operations
- Checking permissions and forking when needed
- Processing GitHub PRs and issues
"""

import os
import subprocess
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class GitHubPRProcessor:
    """Processes GitHub pull requests and converts them to SimulateDev tasks"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            print("WARNING: No GitHub token found. PR fetching may be limited.")
        
        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        } if self.github_token else {}
        
        self.github_integration = GitHubIntegration(self.github_token)
    
    def parse_pr_url(self, pr_url: str) -> Dict[str, Any]:
        """Parse GitHub PR URL to extract owner, repo, and PR number"""
        # Handle different URL formats
        # https://github.com/owner/repo/pull/123
        # github.com/owner/repo/pull/123
        
        # Clean up the URL
        if not pr_url.startswith(('http://', 'https://')):
            pr_url = 'https://' + pr_url
        
        parsed = urlparse(pr_url)
        if parsed.netloc != 'github.com':
            raise ValueError(f"Invalid GitHub URL: {pr_url}")
        
        # Parse path: /owner/repo/pull/123
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) != 4 or path_parts[2] != 'pull':
            raise ValueError(f"Invalid GitHub PR URL format: {pr_url}")
        
        try:
            pr_number = int(path_parts[3])
        except ValueError:
            raise ValueError(f"Invalid PR number in URL: {pr_url}")
        
        return {
            'owner': path_parts[0],
            'repo': path_parts[1],
            'pr_number': pr_number,
            'repo_url': f"https://github.com/{path_parts[0]}/{path_parts[1]}"
        }
    
    def fetch_pr_data(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Fetch PR data from GitHub API"""
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        
        try:
            response = requests.get(api_url, headers=self.headers)
            
            if response.status_code == 404:
                raise ValueError(f"PR #{pr_number} not found in {owner}/{repo}")
            elif response.status_code != 200:
                raise ValueError(f"Failed to fetch PR: HTTP {response.status_code}")
            
            pr_data = response.json()
            
            # Also fetch PR comments
            comments_url = pr_data.get('comments_url', '')
            comments = []
            if comments_url:
                comments_response = requests.get(comments_url, headers=self.headers)
                if comments_response.status_code == 200:
                    comments = comments_response.json()
            
            # Fetch review comments
            review_comments_url = pr_data.get('review_comments_url', '')
            review_comments = []
            if review_comments_url:
                review_comments_response = requests.get(review_comments_url, headers=self.headers)
                if review_comments_response.status_code == 200:
                    review_comments = review_comments_response.json()
            
            # Fetch PR reviews
            reviews_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
            reviews = []
            if self.headers:
                reviews_response = requests.get(reviews_url, headers=self.headers)
                if reviews_response.status_code == 200:
                    reviews = reviews_response.json()
            
            pr_data['comments_data'] = comments
            pr_data['review_comments_data'] = review_comments
            pr_data['reviews_data'] = reviews
            return pr_data
            
        except requests.RequestException as e:
            raise ValueError(f"Error fetching PR data: {str(e)}")
    
    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetch the PR diff"""
        diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        
        try:
            # Request diff format
            headers = self.headers.copy() if self.headers else {}
            headers['Accept'] = 'application/vnd.github.v3.diff'
            
            response = requests.get(diff_url, headers=headers)
            
            if response.status_code == 200:
                return response.text
            else:
                print(f"WARNING: Could not fetch PR diff: HTTP {response.status_code}")
                return ""
                
        except requests.RequestException as e:
            print(f"WARNING: Error fetching PR diff: {str(e)}")
            return ""
    
    def synthesize_pr_task_prompt(self, pr_data: Dict[str, Any], repo_info: Dict[str, Any], 
                                  custom_task: str, pr_diff: str = "") -> str:
        """Convert GitHub PR data and custom task into a SimulateDev task prompt"""
        
        title = pr_data.get('title', 'Untitled PR')
        body = pr_data.get('body', '')
        pr_number = pr_data.get('number', 'Unknown')
        pr_url = pr_data.get('html_url', '')
        state = pr_data.get('state', 'unknown')
        head_branch = pr_data.get('head', {}).get('ref', 'unknown')
        base_branch = pr_data.get('base', {}).get('ref', 'main')
        
        # Process comments
        comments = pr_data.get('comments_data', [])
        review_comments = pr_data.get('review_comments_data', [])
        reviews = pr_data.get('reviews_data', [])
        
        discussion_text = ""
        if comments or review_comments or reviews:
            discussion_text = "\n\n## PR Discussion:\n"
            
            # Regular comments
            if comments:
                discussion_text += "\n### General Comments:\n"
                for i, comment in enumerate(comments[:10], 1):  # Limit to first 10 comments
                    author = comment.get('user', {}).get('login', 'Unknown')
                    comment_body = comment.get('body', '')
                    if comment_body.strip():
                        discussion_text += f"\n**Comment {i} by @{author}:**\n{comment_body}\n"
            
            # Review comments (inline code comments)
            if review_comments:
                discussion_text += "\n### Code Review Comments:\n"
                for i, comment in enumerate(review_comments[:10], 1):
                    author = comment.get('user', {}).get('login', 'Unknown')
                    comment_body = comment.get('body', '')
                    file_path = comment.get('path', 'unknown file')
                    if comment_body.strip():
                        discussion_text += f"\n**Review Comment {i} by @{author} on {file_path}:**\n{comment_body}\n"
            
            # PR reviews
            if reviews:
                discussion_text += "\n### PR Reviews:\n"
                for i, review in enumerate(reviews[:5], 1):
                    author = review.get('user', {}).get('login', 'Unknown')
                    review_state = review.get('state', 'COMMENTED')
                    review_body = review.get('body', '')
                    if review_body and review_body.strip():
                        discussion_text += f"\n**Review {i} by @{author} ({review_state}):**\n{review_body}\n"
        
        # Include diff if available (truncated for readability)
        diff_section = ""
        if pr_diff:
            # Truncate diff if too long
            max_diff_length = 5000
            if len(pr_diff) > max_diff_length:
                diff_section = f"\n\n## PR Changes (Diff - First {max_diff_length} characters):\n```diff\n{pr_diff[:max_diff_length]}\n... (truncated)\n```"
            else:
                diff_section = f"\n\n## PR Changes (Diff):\n```diff\n{pr_diff}\n```"
        
        task_prompt = f"""# GitHub Pull Request Task

## PR Information
- **Repository**: {repo_info['repo_url']}
- **PR**: #{pr_number} - {title}
- **URL**: {pr_url}
- **State**: {state}
- **Head Branch**: {head_branch}
- **Base Branch**: {base_branch}

## PR Description
{body}
{discussion_text}
{diff_section}

## Custom Task
{custom_task}

## Task Instructions

Based on the pull request above and the custom task, please:

1. **Understand the PR Context**: Review the PR description, changes, and any discussion to understand what this PR is trying to accomplish.

2. **Analyze Current Changes**: Examine the diff and current implementation to understand what has been done so far.

3. **Execute Custom Task**: Focus on the specific task requested:
   {custom_task}

4. **Implement Improvements**: 
   - Make the requested changes or improvements
   - Follow the project's coding standards and patterns
   - Ensure your changes work well with the existing PR changes
   - Add appropriate error handling where needed

5. **Test Your Changes**: 
   - Verify that your modifications work as expected
   - Test interaction with existing PR changes
   - Ensure no existing functionality is broken

6. **Document Your Work**:
   - Add or update comments in the code where necessary
   - Update documentation if your changes affect user-facing functionality
   - Provide clear explanation of what was changed and why

## Success Criteria
- The custom task is completed successfully
- Changes integrate well with the existing PR
- No existing functionality is broken
- Code follows project conventions
- Changes are well-tested and documented

## Working Branch
You are working on branch `{head_branch}`. Any changes you make will be committed to this branch.

Please implement the requested changes while respecting the existing work in this pull request.
"""
        
        return task_prompt
    
    def clone_pr_branch(self, repo_url: str, head_branch: str, target_dir: str) -> str:
        """Clone the repository and checkout the PR branch"""
        try:
            # Parse repo info for cloning
            repo_info = self.github_integration.parse_repo_info(repo_url)
            
            print(f"Cloning repository and checking out branch '{head_branch}'...")
            
            # Clone the repository
            subprocess.run([
                "git", "clone", repo_url, target_dir
            ], check=True, capture_output=True)
            
            # Checkout the PR branch
            subprocess.run([
                "git", "checkout", head_branch
            ], cwd=target_dir, check=True, capture_output=True)
            
            print(f"Successfully cloned and checked out branch '{head_branch}'")
            return target_dir
            
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to clone repository or checkout branch: {e}")
    
    def check_for_changes(self, repo_path: str) -> bool:
        """Check if there are any uncommitted changes in the repository"""
        try:
            result = subprocess.run([
                "git", "status", "--porcelain"
            ], cwd=repo_path, capture_output=True, text=True, check=True)
            
            # If there's any output, there are changes
            return bool(result.stdout.strip())
            
        except subprocess.CalledProcessError:
            return False
    
    def commit_and_push_changes(self, repo_path: str, branch_name: str, task_description: str) -> bool:
        """Commit and push changes to the PR branch"""
        try:
            # Configure git user if needed
            self.github_integration.setup_git_config(repo_path)
            
            # Add all changes
            subprocess.run([
                "git", "add", "."
            ], cwd=repo_path, check=True)
            
            # Create commit message
            commit_message = f"SimulateDev: {task_description[:100]}{'...' if len(task_description) > 100 else ''}"
            
            # Commit changes
            subprocess.run([
                "git", "commit", "-m", commit_message
            ], cwd=repo_path, check=True)
            
            # Push to the branch
            subprocess.run([
                "git", "push", "origin", branch_name
            ], cwd=repo_path, check=True)
            
            print(f"✅ Changes committed and pushed to branch '{branch_name}'")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to commit and push changes: {e}")
            return False

    def analyze_pr_comments_and_generate_task(self, pr_data: Dict[str, Any]) -> str:
        """Analyze PR comments and generate a comprehensive task to address them"""
        
        comments = pr_data.get('comments_data', [])
        review_comments = pr_data.get('review_comments_data', [])
        reviews = pr_data.get('reviews_data', [])
        
        if not comments and not review_comments and not reviews:
            return "No comments or reviews found on this PR to address."
        
        # Categorize and analyze comments
        actionable_comments = []
        code_review_comments = []
        general_feedback = []
        
        # Process general comments
        for comment in comments:
            comment_body = comment.get('body', '').strip()
            author = comment.get('user', {}).get('login', 'Unknown')
            if comment_body and not comment_body.lower().startswith(('lgtm', 'looks good', '👍', ':+1:')):
                general_feedback.append({
                    'author': author,
                    'body': comment_body,
                    'type': 'general'
                })
        
        # Process review comments (inline code comments)
        for comment in review_comments:
            comment_body = comment.get('body', '').strip()
            author = comment.get('user', {}).get('login', 'Unknown')
            file_path = comment.get('path', 'unknown file')
            line_number = comment.get('line') or comment.get('original_line')
            
            if comment_body:
                code_review_comments.append({
                    'author': author,
                    'body': comment_body,
                    'file': file_path,
                    'line': line_number,
                    'type': 'code_review'
                })
        
        # Process PR reviews
        for review in reviews:
            review_body = review.get('body', '').strip()
            author = review.get('user', {}).get('login', 'Unknown')
            review_state = review.get('state', 'COMMENTED')
            
            if review_body and review_state in ['CHANGES_REQUESTED', 'COMMENTED']:
                actionable_comments.append({
                    'author': author,
                    'body': review_body,
                    'state': review_state,
                    'type': 'review'
                })
        
        # Generate comprehensive task
        task_parts = []
        
        task_parts.append("# PR Review Comments Analysis and Resolution")
        task_parts.append("\nThis task involves addressing all the feedback and comments received on this pull request.")
        
        if actionable_comments:
            task_parts.append("\n## PR Reviews to Address:")
            for i, comment in enumerate(actionable_comments, 1):
                state_emoji = "🔴" if comment['state'] == 'CHANGES_REQUESTED' else "💬"
                task_parts.append(f"\n### {state_emoji} Review {i} by @{comment['author']} ({comment['state']}):")
                task_parts.append(f"{comment['body']}")
        
        if code_review_comments:
            task_parts.append("\n## Code Review Comments to Address:")
            for i, comment in enumerate(code_review_comments, 1):
                line_info = f" (line {comment['line']})" if comment['line'] else ""
                task_parts.append(f"\n### 📝 Comment {i} by @{comment['author']} on `{comment['file']}`{line_info}:")
                task_parts.append(f"{comment['body']}")
        
        if general_feedback:
            task_parts.append("\n## General Feedback to Consider:")
            for i, comment in enumerate(general_feedback, 1):
                task_parts.append(f"\n### 💡 Feedback {i} by @{comment['author']}:")
                task_parts.append(f"{comment['body']}")
        
        # Add implementation instructions
        task_parts.append("\n## Implementation Instructions:")
        task_parts.append("\nPlease address each of the above comments and feedback by:")
        task_parts.append("\n1. **Carefully reading and understanding each comment**")
        task_parts.append("   - Identify what changes are being requested")
        task_parts.append("   - Understand the reasoning behind each suggestion")
        task_parts.append("   - Prioritize changes requested vs. suggestions")
        
        task_parts.append("\n2. **Implementing the requested changes**")
        task_parts.append("   - Make code modifications as requested in review comments")
        task_parts.append("   - Address any bugs or issues pointed out")
        task_parts.append("   - Improve code quality based on feedback")
        task_parts.append("   - Add missing functionality or tests as requested")
        
        task_parts.append("\n3. **Following best practices**")
        task_parts.append("   - Maintain consistent code style with the project")
        task_parts.append("   - Add appropriate error handling where suggested")
        task_parts.append("   - Update documentation if changes affect public APIs")
        task_parts.append("   - Ensure backward compatibility unless breaking changes are explicitly requested")
        
        task_parts.append("\n4. **Testing your changes**")
        task_parts.append("   - Verify that all requested changes work as expected")
        task_parts.append("   - Test edge cases mentioned in the reviews")
        task_parts.append("   - Ensure existing functionality still works")
        
        task_parts.append("\n## Success Criteria:")
        task_parts.append("- All review comments have been addressed appropriately")
        task_parts.append("- Code changes resolve the issues raised without introducing new problems")
        task_parts.append("- The implementation follows the project's coding standards")
        task_parts.append("- Changes are well-tested and documented")
        
        # Count total items to address
        total_items = len(actionable_comments) + len(code_review_comments) + len(general_feedback)
        task_parts.append(f"\n**Total items to address: {total_items}**")
        
        return "\n".join(task_parts)

    def generate_review_response_commit_message(self, pr_data: Dict[str, Any]) -> str:
        """Generate a descriptive commit message for addressing PR review comments"""
        
        comments = pr_data.get('comments_data', [])
        review_comments = pr_data.get('review_comments_data', [])
        reviews = pr_data.get('reviews_data', [])
        
        # Count different types of feedback
        review_count = len([r for r in reviews if r.get('body', '').strip()])
        code_comment_count = len(review_comments)
        general_comment_count = len([c for c in comments if c.get('body', '').strip()])
        
        total_items = review_count + code_comment_count + general_comment_count
        
        # Generate descriptive message
        if total_items == 0:
            return "Address PR feedback"
        
        message_parts = []
        if review_count > 0:
            message_parts.append(f"{review_count} review{'s' if review_count != 1 else ''}")
        if code_comment_count > 0:
            message_parts.append(f"{code_comment_count} code comment{'s' if code_comment_count != 1 else ''}")
        if general_comment_count > 0:
            message_parts.append(f"{general_comment_count} general comment{'s' if general_comment_count != 1 else ''}")
        
        if len(message_parts) == 1:
            return f"Address {message_parts[0]} from PR review"
        elif len(message_parts) == 2:
            return f"Address {message_parts[0]} and {message_parts[1]} from PR review"
        else:
            return f"Address {', '.join(message_parts[:-1])}, and {message_parts[-1]} from PR review"

    def commit_and_push_review_changes(self, repo_path: str, branch_name: str, pr_data: Dict[str, Any]) -> bool:
        """Commit and push changes specifically for addressing PR review comments"""
        try:
            # Configure git user if needed
            self.github_integration.setup_git_config(repo_path)
            
            # Add all changes
            subprocess.run([
                "git", "add", "."
            ], cwd=repo_path, check=True)
            
            # Generate descriptive commit message
            commit_message = self.generate_review_response_commit_message(pr_data)
            
            # Commit changes
            subprocess.run([
                "git", "commit", "-m", commit_message
            ], cwd=repo_path, check=True)
            
            # Push to the branch
            subprocess.run([
                "git", "push", "origin", branch_name
            ], cwd=repo_path, check=True)
            
            print(f"✅ Changes committed and pushed to branch '{branch_name}'")
            print(f"📝 Commit message: {commit_message}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to commit and push changes: {e}")
            return False


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
        
        # Track the last pushed branch name (for handling conflicts)
        self._last_pushed_branch = None
    
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
    
    def get_authenticated_user_info(self) -> Optional[Dict[str, Any]]:
        """Get the authenticated user's full information including name and email"""
        if not self.github_token:
            return None
        
        try:
            # Get basic user info
            user_response = requests.get(
                "https://api.github.com/user",
                headers=self.base_headers
            )
            
            if user_response.status_code != 200:
                print(f"ERROR: Failed to get user info: {user_response.status_code}")
                return None
            
            user_data = user_response.json()
            
            # Get user emails to find primary email
            emails_response = requests.get(
                "https://api.github.com/user/emails",
                headers=self.base_headers
            )
            
            primary_email = None
            if emails_response.status_code == 200:
                emails = emails_response.json()
                # Find primary email
                for email_info in emails:
                    if email_info.get("primary", False):
                        primary_email = email_info.get("email")
                        break
                # Fallback to first email if no primary found
                if not primary_email and emails:
                    primary_email = emails[0].get("email")
            
            # Get the name, but be smart about fallbacks
            github_name = user_data.get("name")
            github_login = user_data.get("login")
            
            # Use login (username) if:
            # 1. No name is set (None or empty string)
            # 2. Name is a generic placeholder like "Your Name"
            # 3. Name is the same as login (redundant)
            if (not github_name or 
                github_name.strip() == "" or 
                github_name.lower() in ["your name", "user", "username"] or
                github_name == github_login):
                display_name = github_login
            else:
                display_name = github_name
            
            return {
                "login": github_login,
                "name": display_name,
                "email": primary_email or f"{github_login}@users.noreply.github.com"
            }
            
        except Exception as e:
            print(f"ERROR: Error getting user info: {str(e)}")
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
            # Check if user has explicitly set git config in environment
            env_git_name = os.getenv("GIT_USER_NAME")
            env_git_email = os.getenv("GIT_USER_EMAIL")
            
            if env_git_name and env_git_email:
                # User has explicitly provided both name and email - respect their choice
                git_name = env_git_name
                git_email = env_git_email
                print(f"INFO: Using user-provided git config - Name: {git_name}, Email: {git_email}")
            else:
                # Try to auto-detect from GitHub API
                user_info = self.get_authenticated_user_info()
                
                if user_info:
                    # Use GitHub info for missing values, env vars for provided ones
                    git_name = env_git_name or user_info["name"]
                    git_email = env_git_email or user_info["email"]
                    print(f"INFO: Using GitHub user info - Name: {git_name}, Email: {git_email}")
                else:
                    # Fallback to defaults for missing values
                    git_name = env_git_name or "SimulateDev Bot"
                    git_email = env_git_email or "simulatedev@example.com"
                    print(f"INFO: Using fallback git config - Name: {git_name}, Email: {git_email}")
            
            # Set up git user
            subprocess.run(
                ["git", "config", "user.name", git_name],
                cwd=repo_path,
                check=True
            )
            subprocess.run(
                ["git", "config", "user.email", git_email],
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
            print(f"SUCCESS: Committed changes")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to commit changes: {e.stderr.decode()}")
            return False
    
    def push_branch(self, repo_path: str, branch_name: str, repo_url: str) -> bool:
        """Push branch to remote repository with conflict resolution"""
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
            
            # Try to push the branch
            try:
                subprocess.run(
                    ["git", "push", "-u", "origin", branch_name],
                    cwd=repo_path,
                    check=True,
                    capture_output=True
                )
                print(f"SUCCESS: Pushed branch {branch_name} to remote")
                return True
                
            except subprocess.CalledProcessError as push_error:
                error_output = push_error.stderr.decode()
                
                # Check if it's a non-fast-forward error
                if "non-fast-forward" in error_output or "rejected" in error_output:
                    print(f"INFO: Branch {branch_name} has conflicts with remote. Attempting to resolve...")
                    
                    # Try to fetch and merge remote changes
                    try:
                        # Fetch the latest changes
                        subprocess.run(
                            ["git", "fetch", "origin", branch_name],
                            cwd=repo_path,
                            check=True,
                            capture_output=True
                        )
                        
                        # Try to merge the remote changes
                        subprocess.run(
                            ["git", "merge", f"origin/{branch_name}"],
                            cwd=repo_path,
                            check=True,
                            capture_output=True
                        )
                        
                        # Try pushing again after merge
                        subprocess.run(
                            ["git", "push", "-u", "origin", branch_name],
                            cwd=repo_path,
                            check=True,
                            capture_output=True
                        )
                        print(f"SUCCESS: Resolved conflicts and pushed branch {branch_name} to remote")
                        return True
                        
                    except subprocess.CalledProcessError:
                        # If merge fails, create a new unique branch name
                        print(f"INFO: Cannot merge conflicts automatically. Creating new unique branch...")
                        return self._create_and_push_unique_branch(repo_path, branch_name, repo_url)
                else:
                    # Re-raise for other types of push errors
                    raise push_error
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to push branch {branch_name}: {e.stderr.decode()}")
            return False
    
    def _create_and_push_unique_branch(self, repo_path: str, original_branch_name: str, repo_url: str) -> bool:
        """Create a new unique branch name and push it"""
        from datetime import datetime
        
        # Generate a unique branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_branch_name = f"{original_branch_name}_{timestamp}"
        
        try:
            # Create and checkout the new unique branch
            subprocess.run(
                ["git", "checkout", "-b", unique_branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            
            # Push the new unique branch
            subprocess.run(
                ["git", "push", "-u", "origin", unique_branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True
            )
            
            print(f"SUCCESS: Created and pushed unique branch {unique_branch_name} to remote")
            
            # Update the branch name in the class for PR creation
            # We need to return the new branch name somehow - let's store it as an instance variable
            self._last_pushed_branch = unique_branch_name
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create and push unique branch: {e.stderr.decode()}")
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
            
            # Validate that head_ref is not None or empty
            if not head_ref:
                print(f"ERROR: Invalid branch name: {branch_name}")
                return None
            
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
                return pr_data
            elif response.status_code == 422:
                # Handle validation errors - only try 'main' as fallback if not already tried
                print(f"WARNING: PR creation failed with validation error: {response.text}")
                
                if base_branch != "main":
                    print(f"INFO: Trying base branch: main")
                    pr_data["base"] = "main"
                    
                    retry_response = requests.post(
                        url,
                        json=pr_data,
                        headers=self.base_headers
                    )
                    
                    if retry_response.status_code == 201:
                        pr_data = retry_response.json()
                        return pr_data
                    else:
                        print(f"ERROR: Failed to create PR with 'main' base branch: {retry_response.status_code} - {retry_response.text}")
                else:
                    print(f"ERROR: Already tried 'main' as base branch")
                
                print(f"ERROR: Failed to create PR: {response.status_code} - {response.text}")
                return None
            else:
                print(f"ERROR: Failed to create PR: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"ERROR: Error creating pull request: {str(e)}")
            return None
    
    def generate_commit_and_pr_content_with_claude(self, agent_execution_report_summary: str, workflow_name: str, coding_ides_info: Optional[str] = None, execution_time_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        Use Claude to generate both commit message and PR content in a single API call
        
        Args:
            agent_execution_report_summary: The summary/output from the coding agent
            workflow_name: Name of the workflow used (preset workflow name or task description for custom coding)
            coding_ides_info: Optional information about coding IDEs used (roles, models, etc.)
            execution_time_seconds: Optional execution time in seconds
            
        Returns:
            Dict with 'commit_message', 'pr_title', 'pr_description', 'pr_changes_summary', and 'branch_name' keys
        """
        try:
            # Use the shared Claude client
            from utils.llm_client import generate_commit_and_pr_content_with_llm
            return generate_commit_and_pr_content_with_llm(agent_execution_report_summary, workflow_name, coding_ides_info, execution_time_seconds)
                
        except Exception as e:
            print(f"WARNING: Error calling Claude for content generation: {str(e)}")
            return self._generate_default_commit_and_pr_content(workflow_name)
    
    def _generate_default_commit_and_pr_content(self, workflow_name: str) -> Dict[str, Any]:
        """Generate default commit message and PR content when Claude processing fails"""
        from datetime import datetime
        
        # Generate default branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_workflow_name = workflow_name.replace(" ", "-").replace("(", "").replace(")", "").replace("_", "-").lower()
        default_branch_name = f"simulatedev/{sanitized_workflow_name}_{timestamp}"
        
        return {
            "commit_message": f"SimulateDev: {workflow_name}",
            "pr_title": f"[SimulateDev] {workflow_name[:50]}{'...' if len(workflow_name) > 50 else ''}",
            "pr_description": f"Automated changes generated by SimulateDev workflow.",
            "pr_changes_summary": f"Changes implemented according to the workflow: \"{workflow_name}\"",
            "branch_name": default_branch_name,
            "concise_task_description": workflow_name
        }

    def generate_pr_description(self, workflow_name: str, pr_title: str, pr_description: str, pr_changes_summary: str, coding_ides_info: Optional[str] = None, concise_task_description: Optional[str] = None, execution_time_seconds: Optional[float] = None) -> tuple[str, str]:
        """
        Generate formatted PR title and description
        
        Args:
            workflow_name: Name of the workflow used (preset workflow name or task description for custom coding)
            pr_title: PR title from Claude or default
            pr_description: PR description from Claude or default
            pr_changes_summary: Changes summary from Claude or default
            coding_ides_info: Optional information about coding IDEs used
            execution_time_seconds: Optional execution time in seconds
            
        Returns:
            tuple[str, str]: (pr_title, formatted_pr_description)
        """
        # Build the formatted description with the new format
        description_parts = [
            "# Automated Changes by [SimulateDev](https://github.com/saharmor/simulatedev)",
            "",
            "## Setup"
        ]
        
        # Add task description as subheader
        description_parts.append("### Task")
        if concise_task_description:
            description_parts.append(concise_task_description)
        else:
            description_parts.append(workflow_name)
        
        description_parts.append("")
        
        # Add coding agents information as subheader with numbered list
        description_parts.append("### Coding agents used")
        if coding_ides_info:
            # Split the coding_ides_info by comma and create numbered list
            agents = [agent.strip() for agent in coding_ides_info.split(',')]
            for i, agent in enumerate(agents, 1):
                description_parts.append(f"{i}. {agent}")
        else:
            description_parts.append("1. Not specified")
        
        description_parts.append("")
        
        # Add execution time information
        description_parts.append("### Execution time")
        if execution_time_seconds is not None:
            if execution_time_seconds < 60:
                time_str = f"{execution_time_seconds:.1f} seconds"
            else:
                minutes = int(execution_time_seconds // 60)
                seconds = execution_time_seconds % 60
                time_str = f"{minutes}m {seconds:.1f}s"
            description_parts.append(f"⏱️ {time_str}")
        else:
            description_parts.append("Execution time data not available")
        
        description_parts.extend([
            "",
            "---",
            "",
            "## Summary",
            pr_description,
            "",
            "## What changed?",
            pr_changes_summary,
            "",
            "## Review Instructions",
            "Please carefully review all changes before merging. While AI agents are powerful, human oversight is always recommended.",
            "",
            "---",
            "*Generated by [SimulateDev](https://github.com/saharmor/simulatedev), the AI coding agents collaboration platform.*"
        ])
        
        formatted_pr_description = "\n".join(description_parts)
        
        return pr_title, formatted_pr_description.strip()

    def full_workflow(
        self,
        repo_path: str,
        repo_url: str,
        workflow_name: str,
        agent_execution_report_summary: Optional[str] = None,
        coding_ides_info: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
    ) -> Optional[str]:
        """
        Complete workflow: create branch, commit changes, push, and create PR
        
        Args:
            agent_execution_report_summary: Optional summary/output from the coding agent for better content generation
            coding_ides_info: Optional information about coding IDEs used (roles, models, etc.)
            execution_time_seconds: Optional execution time in seconds
        
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
        # Setup git config
        if not self.setup_git_config(repo_path):
            return None
        
        # Generate commit message and PR content using Claude (single API call)
        if agent_execution_report_summary:
            content = self.generate_commit_and_pr_content_with_claude(agent_execution_report_summary, workflow_name, coding_ides_info, execution_time_seconds)
            commit_message = content["commit_message"]
            branch_name = content["branch_name"]
            pr_title, pr_description = self.generate_pr_description(
                workflow_name,
                content["pr_title"],
                content["pr_description"],
                content["pr_changes_summary"],
                coding_ides_info,
                content['concise_task_description'],
                execution_time_seconds
            )
        else:
            # Use default formats when no agent output is provided
            default_content = self._generate_default_commit_and_pr_content(workflow_name)
            commit_message = default_content["commit_message"]
            branch_name = default_content["branch_name"]
            pr_title, pr_description = self.generate_pr_description(
                workflow_name,
                default_content["pr_title"],
                default_content["pr_description"],
                default_content["pr_changes_summary"],
                coding_ides_info,
                default_content['concise_task_description'],
                execution_time_seconds
            )
        
        # Create branch
        if not self.create_branch(repo_path, branch_name):
            return None
        
        if not self.commit_changes(repo_path, commit_message):
            return None
        
        # Push branch - this may create a unique branch name if conflicts occur
        self._last_pushed_branch = None  # Reset before push
        if not self.push_branch(repo_path, branch_name, repo_url):
            return None
        
        # Use the actual pushed branch name (may be different if conflicts were resolved)
        final_branch_name = self._last_pushed_branch if self._last_pushed_branch else branch_name
        
        pr = self.create_pull_request(
            repo_url=repo_url,
            branch_name=final_branch_name,
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
        workflow_name: str,
        agent_execution_report_summary: Optional[str] = None,
        coding_ides_info: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
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
            return self.full_workflow(repo_path, original_repo_url, workflow_name, agent_execution_report_summary, coding_ides_info, execution_time_seconds)
        else:
            print("INFO: No push permissions, using fork workflow...")
            return self.fork_workflow(repo_path, original_repo_url, workflow_name, agent_execution_report_summary, coding_ides_info, execution_time_seconds)
    
    def fork_workflow(
        self,
        repo_path: str,
        original_repo_url: str,
        workflow_name: str,
        agent_execution_report_summary: Optional[str] = None,
        coding_ides_info: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
    ) -> Optional[str]:
        """
        Fork-based workflow for repositories where we don't have push permissions
        
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
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
        
        # Step 4: Generate commit message and PR content using Claude (single API call)
        if agent_execution_report_summary:
            content = self.generate_commit_and_pr_content_with_claude(agent_execution_report_summary, workflow_name, coding_ides_info, execution_time_seconds)
            commit_message = content["commit_message"]
            branch_name = content["branch_name"]
            pr_title, pr_description = self.generate_pr_description(
                workflow_name,
                content["pr_title"],
                content["pr_description"],
                content["pr_changes_summary"],
                coding_ides_info,
                content['concise_task_description'],
                execution_time_seconds
            )
        else:
            # Use default formats when no agent output is provided
            default_content = self._generate_default_commit_and_pr_content(workflow_name)
            commit_message = default_content["commit_message"]
            branch_name = default_content["branch_name"]
            pr_title, pr_description = self.generate_pr_description(
                workflow_name,
                default_content["pr_title"],
                default_content["pr_description"],
                default_content["pr_changes_summary"],
                coding_ides_info,
                default_content['concise_task_description'],
                execution_time_seconds
            )
        
        # Step 5: Create branch
        if not self.create_branch(repo_path, branch_name):
            return None
        
        if not self.commit_changes(repo_path, commit_message):
            return None
        
        # Step 6: Push to fork - this may create a unique branch name if conflicts occur
        self._last_pushed_branch = None  # Reset before push
        if not self.push_branch(repo_path, branch_name, fork_git_url):
            return None
        
        # Use the actual pushed branch name (may be different if conflicts were resolved)
        final_branch_name = self._last_pushed_branch if self._last_pushed_branch else branch_name
        
        # Step 7: Create cross-repository pull request
        pr = self.create_pull_request(
            repo_url=original_repo_url,  # Target: original repo
            branch_name=final_branch_name,
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
        
        # Test getting full user info
        print("\nTesting user info retrieval...")
        user_info = integration.get_authenticated_user_info()
        if user_info:
            print(f"SUCCESS: User info retrieved:")
            print(f"  Login: {user_info['login']}")
            print(f"  Name: {user_info['name']}")
            print(f"  Email: {user_info['email']}")
            
            # Demonstrate git config behavior
            print(f"\nGit Config Behavior Examples:")
            print(f"1. No env vars set → Uses GitHub: {user_info['name']} <{user_info['email']}>")
            print(f"2. Both env vars set → Uses env vars (overrides GitHub)")
            print(f"3. Only GIT_USER_NAME set → Uses custom name + GitHub email")
            print(f"4. Only GIT_USER_EMAIL set → Uses GitHub name + custom email")
        else:
            print("WARNING: Could not retrieve user info")
    else:
        print("WARNING: Not authenticated or no token provided")
        print("Git config will use environment variables or defaults")
    
    # Test parsing repo URL
    test_repo_url = "https://github.com/octocat/Hello-World"
    print(f"\nTesting repo URL parsing: {test_repo_url}")
    repo_info = integration.parse_repo_info(test_repo_url)
    print(f"Parsed repo info: {repo_info}")
    
    # Test permission checking
    print(f"\nTesting permission checking for: {test_repo_url}")
    has_permissions = integration.check_push_permissions(test_repo_url)
    print(f"Push permissions: {has_permissions}")


def run_github_preflight_check(repo_url: str, create_pr: bool = True) -> bool:
    """
    Run a comprehensive GitHub preflight check before executing coding agents.
    
    This function tests:
    1. GitHub token authentication
    2. User info retrieval 
    3. Repository access and permissions
    4. Fork capability (if needed)
    5. Basic API connectivity
    
    Args:
        repo_url: The GitHub repository URL to test
        create_pr: Whether PR creation will be attempted (affects permission checks)
    
    Returns:
        bool: True if all checks pass, False if any critical check fails
    """
    integration = GitHubIntegration()
    all_checks_passed = True
    
    # Check 1: GitHub token authentication
    try:
        username = integration.get_authenticated_user()
        if not username:
            print("❌ GitHub authentication failed - check your GITHUB_TOKEN environment variable")
            all_checks_passed = False
    except Exception as e:
        print(f"❌ GitHub authentication error: {str(e)}")
        all_checks_passed = False
    
    # Check 2: Repository URL parsing
    try:
        repo_info = integration.parse_repo_info(repo_url)
    except Exception as e:
        print(f"❌ Invalid repository URL: {str(e)}")
        all_checks_passed = False
    
    # Check 3: Repository access and permissions (only if PR creation is enabled)
    if create_pr:
        try:
            has_push_permissions = integration.check_push_permissions(repo_url)
            # Just test access, don't print success messages - only errors
        except Exception as e:
            print(f"❌ Repository permission check failed: {str(e)}")
            all_checks_passed = False
    
    # Check 4: Basic API connectivity
    try:
        import requests
        headers = integration.base_headers if hasattr(integration, 'base_headers') else {}
        response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        
        if response.status_code == 401:
            print("❌ GitHub API authentication failed - check your GITHUB_TOKEN permissions")
            all_checks_passed = False
        elif response.status_code == 403:
            print("⚠️  GitHub API rate limited - execution may be slower")
        elif response.status_code != 200:
            print(f"⚠️  GitHub API connectivity issues (HTTP {response.status_code})")
    except requests.exceptions.Timeout:
        print("❌ GitHub API request timed out - check your internet connection")
        all_checks_passed = False
    except Exception as e:
        print(f"❌ GitHub API connectivity test failed: {str(e)}")
        all_checks_passed = False
    
    return all_checks_passed


if __name__ == "__main__":
    test_github_integration() 