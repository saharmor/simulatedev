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
import webbrowser
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from clone_repo import clone_repository
from workflows.general_coding import GeneralCodingWorkflow
from github_integration import GitHubIntegration
from coding_agents import CodingAgentType
from exceptions import AgentTimeoutException, WorkflowTimeoutException


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
        self.workflow_orchestrator = GeneralCodingWorkflow()
        self.github_integration = GitHubIntegration()
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos")
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Create CodingAgentResponses directory
        self.responses_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CodingAgentResponses")
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def save_agent_response(self, repo_url: str, agent_name: str, response: str):
        """Save the agent response to a file with the specified naming format"""
        try:
            # Extract repository name from URL
            repo_name = os.path.splitext(os.path.basename(repo_url.rstrip('/')))[0]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            # Generate timestamp
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M")
            
            # Create filename
            filename = f"{repo_name}_{date_str}_{time_str}.txt"
            filepath = os.path.join(self.responses_dir, filename)
            
            # Save response to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"SimulateDev Agent Response\n")
                f.write(f"{'='*50}\n")
                f.write(f"Repository: {repo_url}\n")
                f.write(f"Agent: {agent_name}\n")
                f.write(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
                f.write(response)
            
            print(f"SUCCESS: Agent response saved to: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"WARNING: Failed to save agent response: {str(e)}")
            return None
    
    async def process_request(self, request: ProjectRequest) -> bool:
        """
        Process a coding request through the specified AI agent
        
        Args:
            request: ProjectRequest containing repo URL, prompt, and agent
            
        Returns:
            bool: True if successful, False otherwise
        """
        pr_url = None
        agent_response = None
        is_error = False
        try:
            from config import config
            
            print(f"Starting SimulateDev process...")
            print(f"Repository: {request.repo_url}")
            print(f"Agent: {request.agent.value}")
            print(f"Timeout: {config.agent_timeout_seconds} seconds ({config.agent_timeout_seconds/60:.1f} minutes)")
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
                repo_path = self.workflow_orchestrator.clone_repository(request.repo_url)
            
            print(f"SUCCESS: Repository cloned to: {repo_path}")
            
            # Step 2: Open IDE
            print(f"\nOpening {request.agent.value.title()}...")
            repo_name = self.workflow_orchestrator.get_repo_name(request.repo_url)
            await self.workflow_orchestrator.open_ide(request.agent, repo_path, repo_name)
            print(f"SUCCESS: {request.agent.value.title()} opened successfully")
            
            # Step 3: Execute prompt with agent (includes sending, waiting, and getting response)
            print(f"\nExecuting prompt with {request.agent.value.title()}...")
            agent_execution_report_summary = await self.workflow_orchestrator.execute_agent_prompt(request.agent, request.prompt)
            print("SUCCESS: Agent completed the task and returned results")
            
            # Step 6: Save agent response to file
            print("\nSaving agent response...")
            response_filepath = self.save_agent_response(request.repo_url, request.agent.value, agent_response)
            
            # Step 7: Create pull request (includes all git operations)
            if request.create_pr:
                print("\nProcessing changes and creating pull request...")
                pr_url = self.github_integration.smart_workflow(
                    repo_path=repo_path,
                    original_repo_url=request.repo_url,
                    agent_name=request.agent.value,
                    agent_execution_report_summary=agent_execution_report_summary
                )
                
                if pr_url:
                    print(f"SUCCESS: Pull request created: {pr_url}")
                    print("Opening pull request in your default browser...")
                    webbrowser.open(pr_url)
                else:
                    print("WARNING: Pull request creation failed")
            else:
                print("\nSkipping pull request creation")
            
            print(f"\nProcess completed successfully!")
            print(f"Results:\n{agent_response}")
            
            # Print final summary with PR URL if available
            print(f"\n{'='*60}")
            print(f"SIMULATEDEV COMPLETED SUCCESSFULLY")
            print(f"{'='*60}")
            print(f"Repository: {request.repo_url}")
            print(f"Agent: {request.agent.value}")
            if response_filepath:
                print(f"Response saved to: {response_filepath}")
            if pr_url:
                print(f"Pull Request URL: {pr_url}")
                print(f"\nYou can review and merge the changes at: {pr_url}")
            print(f"{'='*60}")
            
            return True
        except (AgentTimeoutException, WorkflowTimeoutException) as e:
            print(f"\n{e.get_user_friendly_message()}")
            is_error = True
        except Exception as e:
            print(f"ERROR: Error during processing: {str(e)}")
            
            # Still try to save the response if we got one
            if agent_response:
                print("\nAttempting to save agent response despite error...")
                self.save_agent_response(request.repo_url, request.agent.value, agent_response)
            is_error = True
        
        if is_error:
            # Print summary even on failure
            print(f"\n{'='*60}")
            print(f"SimulateDev failed!")
            print(f"{'='*60}")
            print(f"Repository: {request.repo_url}")
            print(f"Agent: {request.agent.value}")
            print(f"Error: {str(e)}")
            if pr_url:
                print(f"Pull Request URL: {pr_url}")
            print(f"{'='*60}")
            
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
            print("\nSimulateDev did not complete successfully.")
            print("Check the output above for specific details about what went wrong.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 