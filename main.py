#!/usr/bin/env python3
"""
SimulateDev - AI Coding Agent Orchestrator

This tool allows you to run various AI coding agents (Cursor, Windsurf, Claude Code) 
on any GitHub repository with a custom prompt, and automatically create pull requests.

Usage:
    python main.py <repo_url> <prompt> <agent_name>
    
Examples:
    python main.py https://github.com/user/repo "Fix responsive table design" cursor
    python main.py https://github.com/user/repo "Add error handling" windsurf
"""

import argparse
import asyncio
import os
import sys
from typing import Optional
from dataclasses import dataclass

from clone_repo import clone_repository
from bug_hunter import BugHunter
from computer_use_utils import ClaudeComputerUse
from github_integration import GitHubIntegration
from coding_agents import AgentFactory, CodingAgentType


@dataclass
class ProjectRequest:
    repo_url: str
    prompt: str
    agent: CodingAgentType
    target_dir: Optional[str] = None
    create_pr: bool = True


class SimulateDev:
    """Main orchestrator for AI coding agent automation"""
    
    def __init__(self):
        self.bug_hunter = BugHunter()
        self.github_integration = GitHubIntegration()
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos")
        os.makedirs(self.base_dir, exist_ok=True)
    
    async def process_request(self, request: ProjectRequest) -> bool:
        """
        Process a coding request through the specified AI agent
        
        Args:
            request: ProjectRequest containing repo URL, prompt, and agent
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Starting SimulateDev process...")
            print(f"Repository: {request.repo_url}")
            print(f"Agent: {request.agent.value}")
            print(f"Prompt: {request.prompt}")
            print(f"Create PR: {request.create_pr}")
            
            # Step 1: Clone repository
            print("\nCloning repository...")
            if request.target_dir:
                repo_path = request.target_dir
                success = clone_repository(request.repo_url, request.target_dir)
                if not success:
                    print("ERROR: Failed to clone repository")
                    return False
            else:
                repo_path = self.bug_hunter.clone_repository(request.repo_url)
            
            print(f"SUCCESS: Repository cloned to: {repo_path}")
            
            # Step 2: Open IDE
            print(f"\nOpening {request.agent.value.title()}...")
            await self.bug_hunter.open_ide(request.agent, repo_path, should_wait_for_focus=True)
            print(f"SUCCESS: {request.agent.value.title()} opened successfully")
            
            # Step 3: Send prompt to agent (using new agent class system)
            print(f"\nSending prompt to {request.agent.value.title()}...")
            await self.bug_hunter.send_prompt_to_agent(request.agent, request.prompt)
            print("SUCCESS: Prompt sent successfully")
            
            # Step 4: Wait for completion
            print(f"\nWaiting for {request.agent.value.title()} to complete...")
            await self.bug_hunter.wait_for_agent_completion(request.agent, timeout_seconds=300)
            print("SUCCESS: Agent completed the task")
            
            # Step 5: Extract results
            print("\nExtracting results...")
            results = await self.bug_hunter.get_last_message(request.agent)
            print("SUCCESS: Results extracted")
            
            # Step 6: Create pull request (includes all git operations)
            if request.create_pr:
                print("\nProcessing changes and creating pull request...")
                pr_url = self.github_integration.smart_workflow(
                    repo_path=repo_path,
                    original_repo_url=request.repo_url,
                    prompt=request.prompt,
                    agent_name=request.agent.value
                )
                
                if pr_url:
                    print(f"SUCCESS: Pull request created: {pr_url}")
                    print(f"\nYou can review the changes at: {pr_url}")
                else:
                    print("WARNING: Pull request creation failed")
            else:
                print("\nSkipping pull request creation")
            
            print(f"\nProcess completed successfully!")
            print(f"Results:\n{results}")
            
            return True
            
        except Exception as e:
            print(f"ERROR: Error during processing: {str(e)}")
            return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run AI coding agents on GitHub repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py https://github.com/user/repo "Fix responsive table design" cursor
  python main.py https://github.com/user/repo "Add error handling" windsurf
  python main.py https://github.com/user/repo "Optimize performance" claude_code
  
  # Skip pull request creation
  python main.py https://github.com/user/repo "Fix bugs" cursor --no-pr
        """
    )
    
    parser.add_argument(
        "repo_url",
        help="URL of the GitHub repository to process"
    )
    
    parser.add_argument(
        "prompt", 
        help="The coding task prompt to send to the AI agent"
    )
    
    parser.add_argument(
        "agent",
        choices=[agent.value for agent in CodingAgentType],
        help="The AI coding agent to use"
    )
    
    parser.add_argument(
        "--target-dir",
        help="Custom directory to clone the repository (optional)"
    )
    
    parser.add_argument(
        "--no-pr",
        action="store_true",
        help="Skip creating a pull request"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point"""
    try:
        args = parse_arguments()
        
        # Convert string to enum
        agent_type = CodingAgentType(args.agent)
        
        # Create project request
        request = ProjectRequest(
            repo_url=args.repo_url,
            prompt=args.prompt,
            agent=agent_type,
            target_dir=args.target_dir,
            create_pr=not args.no_pr
        )
        
        # Initialize and run SimulateDev
        simulatedev = SimulateDev()
        success = await simulatedev.process_request(request)
        
        if success:
            print("\nSimulateDev completed successfully!")
            sys.exit(0)
        else:
            print("\nSimulateDev failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 