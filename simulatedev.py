#!/usr/bin/env python3
"""
SimulateDev - Unified AI Coding Assistant

This is the main CLI for SimulateDev that handles both single-agent and multi-agent workflows
using a unified architecture. Single-agent workflows are treated as multi-agent workflows 
with one coder agent.

A workflow must be specified using the --workflow flag. Available workflows:
- general_coding: Custom coding tasks with your own prompt
- bug_hunting: Find and fix security vulnerabilities and bugs  
- code_optimization: Performance optimizations and improvements

Usage:
    # Single-agent mode (most common)
    python simulatedev.py "Fix responsive table design" cursor --repo https://github.com/user/repo --workflow general_coding
    python simulatedev.py "Add error handling" windsurf --work-dir ./my-project --workflow general_coding
    
    # Multi-agent mode
    python simulatedev.py --multi task.json --repo https://github.com/user/repo --workflow bug_hunting
    python simulatedev.py --multi --json '{"task":"Build app","agents":[...]}' --workflow code_optimization
    python simulatedev.py --multi --interactive --workflow general_coding

Examples:
    # Quick single-agent tasks
    python simulatedev.py "Fix the login bug" cursor --repo https://github.com/myorg/webapp --workflow general_coding
    python simulatedev.py "Add unit tests" windsurf --work-dir ./my-project --no-pr --workflow general_coding
    
    # Multi-agent collaboration
    python simulatedev.py --multi task.json --repo https://github.com/myorg/webapp --workflow bug_hunting
    python simulatedev.py --multi --interactive --workflow code_optimization
    
    # Complex multi-agent with JSON
    python simulatedev.py --multi --json '{
        "task": "Build a REST API with tests",
        "agents": [
            {"coding_ide": "claude_code", "model": "Opus 4", "role": "Planner"},
            {"coding_ide": "cursor", "model": "N/A", "role": "Coder"},
            {"coding_ide": "windsurf", "model": "4", "role": "Tester"}
        ]
    }' --workflow general_coding
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


def validate_json_input(data: Dict[str, Any]) -> MultiAgentTask:
    """Validate and parse JSON input into MultiAgentTask"""
    
    # Validate required fields
    if "agents" not in data:
        raise ValueError("Missing required field: 'agents'")
    
    if not isinstance(data["agents"], list) or len(data["agents"]) == 0:
        raise ValueError("'agents' must be a non-empty list")
    
    # For general_coding workflow, coding_task_prompt is required
    # Note: workflow might be passed as command-line argument, so check both JSON and assume general_coding if prompt is provided
    workflow_in_json = data.get("workflow")
    has_coding_prompt = data.get("coding_task_prompt") or data.get("prompt") or data.get("task")
    
    if workflow_in_json == "general_coding" and not has_coding_prompt:
        raise ValueError("'coding_task_prompt' is required for 'general_coding' workflow")
    
    # Validate and parse agents
    agents = []
    supported_roles = [role.value for role in AgentRole]
    used_roles = set()
    
    for i, agent_data in enumerate(data["agents"]):
        if not isinstance(agent_data, dict):
            raise ValueError(f"Agent {i} must be an object")
        
        # Check required fields
        if "coding_ide" not in agent_data:
            raise ValueError(f"Agent {i} missing required field: 'coding_ide'")
        
        for field in ["model", "role"]:
            if field not in agent_data:
                raise ValueError(f"Agent {i} missing required field: '{field}'")
        
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
    
    return MultiAgentTask.from_dict(data)


def load_json_from_file(file_path: str) -> Dict[str, Any]:
    """Load JSON from file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in file {file_path}: {str(e)}")


def load_json_from_string(json_string: str) -> Dict[str, Any]:
    """Load JSON from string"""
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON string: {str(e)}")


