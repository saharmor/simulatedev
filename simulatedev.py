#!/usr/bin/env python3
"""
SimulateDev - AI Coding Assistant

This is the unified CLI for SimulateDev that executes both predefined workflows and custom coding tasks using AI agents.

Usage:
    # Single coding agent + predefined workflows
    python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor
    python simulatedev.py --workflow optimize --repo https://github.com/user/repo --agent windsurf
    python simulatedev.py --workflow refactor --repo https://github.com/user/repo --agent cursor
    python simulatedev.py --workflow low-hanging --repo https://github.com/user/repo --agent cursor
    
         # Single coding agent + custom coding workflow (requires task description)
     python simulatedev.py --workflow custom --task "Fix responsive table design" --repo https://github.com/user/repo --agent cursor
     
     # Multi-agent + custom coding workflow
     python simulatedev.py --workflow custom --task "Add support for Firefox browser automation" --repo  https://github.com/browserbase/stagehand --coding-agents '[
        {"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},
        {"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}
    ]'

Available workflows:
- bugs: Find and fix one high-impact bug
- optimize: Find and implement one high-value performance optimization  
- refactor: Code quality improvements and refactoring
- low-hanging: Find and implement one impressive low-hanging fruit improvement
- custom: Custom coding tasks with your own prompt (requires --task)

Note: 
- Repository must be a valid GitHub URL (https://github.com/user/repo)
- For custom workflow, --task is required
- When specifying coding agents, the 'model' field is mandatory and cannot be empty or 'N/A'
"""

import argparse
import asyncio
import json
import os
import shutil
import sys
import webbrowser
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse

from src.orchestrator import Orchestrator, TaskRequest
from agents import MultiAgentTask, AgentDefinition, AgentRole, CodingAgentIdeType
from common.config import config
from common.exceptions import AgentTimeoutException, WorkflowTimeoutException


def validate_github_url(repo_url: str) -> bool:
    """Validate that the repository URL is a valid GitHub URL"""
    if not repo_url:
        return False
    
    # Check for GitHub URL patterns
    github_patterns = [
        'https://github.com/',
        'http://github.com/',
        'git@github.com:',
        'github.com/'
    ]
    
    return any(repo_url.startswith(pattern) for pattern in github_patterns)


def validate_coding_agents_json(json_string: str) -> List[AgentDefinition]:
    """Validate and parse coding agents JSON"""
    try:
        agents_data = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON for coding agents: {str(e)}")
    
    if not isinstance(agents_data, list):
        raise ValueError("Coding agents must be a JSON array")
    
    if len(agents_data) == 0:
        raise ValueError("Coding agents array cannot be empty")
    
    agents = []
    supported_roles = [role.value for role in AgentRole]
    used_roles = set()
    
    for i, agent_data in enumerate(agents_data):
        if not isinstance(agent_data, dict):
            raise ValueError(f"Agent {i} must be an object")
        
        # Check required fields
        for field in ["coding_ide", "model", "role"]:
            if field not in agent_data:
                raise ValueError(f"Agent {i} missing required field: '{field}'")
        
        # Validate model is not empty or N/A
        model = agent_data["model"].strip() if isinstance(agent_data["model"], str) else str(agent_data["model"])
        if not model or model.upper() == "N/A":
            raise ValueError(f"Agent {i} must have a valid model specified (cannot be empty or 'N/A')")
        
        # Validate role
        if agent_data["role"] not in supported_roles:
            raise ValueError(f"Agent {i} has invalid role: '{agent_data['role']}'. Supported roles: {supported_roles}")
        
        # Check for duplicate roles
        agent_role = agent_data["role"]
        if agent_role in used_roles:
            raise ValueError(f"Duplicate role '{agent_role}' found. Each role can only be assigned to one agent.")
        used_roles.add(agent_role)
        
        # Create agent definition
        agent_def = AgentDefinition.from_dict(agent_data)
        agents.append(agent_def)
    
    return agents


def create_default_coder_agent(agent_type: str = "cursor") -> List[AgentDefinition]:
    """Create default single coder agent"""
    return [AgentDefinition(
        coding_ide=agent_type,
        model="claude-4-sonnet",  # Default model
        role=AgentRole.CODER
    )]


