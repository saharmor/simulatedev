#!/usr/bin/env python3
"""
SimulateDev Workflows CLI - Specialized Workflow Launcher

This tool allows you to run specialized AI coding workflows on GitHub repositories.

Usage:
    python workflows_cli.py <workflow> <repo_url> <agent_name>
    
Available Workflows:
    bugs        - Find and fix bugs in the codebase
    optimize    - Performance optimization and refactoring  
    refactor    - Code quality improvements and refactoring
    low-hanging - Find easy wins and quick improvements
    
Examples:
    python workflows_cli.py bugs https://github.com/user/repo cursor
    python workflows_cli.py optimize https://github.com/user/repo windsurf
    python workflows_cli.py low-hanging https://github.com/user/repo cursor
"""

import argparse
import asyncio
import os
import sys
from typing import Optional
from dataclasses import dataclass

from clone_repo import clone_repository
from workflows.bug_hunting import BugHunter
from workflows.code_optimization import CodeOptimizer
from workflows.general_coding import GeneralCodingWorkflow
from github_integration import GitHubIntegration
from coding_agents import CodingAgentType


@dataclass
class WorkflowRequest:
    workflow_type: str
    repo_url: str
    agent: CodingAgentType
    target_dir: Optional[str] = None
    create_pr: bool = True


class WorkflowOrchestrator:
    """Orchestrator for specialized AI coding workflows"""
    
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
            'general': GeneralCodingWorkflow()
        }
        
        if workflow_type not in workflows:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        return workflows[workflow_type]
    
    async def execute_workflow(self, request: WorkflowRequest) -> bool:
        """Execute the specified workflow"""
        try:
            print(f"🚀 Starting {request.workflow_type} workflow...")
            print(f"Repository: {request.repo_url}")
            print(f"Agent: {request.agent.value}")
            print(f"Create PR: {request.create_pr}")
            
            # Get workflow instance
            workflow = self.get_workflow_instance(request.workflow_type)
            
            # Step 1: Clone repository
            print("\n📥 Cloning repository...")
            if request.target_dir:
                repo_path = request.target_dir
                success = clone_repository(request.repo_url, request.target_dir)
                if not success:
                    print("❌ ERROR: Failed to clone repository")
                    return False
            else:
                repo_path = workflow.clone_repository(request.repo_url)
            
            print(f"✅ SUCCESS: Repository cloned to: {repo_path}")
            
            # Step 2: Execute the specific workflow
            print(f"\n🔧 Executing {request.workflow_type} workflow...")
            
            if request.workflow_type == 'bugs':
                results = await workflow.hunt_bugs(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'optimize':
                results = await workflow.optimize_performance(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'refactor':
                results = await workflow.refactor_code(request.agent, request.repo_url, repo_path)
            elif request.workflow_type == 'low-hanging':
                results = await workflow.find_low_hanging_fruit(request.agent, request.repo_url, repo_path)
            else:
                # General workflow would need a prompt, but we're focusing on specialized workflows here
                raise ValueError(f"Unsupported workflow in execute_workflow: {request.workflow_type}")
            
            print("✅ SUCCESS: Workflow completed")
            
            # Step 3: Create pull request if requested
            if request.create_pr:
                print("\n📝 Creating pull request...")
                
                # Create workflow-specific commit message
                workflow_descriptions = {
                    'bugs': 'Fix bugs and security issues',
                    'optimize': 'Performance optimizations and improvements',
                    'refactor': 'Code refactoring and quality improvements',
                    'low-hanging': 'Quick wins and easy improvements'
                }
                
                commit_message = workflow_descriptions.get(request.workflow_type, f"{request.workflow_type} improvements")
                
                pr_url = self.github_integration.smart_workflow(
                    repo_path=repo_path,
                    original_repo_url=request.repo_url,
                    prompt=commit_message,
                    agent_name=f"{request.agent.value}-{request.workflow_type}"
                )
                
                if pr_url:
                    print(f"✅ SUCCESS: Pull request created: {pr_url}")
                    print(f"\n🔗 You can review the changes at: {pr_url}")
                else:
                    print("⚠️ WARNING: Pull request creation failed")
            else:
                print("\n⏭️ Skipping pull request creation")
            
            print(f"\n🎉 {request.workflow_type.title()} workflow completed successfully!")
            print(f"\n📊 Results Summary:\n{results}")
            
            return True
            
        except Exception as e:
            print(f"❌ ERROR: Workflow execution failed: {str(e)}")
            return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run specialized AI coding workflows on GitHub repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Workflows:
  bugs        - Find and fix bugs in the codebase
  optimize    - Performance optimization and improvements  
  refactor    - Code quality improvements and refactoring
  low-hanging - Find easy wins and quick improvements
  
Examples:
  python workflows_cli.py bugs https://github.com/user/repo cursor
  python workflows_cli.py optimize https://github.com/user/repo windsurf
  python workflows_cli.py refactor https://github.com/user/repo cursor
  python workflows_cli.py low-hanging https://github.com/user/repo windsurf
  
  # Skip pull request creation
  python workflows_cli.py bugs https://github.com/user/repo cursor --no-pr
        """
    )
    
    parser.add_argument(
        "workflow",
        choices=["bugs", "optimize", "refactor", "low-hanging"],
        help="The type of workflow to run"
    )
    
    parser.add_argument(
        "repo_url",
        help="URL of the GitHub repository to process"
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
        
        # Create workflow request
        request = WorkflowRequest(
            workflow_type=args.workflow,
            repo_url=args.repo_url,
            agent=agent_type,
            target_dir=args.target_dir,
            create_pr=not args.no_pr
        )
        
        # Initialize and run workflow orchestrator
        orchestrator = WorkflowOrchestrator()
        success = await orchestrator.execute_workflow(request)
        
        if success:
            print(f"\n🎊 {args.workflow.title()} workflow completed successfully!")
            sys.exit(0)
        else:
            print(f"\n💥 {args.workflow.title()} workflow failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 