def interactive_multi_agent_mode() -> MultiAgentTask:
    """Interactive mode for creating multi-agent tasks"""
    print("Multi-Agent Task Builder")
    print("=" * 40)
    
    # Get repository URL (optional since it can be passed via --repo)
    repo_url = input("Enter repository URL (optional, can also use --repo flag): ").strip()
    if not repo_url:
        repo_url = None
    
    # Get workflow type (required, but can be overridden by --workflow flag)
    print("\nWorkflow selection (required - will be overridden by --workflow flag if provided):")
    print("  1. general_coding - Custom coding tasks with your own prompt")
    print("  2. bug_hunting - Find and fix security vulnerabilities and bugs")
    print("  3. code_optimization - Performance optimizations and improvements")
    
    workflow_choice = input("Select workflow (1-3): ").strip()
    workflow = None
    coding_task_prompt = None
    
    if workflow_choice == "1":
        workflow = "general_coding"
        coding_task_prompt = input("Enter your custom coding task prompt: ").strip()
        if not coding_task_prompt:
            print("Coding task prompt cannot be empty for general_coding workflow.")
            sys.exit(1)
    elif workflow_choice == "2":
        workflow = "bug_hunting"
    elif workflow_choice == "3":
        workflow = "code_optimization"
    else:
        print("Invalid workflow choice. Please select 1, 2, or 3.")
        sys.exit(1)
    
    # Get agents
    agents = []
    print("\nNow let's define the agents:")
    supported_agents = [agent.value for agent in CodingAgentIdeType]
    print(f"Supported agents: {', '.join(supported_agents)}")
    supported_roles = [role.value for role in AgentRole]
    print(f"Supported roles: {', '.join(supported_roles)}")
    
    while True:
        print(f"\nAgent {len(agents) + 1}:")
        coding_ide = input("  Coding IDE (or 'done' to finish): ").strip()
        
        if coding_ide.lower() == 'done':
            break
        
        if not coding_ide:
            print("  Coding IDE cannot be empty.")
            continue
        
        model = input("  Model (e.g., 'Opus 4', 'N/A'): ").strip()
        if not model:
            model = "N/A"
        
        role = input("  Role (Planner/Coder/Tester): ").strip()
        
        try:
            agent_role = AgentRole(role)
            agents.append(AgentDefinition(coding_ide=coding_ide, model=model, role=agent_role))
            print(f"  Added {coding_ide} as {role}")
        except ValueError:
            print(f"  Invalid role: {role}. Supported roles: Planner, Coder, Tester")
    
    if not agents:
        print("At least one agent is required.")
        sys.exit(1)
    
    return MultiAgentTask(agents=agents, repo_url=repo_url, workflow=workflow, coding_task_prompt=coding_task_prompt)


def print_task_summary(request: TaskRequest):
    """Print a summary of the task request"""
    if request.workflow_type:
        workflow_type = f"Workflow ({request.workflow_type})"
    else:
        workflow_type = "Single-Agent" if len(request.agents) == 1 and request.agents[0].role == AgentRole.CODER else "Multi-Agent"
    
    print(f"\n{workflow_type} Task Summary")
    print(f"=" * 50)
    print(f"Task: {request.task_description}")
    
    if request.workflow_type:
        print(f"Workflow: {request.workflow_type}")
    
    print(f"Agents: {len(request.agents)}")
    
    for i, agent in enumerate(request.agents, 1):
        print(f"  {i}. {agent.coding_ide} ({agent.model}) - {agent.role.value}")
    
    if request.repo_url:
        print(f"Repository: {request.repo_url}")
    
    if request.work_directory:
        print(f"Work Directory: {request.work_directory}")
    
    print(f"Create PR: {request.create_pr}")
    print(f"=" * 50)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="SimulateDev - Unified AI Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single-agent (default mode)
  python simulatedev.py "Fix responsive design" cursor --repo https://github.com/user/repo --workflow general_coding
  python simulatedev.py "Add error handling" windsurf --work-dir ./project --workflow general_coding
  
  # Multi-agent mode
  python simulatedev.py --multi task.json --repo https://github.com/user/repo --workflow bug_hunting
  python simulatedev.py --multi --json '{"task":"Build app","agents":[...]}' --workflow code_optimization
  python simulatedev.py --multi --interactive --workflow general_coding