def print_task_summary(request: TaskRequest, workflow_type: str):
    """Print a summary of the task to be executed"""
    print(f"\nTask Summary:")
    if workflow_type == "custom":
        print(f"  Task: {request.task_description}")
    else:
        print(f"  Workflow: {workflow_type.title()} - Systematic approach (map → rank → choose → implement one)")
    print(f"  Repository: {request.repo_url or request.work_directory or 'Current directory'}")
    print(f"  Workflow Type: {workflow_type}")
    print(f"  Agents: {len(request.agents)} agent(s)")
    
    for i, agent in enumerate(request.agents, 1):
        print(f"    {i}. {agent.role.value} - {agent.coding_ide} ({agent.model})")
    
    if request.target_dir:
        print(f"  Target Directory: {request.target_dir}")
    if request.work_directory:
        print(f"  Work Directory: {request.work_directory}")
    print(f"  Create PR: {'Yes' if request.create_pr else 'No'}")
    if hasattr(config, 'agent_timeout_seconds'):
        print(f"  Timeout: {config.agent_timeout_seconds} seconds ({config.agent_timeout_seconds/60:.1f} minutes)")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="SimulateDev - AI Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Workflows:
  bugs        - Find and fix one high-impact bug
  optimize    - Find and implement one high-value performance optimization  
  refactor    - Code quality improvements and refactoring
  low-hanging - Find and implement one impressive low-hanging fruit improvement
  custom      - Custom coding tasks with your own prompt (requires --task)

Examples:
  # Predefined workflows
  python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor
  python simulatedev.py --workflow optimize --repo https://github.com/user/repo --agent windsurf
  
  # Custom coding (single agent)
  python simulatedev.py --workflow custom --task "Fix responsive design" --repo https://github.com/user/repo --agent cursor
  
  # Custom coding (multiple agents)
  python simulatedev.py --workflow custom --task "Build REST API" --repo https://github.com/user/repo \\
    --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'

  # Skip pull request creation (only recommended for testing purposes)
  python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor --no-pr
  
  # Keep existing repository folder (don't delete before cloning)
  python simulatedev.py --workflow optimize --repo https://github.com/user/repo --agent cursor --no-delete-existing-repo-env

