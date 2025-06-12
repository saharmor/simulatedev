#!/usr/bin/env python3
"""
SimulateDev Workflows CLI - AI Coding Workflow Launcher

This tool provides a command-line interface for running predefined AI coding workflows 
on GitHub repositories using the unified orchestrator.

Usage:
    python workflows_cli.py <workflow> <repo_url> <agent_name>
    
Available Workflows:
    bugs        - Find and fix one high-impact bug
    optimize    - Find and implement one high-value performance optimization  
    refactor    - Code quality improvements and refactoring
    low-hanging - Find and implement one impressive low-hanging fruit improvement
    test        - Simple hello world test for end-to-end agent testing
    
Systematic Approach:
    1. MAPPING: Comprehensively identify all opportunities (bugs/improvements)
    2. RANKING: Score each by implementation likelihood + impact/impressiveness  
    3. SELECTION: Choose the highest-scoring opportunity
    4. IMPLEMENTATION: Implement only that one improvement completely
    
    This ensures the coding agent focuses on achievable, high-value work rather than
    attempting everything and potentially failing to complete any improvements.
    
Examples:
    python workflows_cli.py bugs https://github.com/user/repo cursor
    python workflows_cli.py optimize https://github.com/user/repo windsurf
    python workflows_cli.py low-hanging https://github.com/user/repo cursor
    
    # Skip pull request creation
    python workflows_cli.py bugs https://github.com/user/repo cursor --no-pr
    
    # Delete existing repository folder if it exists
    python workflows_cli.py bugs https://github.com/user/repo cursor --delete-existing
"""

import argparse
import asyncio
import os
import shutil
import sys
import webbrowser
from urllib.parse import urlparse

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import Orchestrator
from coding_agents import CodingAgentIdeType
from common.config import config
from common.exceptions import AgentTimeoutException, WorkflowTimeoutException


async def execute_workflow(workflow_type: str, repo_url: str, agent_type: str,
                          target_dir: str = None, create_pr: bool = True, 
                          delete_existing: bool = False) -> bool:
    """Execute a predefined workflow using the unified orchestrator"""
    try:
        print(f"STARTING: {workflow_type} workflow...")
        print(f"Repository: {repo_url}")
        print(f"Agent: {agent_type}")
        print(f"Timeout: {config.agent_timeout_seconds} seconds ({config.agent_timeout_seconds/60:.1f} minutes)")
        print(f"Approach: Systematic (map → rank → choose → implement one)")
        print(f"Create PR: {create_pr}")
        
        # Handle repository deletion if requested
        if delete_existing:
            parsed_path = urlparse(repo_url).path.rstrip('/')
            repo_name = os.path.splitext(os.path.basename(parsed_path))[0]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            repo_path = os.path.join(config.scanned_repos_path, repo_name)
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
                print(f"Deleted existing repository folder: {repo_path}")
        
        # Create workflow request using the unified orchestrator
        orchestrator = Orchestrator()
        request = Orchestrator.create_request(
            workflow_type=workflow_type,
            repo_url=repo_url,
            agent_type=agent_type,
            target_dir=target_dir,
            create_pr=create_pr,
            delete_existing=delete_existing
        )
        
        # Execute the workflow
        response = await orchestrator.execute_task(request)
        
        if response.success:
            print(f"\nCOMPLETED: {workflow_type.title()} workflow completed successfully!")
            
            # Open PR in browser if created
            if hasattr(response, 'pr_url') and response.pr_url:
                print("Opening pull request in your default browser...")
                webbrowser.open(response.pr_url)
                print(f"\nREVIEW: You can review the changes at: {response.pr_url}")
            
            print(f"\nRESULTS: Summary:\n{response.final_output}")
            return True
        else:
            print(f"\nFAILED: {workflow_type.title()} workflow did not complete successfully.")
            if response.error_message:
                print(f"Error: {response.error_message}")
            print("Check the output above for specific details about what went wrong.")
            return False
            
    except Exception as e:
        if isinstance(e, (AgentTimeoutException, WorkflowTimeoutException)):
            # Handle timeout scenarios gracefully
            print(f"\n{e.get_user_friendly_message()}")
        else:
            print(f"ERROR: Workflow execution failed: {str(e)}")
        return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run AI coding workflows on GitHub repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Workflows:
  bugs        - Find and fix one high-impact bug
  optimize    - Find and implement one high-value performance optimization  
  refactor    - Code quality improvements and refactoring
  low-hanging - Find and implement one impressive low-hanging fruit improvement
  test        - Simple hello world test for end-to-end agent testing
  
Systematic Approach:
  1. MAPPING: Comprehensively identify all opportunities
  2. RANKING: Score by implementation likelihood + impact/impressiveness  
  3. SELECTION: Choose the highest-scoring opportunity
  4. IMPLEMENTATION: Implement only that one improvement completely
  
Examples:
  python workflows_cli.py bugs https://github.com/user/repo cursor
  python workflows_cli.py optimize https://github.com/user/repo windsurf
  python workflows_cli.py low-hanging https://github.com/user/repo cursor
  
  # Skip pull request creation
  python workflows_cli.py bugs https://github.com/user/repo cursor --no-pr
  
  # Delete existing repository folder if it exists
  python workflows_cli.py bugs https://github.com/user/repo cursor --delete-existing
        """
    )
    
    parser.add_argument(
        "workflow",
        choices=["bugs", "optimize", "refactor", "low-hanging", "test"],
        help="The type of workflow to run"
    )
    
    parser.add_argument(
        "repo_url",
        help="URL of the GitHub repository to process"
    )
    
    parser.add_argument(
        "agent",
        choices=[agent.value for agent in CodingAgentIdeType],
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
    
    parser.add_argument(
        "--delete-existing",
        action="store_true",
        help="Delete existing repository folder if it already exists (default: False)"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point"""
    try:
        args = parse_arguments()
        
        # Execute workflow using the unified orchestrator
        success = await execute_workflow(
            workflow_type=args.workflow,
            repo_url=args.repo_url,
            agent_type=args.agent,
            target_dir=args.target_dir,
            create_pr=not args.no_pr,
            delete_existing=args.delete_existing
        )
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nINTERRUPTED: Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 