Note: A workflow must be specified using the --workflow flag.
        """
    )
    
    # Mode selection
    parser.add_argument("--multi", action="store_true", help="Multi-agent mode")
    
    # Single-agent arguments (default mode)
    parser.add_argument("task", nargs="?", help="The coding task description (single-agent mode)")
    parser.add_argument("agent", nargs="?", help="Agent type: cursor, windsurf, claude, etc. (single-agent mode)")
    
    # Multi-agent input methods
    multi_group = parser.add_mutually_exclusive_group()
    multi_group.add_argument("json_file", nargs="?", help="Path to JSON file (multi-agent mode)")
    multi_group.add_argument("--json", help="JSON string (multi-agent mode)")
    multi_group.add_argument("--interactive", action="store_true", help="Interactive mode (multi-agent)")
    
    # Common options
    parser.add_argument("--repo", help="Repository URL to clone")
    parser.add_argument("--target-dir", help="Target directory for cloning")
    parser.add_argument("--work-dir", help="Working directory for the task")
    parser.add_argument("--workflow", choices=["general_coding", "bug_hunting", "code_optimization"], help="Workflow type (REQUIRED)", required=True)
    parser.add_argument("--no-pr", action="store_true", help="Skip creating pull request")
    parser.add_argument("--output", help="Output file for execution report")
    parser.add_argument("--no-report", action="store_true", help="Skip saving execution report")
    parser.add_argument("--delete-existing", action="store_true", help="Delete existing repository directory before cloning")
    
    return parser.parse_args()


async def execute_single_agent(args) -> bool:
    """Execute single-agent workflow"""
    try:
        print("Single-Agent Mode")
        print("=" * 30)
        
        # Get task and agent from arguments
        task_description = args.task
        agent_name = args.agent
        repo_url = args.repo
        
        if not task_description or not agent_name:
            print("Task description and agent are required for single-agent mode")
            return False
        
        # Validate agent type
        try:
            agent_type = CodingAgentIdeType(agent_name.lower())
        except ValueError:
            print(f"Invalid agent type: {agent_name}")
            print(f"Supported agents: {[agent.value for agent in CodingAgentIdeType]}")
            return False
        
        # Create task request
        task_request = Orchestrator.create_single_agent_request(
            task_description=task_description,
            agent_type=agent_type.value,
            workflow_type=args.workflow,
            repo_url=repo_url,
            target_dir=args.target_dir,
            create_pr=not args.no_pr,
            work_directory=args.work_dir,
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
            output_file = args.output or "single_agent_execution_report.json"
            orchestrator.save_execution_report(response, output_file)
        
        return response.success
        
    except Exception as e:
        print(f"Single-agent execution failed: {str(e)}")
        return False


async def execute_multi_agent(args) -> bool:
    """Execute multi-agent workflow"""
    try:
        print("Multi-Agent Mode")
        print("=" * 30)
        
        # Load task based on input method
        if args.json_file:
            print(f"Loading task from file: {args.json_file}")
            json_data = load_json_from_file(args.json_file)
            task = validate_json_input(json_data)
        elif args.json:
            print("Loading task from JSON string")
            json_data = load_json_from_string(args.json)
            task = validate_json_input(json_data)
        elif args.interactive:
            task = interactive_multi_agent_mode()
        else:
            print("No input method specified for multi-agent mode")
            print("Use: --json 'json_string', json_file, or --interactive")
            return False
        
        # Create task request
        task_request = Orchestrator.create_multi_agent_request(
            task=task,
            workflow_type=args.workflow,
            repo_url=args.repo,
            target_dir=args.target_dir,
            create_pr=not args.no_pr,
            work_directory=args.work_dir,
            delete_existing=args.delete_existing
        )
        
        # Print summary
        print_task_summary(task_request)
        
        # Confirm execution
        confirm = input("\nExecute this multi-agent task? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("Task execution cancelled")
            return False
        
        # Execute
        orchestrator = Orchestrator()
        response = await orchestrator.execute_task(task_request)
        
        # Save report if requested
        if not args.no_report:
            output_file = args.output or "multi_agent_execution_report.json"
            orchestrator.save_execution_report(response, output_file)
        
        return response.success
        
    except Exception as e:
        print(f"Multi-agent execution failed: {str(e)}")
        return False


async def main():
    """Main entry point"""
    try:
        args = parse_arguments()
        
        # Determine mode
        if args.multi or args.json_file or args.json or args.interactive:
            # Multi-agent mode
            success = await execute_multi_agent(args)
        elif args.task and args.agent:
            # Single-agent mode
            success = await execute_single_agent(args)
        else:
            # Show help if no clear mode is specified
            print("Please specify a valid mode:")
            print()
            print("Single-agent (default):")
            print("  python simulatedev.py 'Fix bug' cursor --repo https://github.com/user/repo --workflow general_coding")
            print()
            print("Multi-agent:")
            print("  python simulatedev.py --multi task.json --workflow bug_hunting")
            print("  python simulatedev.py --multi --interactive --workflow code_optimization")
            print()
            print("Use --help for more information")
            return False
        
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