Note: 
- Repository must be a valid GitHub URL (https://github.com/user/repo)
- For custom workflow, --task is required
- Model field is mandatory and cannot be empty or 'N/A' when specifying coding agents
        """
    )
    
    # Required arguments
    parser.add_argument("--workflow", required=True, 
                       choices=["bugs", "optimize", "refactor", "low-hanging", "custom"], 
                       help="The type of workflow to run")
    parser.add_argument("--repo", required=True, 
                       help="GitHub repository URL (e.g., https://github.com/user/repo)")
    
    # Agent specification (either single agent or multi-agent JSON)
    agent_group = parser.add_mutually_exclusive_group()
    agent_group.add_argument("--agent", 
                           choices=[agent.value for agent in CodingAgentIdeType],
                           help="Single AI coding agent to use (for simple workflows)")
    agent_group.add_argument("--coding-agents", 
                           help="JSON array of coding agents (for complex multi-agent workflows)")
    
    # Task description (required for custom workflow)
    parser.add_argument("--task", 
                       help="The coding task description (required for custom workflow)")
    
    # Optional arguments
    parser.add_argument("--target-dir", help="Target directory for cloning")
    parser.add_argument("--work-dir", help="Working directory for the task")
    parser.add_argument("--no-pr", action="store_true", help="Skip creating pull request (only recommended for testing purposes)")
    parser.add_argument("--output", help="Output file for execution report")
    parser.add_argument("--no-report", action="store_true", help="Skip saving execution report")
    parser.add_argument("--no-delete-existing-repo-env", action="store_true",
                       help="Keep existing repository directory (don't delete before cloning)")
    
    return parser.parse_args()


async def execute_task(args) -> bool:
    """Execute the coding task"""
    try:
        print("SimulateDev - AI Coding Assistant")
        print("=" * 40)
        
        # Validate GitHub URL
        if not validate_github_url(args.repo):
            print(f"Error: Repository must be a valid GitHub URL")
            print(f"Provided: {args.repo}")
            print("Valid formats:")
            print("  - https://github.com/user/repo")
            print("  - http://github.com/user/repo") 
            print("  - git@github.com:user/repo.git")
            print("  - github.com/user/repo")
            return False
        
        # Validate task requirement for custom workflow
        if args.workflow == "custom" and not args.task:
            print("Error: --task is required for custom workflow")
            return False
        
        # Validate agent specification
        if not args.agent and not args.coding_agents:
            print("Error: Either --agent or --coding-agents must be specified")
            return False
        
        # Determine if we should delete existing repository directory
        # Default is True, unless --no-delete-existing-repo-env is specified
        delete_existing_repo_env = not args.no_delete_existing_repo_env
        
        # Handle repository deletion if requested
        if delete_existing_repo_env:
            parsed_path = urlparse(args.repo).path.rstrip('/')
            repo_name = os.path.splitext(os.path.basename(parsed_path))[0]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            repo_path = os.path.join(config.scanned_repos_path, repo_name)
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
                print(f"Deleted existing repository folder: {repo_path}")
        
        # Parse coding agents or use default
        if args.coding_agents:
            try:
                agents = validate_coding_agents_json(args.coding_agents)
                print(f"Using {len(agents)} custom agents")
            except ValueError as e:
                print(f"Error parsing coding agents: {e}")
                return False
        else:
            # Use single agent
            agent_type = args.agent or "cursor"
            agents = create_default_coder_agent(agent_type)
            print(f"Using default single {agent_type} agent")
        
        # Create task request based on workflow type
        if args.workflow == "custom":
            # Custom coding workflow
            if len(agents) == 1:
                # Single agent
                agent = agents[0]
                task_request = Orchestrator.create_request(
                    task_description=args.task,
                    agent_type=agent.coding_ide,
                    agent_model=agent.model,
                    agent_role=agent.role,
                    workflow_type="custom_coding",  # Map to internal workflow type
                    repo_url=args.repo,
                    target_dir=args.target_dir,
                    create_pr=not args.no_pr,
                    work_directory=args.work_dir,
                    delete_existing_repo_env=delete_existing_repo_env
                )
            else:
                # Multi-agent
                from agents.base import WorkflowType
                workflow_enum = WorkflowType("custom_coding")
                multi_agent_task = MultiAgentTask(
                    agents=agents,
                    repo_url=args.repo,
                    workflow=workflow_enum,
                    coding_task_prompt=args.task
                )
                task_request = Orchestrator.create_request(
                    multi_agent_task=multi_agent_task,
                    workflow_type="custom_coding",
                    repo_url=args.repo,
                    target_dir=args.target_dir,
                    create_pr=not args.no_pr,
                    work_directory=args.work_dir,
                    delete_existing_repo_env=delete_existing_repo_env
                )
        else:
            # Predefined workflow (bugs, optimize, refactor, low-hanging)
            agent = agents[0]  # Use first agent for predefined workflows
            task_request = Orchestrator.create_request(
                workflow_type=args.workflow,
                repo_url=args.repo,
                agent_type=agent.coding_ide,
                agent_model=agent.model,
                agent_role=agent.role,
                target_dir=args.target_dir,
                create_pr=not args.no_pr,
                delete_existing_repo_env=delete_existing_repo_env
            )
        
        # Print summary
        print_task_summary(task_request, args.workflow)
        
        # Confirm execution
        # confirm = input("\nExecute this task? (y/N): ").strip().lower()
        # if confirm not in ['y', 'yes']:
        #     print("Task execution cancelled")
        #     return False
        
        # Execute
        print(f"\nSTARTING: {args.workflow} workflow...")
        orchestrator = Orchestrator()
        response = await orchestrator.execute_task(task_request)
        
        if response.success:
            print(f"\nCOMPLETED: {args.workflow.title()} workflow completed successfully!")
            
            # Show PR URL if created (but don't open it - orchestrator already did)
            if hasattr(response, 'pr_url') and response.pr_url:
                print(f"\nREVIEW: You can review the changes at: {response.pr_url}")
        else:
            print(f"\nFAILED: {args.workflow.title()} workflow did not complete successfully.")
            if response.error_message:
                print(f"Error: {response.error_message}")
            print("Check the output above for specific details about what went wrong.")
        
        # Save report if requested
        if not args.no_report:
            if args.output:
                # If user specified a custom output path, use it as-is
                output_file = args.output
            else:
                # Use the configured execution output directory
                output_filename = f"{args.workflow}_execution_report.json"
                output_file = os.path.join(config.execution_output_path, output_filename)
            orchestrator.save_execution_report(response, output_file)
            print(f"Execution report saved to: {output_file}")
        
        return response.success
        
    except Exception as e:
        if isinstance(e, (AgentTimeoutException, WorkflowTimeoutException)):
            # Handle timeout scenarios gracefully
            print(f"\n{e.get_user_friendly_message()}")
        else:
            print(f"Task execution failed: {str(e)}")
        return False


async def main():
    """Main entry point"""
    try:
        args = parse_arguments()
        
        # Execute the task
        success = await execute_task(args)
        
        # Print final results
        print(f"\n{'='*60}")
        if success:
            print(f"EXECUTION COMPLETED SUCCESSFULLY")
        else:
            print(f"EXECUTION FAILED")
        print(f"{'='*60}")
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nExecution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 