#!/usr/bin/env python3
"""
SimulateDev Workflows CLI - AI Coding Workflow Launcher

This tool allows you to run AI coding workflows on GitHub repositories.
Each workflow follows a systematic approach: Map → Rank → Choose → Implement

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
from typing import Optional
from dataclasses import dataclass

from utils.clone_repo import clone_repository
from workflows.bug_hunting import BugHunter
from workflows.code_optimization import CodeOptimizer
from workflows.general_coding import GeneralCodingWorkflow
from workflows.test_workflow import TestWorkflow
from src.github_integration import GitHubIntegration
from coding_agents import CodingAgentIdeType

from common.config import config
from common.exceptions import AgentTimeoutException, WorkflowTimeoutException

@dataclass
class WorkflowRequest:
    workflow_type: str
    repo_url: str
    agent: CodingAgentIdeType
    target_dir: Optional[str] = None
    create_pr: bool = True


class WorkflowOrchestrator:
    """Orchestrator for AI coding workflows"""
    
    def __init__(self):
        self.github_integration = GitHubIntegration()
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos")
        os.makedirs(self.base_dir, exist_ok=True)
    
    def get_workflow_instance(self, workflow_type: str):
        """Get the appropriate workflow instance based on type"""
        workflows = {
            'bugs': BugHunter(),
            'optimize': CodeOptimizer(),
            'refactor': CodeOptimizer(),  # Uses refactor method
            'low-hanging': CodeOptimizer(),  # Uses low-hanging fruit method
            'general': GeneralCodingWorkflow(),
            'test': TestWorkflow()
        }
        
        if workflow_type not in workflows:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        return workflows[workflow_type]
    
    async def execute_workflow(self, request: WorkflowRequest) -> bool:
        """Execute the specified workflow"""
        try:            
            print(f"STARTING: {request.workflow_type} workflow...")
            print(f"Repository: {request.repo_url}")
            print(f"Agent: {request.agent.value}")
            print(f"Timeout: {config.agent_timeout_seconds} seconds ({config.agent_timeout_seconds/60:.1f} minutes)")
            print(f"Approach: Systematic (map → rank → choose → implement one)")
            print(f"Create PR: {request.create_pr}")
            
            # Get workflow instance
            workflow = self.get_workflow_instance(request.workflow_type)
            
            # Step 1: Clone repository
            print("\nCLONING: repository...")
            if request.target_dir:
                repo_path = request.target_dir
                success = clone_repository(request.repo_url, request.target_dir)
                if not success:
                    print("ERROR: Failed to clone repository")
                    return False
            else:
                repo_path = workflow.clone_repository(request.repo_url)
            
            print(f"SUCCESS: Repository cloned to: {repo_path}")
            
            # Step 2: Execute the specific workflow
            print(f"\nEXECUTING: {request.workflow_type} workflow...")
            
            if request.workflow_type == 'bugs':
                agent_execution_report_summary = await workflow.hunt_bugs(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'optimize':
                agent_execution_report_summary = await workflow.optimize_performance(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'refactor':
                agent_execution_report_summary = await workflow.refactor_code(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'low-hanging':
                agent_execution_report_summary = await workflow.find_low_hanging_fruit(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'test':
                agent_execution_report_summary = await workflow.execute_simple_hello_world(request.agent, repo_path)
            else:
                # General workflow would need a prompt, but we're focusing on specialized workflows here
                raise ValueError(f"Unsupported workflow in execute_workflow: {request.workflow_type}")
            
            print("SUCCESS: Workflow completed")
            
            # Step 3: Create pull request if requested
            if request.create_pr:
                print("\nCREATING: pull request...")
                
                pr_url = self.github_integration.smart_workflow(
                    repo_path=repo_path,
                    original_repo_url=request.repo_url,
                    agent_name=f"{request.agent.value}-{request.workflow_type}",
                    agent_execution_report_summary=agent_execution_report_summary
                )
                
                if pr_url:
                    print(f"SUCCESS: Pull request created: {pr_url}")
                    print("Opening pull request in your default browser...")
                    webbrowser.open(pr_url)
                    print(f"\nREVIEW: You can review the changes at: {pr_url}")
                else:
                    print("WARNING: Pull request creation failed")
            else:
                print("\nSKIPPING: pull request creation")
            
            print(f"\nRESULTS: Summary:\n{agent_execution_report_summary}")
            
            return True
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
        
        # Convert string to enum
        agent_type = CodingAgentIdeType(args.agent)
        
        # Create workflow request
        request = WorkflowRequest(
            workflow_type=args.workflow,
            repo_url=args.repo_url,
            agent=agent_type,
            target_dir=args.target_dir,
            create_pr=not args.no_pr,
        )
        
        if args.delete_existing:
            # delete local repo directory using same logic as AgentOrchestrator
            from urllib.parse import urlparse
            parsed_path = urlparse(args.repo_url).path.rstrip('/')
            repo_name = os.path.splitext(os.path.basename(parsed_path))[0]
            repo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos", repo_name)
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
                print(f"Deleted existing repository folder: {repo_path}")
        
        # Initialize and run workflow orchestrator
        orchestrator = WorkflowOrchestrator()
        success = await orchestrator.execute_workflow(request)
        
        if success:
            print(f"\nCOMPLETED: {args.workflow.title()} workflow completed successfully!")
            sys.exit(0)
        else:
            print(f"\nFAILED: {args.workflow.title()} workflow did not complete successfully.")
            print("Check the output above for specific details about what went wrong.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nINTERRUPTED: Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 