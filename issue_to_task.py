#!/usr/bin/env python3
"""
Issue to Task Script for SimulateDev

This script reads a GitHub issue URL, synthesizes the conversation into a custom task prompt,
and runs SimulateDev to create a PR addressing the issue.

Usage:
    python issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 --agent cursor
    python issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'
"""

import argparse
import asyncio
import os
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Import SimulateDev modules
from simulatedev import execute_task, validate_coding_agents_json, create_default_coder_agent
from agents import CodingAgentIdeType

# Load environment variables
load_dotenv()


class GitHubIssueProcessor:
    """Processes GitHub issues and converts them to SimulateDev tasks"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            print("WARNING: No GitHub token found. Issue fetching may be limited.")
        
        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        } if self.github_token else {}
    
    def parse_issue_url(self, issue_url: str) -> Dict[str, Any]:
        """Parse GitHub issue URL to extract owner, repo, and issue number"""
        # Handle different URL formats
        # https://github.com/owner/repo/issues/123
        # github.com/owner/repo/issues/123
        
        # Clean up the URL
        if not issue_url.startswith(('http://', 'https://')):
            issue_url = 'https://' + issue_url
        
        parsed = urlparse(issue_url)
        if parsed.netloc != 'github.com':
            raise ValueError(f"Invalid GitHub URL: {issue_url}")
        
        # Parse path: /owner/repo/issues/123
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) != 4 or path_parts[2] != 'issues':
            raise ValueError(f"Invalid GitHub issue URL format: {issue_url}")
        
        try:
            issue_number = int(path_parts[3])
        except ValueError:
            raise ValueError(f"Invalid issue number in URL: {issue_url}")
        
        return {
            'owner': path_parts[0],
            'repo': path_parts[1],
            'issue_number': issue_number,
            'repo_url': f"https://github.com/{path_parts[0]}/{path_parts[1]}"
        }
    
    def fetch_issue_data(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetch issue data from GitHub API"""
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        
        try:
            response = requests.get(api_url, headers=self.headers)
            
            if response.status_code == 404:
                raise ValueError(f"Issue #{issue_number} not found in {owner}/{repo}")
            elif response.status_code != 200:
                raise ValueError(f"Failed to fetch issue: HTTP {response.status_code}")
            
            issue_data = response.json()
            
            # Also fetch comments
            comments_url = issue_data.get('comments_url', '')
            comments = []
            if comments_url:
                comments_response = requests.get(comments_url, headers=self.headers)
                if comments_response.status_code == 200:
                    comments = comments_response.json()
            
            issue_data['comments_data'] = comments
            return issue_data
            
        except requests.RequestException as e:
            raise ValueError(f"Error fetching issue data: {str(e)}")
    
    def synthesize_task_prompt(self, issue_data: Dict[str, Any], repo_info: Dict[str, Any]) -> str:
        """Convert GitHub issue data into a SimulateDev task prompt"""
        
        title = issue_data.get('title', 'Untitled Issue')
        body = issue_data.get('body', '')
        issue_number = issue_data.get('number', 'Unknown')
        issue_url = issue_data.get('html_url', '')
        labels = [label['name'] for label in issue_data.get('labels', [])]
        
        # Process comments
        comments = issue_data.get('comments_data', [])
        comments_text = ""
        if comments:
            comments_text = "\n\n## Discussion from Issue Comments:\n"
            for i, comment in enumerate(comments[:10], 1):  # Limit to first 10 comments
                author = comment.get('user', {}).get('login', 'Unknown')
                comment_body = comment.get('body', '')
                if comment_body.strip():
                    comments_text += f"\n**Comment {i} by @{author}:**\n{comment_body}\n"
        
        # Determine issue type and create appropriate prompt
        issue_type = self._classify_issue_type(title, body, labels)
        
        task_prompt = f"""# GitHub Issue Resolution Task

## Issue Information
- **Repository**: {repo_info['repo_url']}
- **Issue**: #{issue_number} - {title}
- **URL**: {issue_url}
- **Type**: {issue_type}
- **Labels**: {', '.join(labels) if labels else 'None'}

## Issue Description
{body}
{comments_text}

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
    
    def _classify_issue_type(self, title: str, body: str, labels: list) -> str:
        """Classify the type of issue based on title, body, and labels"""
        title_lower = title.lower()
        body_lower = body.lower() if body else ""
        labels_lower = [label.lower() for label in labels]
        
        # Check labels first
        if any(label in labels_lower for label in ['bug', 'error', 'fix', 'crash', 'broken']):
            return "Bug Fix"
        elif any(label in labels_lower for label in ['feature', 'enhancement', 'improvement']):
            return "Feature Enhancement"
        elif any(label in labels_lower for label in ['performance', 'optimization', 'slow']):
            return "Performance Optimization"
        elif any(label in labels_lower for label in ['security', 'vulnerability', 'exploit']):
            return "Security Fix"
        elif any(label in labels_lower for label in ['documentation', 'docs']):
            return "Documentation"
        
        # Check title and body content
        bug_keywords = ['bug', 'error', 'crash', 'broken', 'fail', 'issue', 'problem', 'exception', 'leak']
        feature_keywords = ['feature', 'add', 'implement', 'support', 'enable', 'allow']
        performance_keywords = ['slow', 'performance', 'optimize', 'speed', 'memory', 'cpu']
        
        text_content = f"{title_lower} {body_lower}"
        
        if any(keyword in text_content for keyword in bug_keywords):
            return "Bug Fix"
        elif any(keyword in text_content for keyword in performance_keywords):
            return "Performance Optimization"
        elif any(keyword in text_content for keyword in feature_keywords):
            return "Feature Enhancement"
        
        return "General Issue"


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Convert GitHub Issue to SimulateDev Task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single agent
  python issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 --agent cursor
  
  # Multi-agent
  python issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 \\
    --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'
  
  # Skip PR creation (for testing)
  python issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 --agent cursor --no-pr
        """
    )
    
    # Required arguments
    parser.add_argument("--issue-url", required=True, 
                       help="GitHub issue URL (e.g., https://github.com/owner/repo/issues/123)")
    
    # Agent specification (either single agent or multi-agent JSON)
    agent_group = parser.add_mutually_exclusive_group(required=True)
    agent_group.add_argument("--agent", 
                           choices=[agent.value for agent in CodingAgentIdeType],
                           help="Single AI coding agent to use")
    agent_group.add_argument("--coding-agents", 
                           help="JSON array of coding agents for multi-agent workflows")
    
    # Optional arguments
    parser.add_argument("--no-pr", action="store_true", 
                       help="Skip creating pull request (for testing)")
    parser.add_argument("--target-dir", 
                       help="Target directory for cloning")
    parser.add_argument("--work-dir", 
                       help="Working directory for the task")
    parser.add_argument("--output", 
                       help="Output file for execution report")
    parser.add_argument("--no-report", action="store_true", 
                       help="Skip saving execution report")
    parser.add_argument("--no-delete-existing-repo-env", action="store_true",
                       help="Keep existing repository directory")
    
    return parser.parse_args()


