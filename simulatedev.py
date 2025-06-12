#!/usr/bin/env python3
"""
SimulateDev - AI Coding Assistant

This is the main CLI for SimulateDev that executes coding tasks using AI agents.
By default, it uses a single coder agent, but you can specify multiple agents via JSON.

Usage:
    python simulatedev.py --task "Fix responsive table design" --repo https://github.com/saharmor/gemini-multimodal-playground --workflow general_coding
    python simulatedev.py --task "Add error handling" --repo https://github.com/saharmor/gemini-multimodal-playground --workflow general_coding --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Coder"}]'
    
    # Multi-agent example
    python simulatedev.py --task "Build REST API with tests" --repo https://github.com/saharmor/gemini-multimodal-playground --workflow general_coding --coding-agents '[
        {"coding_ide":"claude_code","model":"Claude Opus 3","role":"Planner"},
        {"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Coder"},
        {"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Tester"}
    ]'

Available workflows:
- general_coding: Custom coding tasks with your own prompt
- bug_hunting: Find and fix security vulnerabilities and bugs  
- code_optimization: Performance optimizations and improvements

Note: 
- Repository must be a valid GitHub URL (https://github.com/user/repo)
- When specifying coding agents, the 'model' field is mandatory and cannot be empty or 'N/A'.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.orchestrator import Orchestrator, TaskRequest
from agents import MultiAgentTask, AgentDefinition, AgentRole, CodingAgentIdeType


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


def create_default_coder_agent() -> List[AgentDefinition]:
    """Create default single coder agent"""
    return [AgentDefinition(
        coding_ide="cursor",  # Default to cursor
        model="claude-4-sonnet",  # Default model
        role=AgentRole.CODER
    )]


def print_task_summary(request: TaskRequest):
    """Print a summary of the task to be executed"""
    print(f"\nTask Summary:")
    print(f"  Task: {request.task_description}")
    print(f"  Repository: {request.repo_url or request.work_directory or 'Current directory'}")
    print(f"  Workflow: {request.workflow_type}")
    print(f"  Agents: {len(request.agents)} agent(s)")
    
    for i, agent in enumerate(request.agents, 1):
        print(f"    {i}. {agent.role.value} - {agent.coding_ide} ({agent.model})")
    
    if request.target_dir:
        print(f"  Target Directory: {request.target_dir}")
    if request.work_directory:
        print(f"  Work Directory: {request.work_directory}")
    print(f"  Create PR: {'Yes' if request.create_pr else 'No'}")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="SimulateDev - AI Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single agent (default)
  python simulatedev.py --task "Fix responsive design" --repo https://github.com/saharmor/gemini-multimodal-playground --workflow general_coding
  
  # Multiple agents
  python simulatedev.py --task "Build REST API" --repo https://github.com/saharmor/gemini-multimodal-playground --workflow general_coding \\
    --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'

Available workflows: general_coding, bug_hunting, code_optimization
Note: 
- Repository must be a valid GitHub URL (https://github.com/user/repo)
- Model field is mandatory and cannot be empty or 'N/A' when specifying coding agents.
        """
    )
    
    # Required arguments
    parser.add_argument("--task", required=True, help="The coding task description")
    parser.add_argument("--repo", required=True, help="GitHub repository URL (e.g., https://github.com/saharmor/gemini-multimodal-playground)")
    parser.add_argument("--workflow", required=True, choices=["general_coding", "bug_hunting", "code_optimization"], help="Workflow type")
    
    # Optional arguments
    parser.add_argument("--coding-agents", help="JSON array of coding agents (defaults to single coder agent)")
    parser.add_argument("--target-dir", help="Target directory for cloning")
    parser.add_argument("--work-dir", help="Working directory for the task")
    parser.add_argument("--no-pr", action="store_true", help="Skip creating pull request")
    parser.add_argument("--output", help="Output file for execution report")
    parser.add_argument("--no-report", action="store_true", help="Skip saving execution report")
    parser.add_argument("--delete-existing", action="store_true", help="Delete existing repository directory before cloning")
    
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
        
        # Parse coding agents or use default
        if args.coding_agents:
            try:
                agents = validate_coding_agents_json(args.coding_agents)
                print(f"Using {len(agents)} custom agents")
            except ValueError as e:
                print(f"Error parsing coding agents: {e}")
                return False
        else:
            agents = create_default_coder_agent()
            print("Using default single coder agent")
        
        # Use the GitHub URL directly
        repo_url = args.repo
        work_directory = args.work_dir
        
        # Create task request using unified method
        if len(agents) == 1:
            # Single agent
            agent = agents[0]
            task_request = Orchestrator.create_request(
                task_description=args.task,
                agent_type=agent.coding_ide,
                agent_model=agent.model,
                agent_role=agent.role,
                workflow_type=args.workflow,
                repo_url=repo_url,
                target_dir=args.target_dir,
                create_pr=not args.no_pr,
                work_directory=work_directory,
                delete_existing=args.delete_existing
            )
        else:
            # Multi-agent
            multi_agent_task = MultiAgentTask(
                agents=agents,
                repo_url=repo_url,
                workflow=args.workflow,
                coding_task_prompt=args.task
            )
            task_request = Orchestrator.create_request(
                multi_agent_task=multi_agent_task,
                workflow_type=args.workflow,
                repo_url=repo_url,
                target_dir=args.target_dir,
                create_pr=not args.no_pr,
                work_directory=work_directory,
                delete_existing=args.delete_existing
            )
        
        # Print summary
        print_task_summary(task_request)
        
        # Confirm execution
        confirm = input("\nExecute this task? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("Task execution cancelled")
            return False
        
        # Execute
        orchestrator = Orchestrator()
        response = await orchestrator.execute_task(task_request)
        
        # Save report if requested
        if not args.no_report:
            output_file = args.output or f"{args.workflow}_execution_report.json"
            orchestrator.save_execution_report(response, output_file)
            print(f"Execution report saved to: {output_file}")
        
        return response.success
        
    except Exception as e:
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