async def main():
    """Main function to process GitHub issue and run SimulateDev"""
    try:
        args = parse_arguments()
        
        print("Issue to Task Converter for SimulateDev")
        print("=" * 50)
        
        # Initialize GitHub issue processor
        processor = GitHubIssueProcessor()
        
        # Parse issue URL
        print(f"Parsing issue URL: {args.issue_url}")
        repo_info = processor.parse_issue_url(args.issue_url)
        print(f"Repository: {repo_info['owner']}/{repo_info['repo']}")
        print(f"Issue Number: #{repo_info['issue_number']}")
        
        # Fetch issue data
        print("Fetching issue data from GitHub...")
        issue_data = processor.fetch_issue_data(
            repo_info['owner'], 
            repo_info['repo'], 
            repo_info['issue_number']
        )
        
        print(f"Issue Title: {issue_data.get('title', 'Untitled')}")
        print(f"Issue State: {issue_data.get('state', 'unknown')}")
        
        # Check if issue is open
        if issue_data.get('state') != 'open':
            print(f"WARNING: Issue is {issue_data.get('state')}. Proceeding anyway...")
        
        # Synthesize task prompt
        print("Synthesizing task prompt...")
        task_prompt = processor.synthesize_task_prompt(issue_data, repo_info)
        
        # Parse coding agents
        if args.coding_agents:
            try:
                agents = validate_coding_agents_json(args.coding_agents)
                print(f"Using {len(agents)} custom agents")
            except ValueError as e:
                print(f"Error parsing coding agents: {e}")
                return False
        else:
            agents = create_default_coder_agent(args.agent)
            print(f"Using default single {args.agent} agent")
        
        # Create arguments for SimulateDev execution
        simulatedev_args = argparse.Namespace()
        simulatedev_args.workflow = "custom"
        simulatedev_args.repo = repo_info['repo_url']
        simulatedev_args.task = task_prompt
        simulatedev_args.agent = args.agent if not args.coding_agents else None
        simulatedev_args.coding_agents = args.coding_agents
        simulatedev_args.target_dir = args.target_dir
        simulatedev_args.work_dir = args.work_dir
        simulatedev_args.no_pr = args.no_pr
        simulatedev_args.output = args.output
        simulatedev_args.no_report = args.no_report
        simulatedev_args.no_delete_existing_repo_env = args.no_delete_existing_repo_env
        
        print("\nTask Summary:")
        print(f"  Issue: #{repo_info['issue_number']} - {issue_data.get('title', 'Untitled')}")
        print(f"  Repository: {repo_info['repo_url']}")
        print(f"  Agents: {len(agents)} agent(s)")
        for i, agent in enumerate(agents, 1):
            print(f"    {i}. {agent.role.value} - {agent.coding_ide} ({agent.model})")
        print(f"  Create PR: {'No' if args.no_pr else 'Yes'}")
        
        # Execute SimulateDev task
        print(f"\nSTARTING: Processing issue #{repo_info['issue_number']}...")
        try:
            success = await execute_task(simulatedev_args)
            
            if success:
                print(f"\nCOMPLETED: Issue #{repo_info['issue_number']} processed successfully!")
                print("Check the output above for the pull request URL.")
            else:
                print(f"\nFAILED: Issue #{repo_info['issue_number']} processing failed.")
                print("Check the output above for specific error details.")
            
            return success
        except Exception as task_error:
            print(f"\nERROR: Exception occurred while processing issue #{repo_info['issue_number']}: {str(task_error)}")
            return False
        
    except KeyboardInterrupt:
        print("\nTask interrupted by user")
        return False
    except Exception as e:
        print(f"Error processing issue: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 