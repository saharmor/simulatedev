#!/usr/bin/env python3
"""
SimulateDev - AI Coding Agent Orchestrator

This tool allows you to run various AI coding agents (Cursor, Windsurf, Cloud Code) 
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
from enum import Enum
from typing import Optional
from dataclasses import dataclass

from clone_repo import clone_repository
from bug_hunter import BugHunter
from computer_use_utils import ClaudeComputerUse
from github_integration import GitHubIntegration


class CodingAgent(Enum):
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    CLOUD_CODE = "cloud_code"  # TODO: Implement Cloud Code support


@dataclass
class ProjectRequest:
    repo_url: str
    prompt: str
    agent: CodingAgent
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
            
            # Step 2: Setup Git for PR creation (before making changes)
            if request.create_pr:
                print("\nSetting up Git configuration...")
                if not self.github_integration.setup_git_config(repo_path):
                    print("WARNING: Git setup failed, continuing without PR creation")
                    request.create_pr = False
            
            # Step 3: Open IDE
            print(f"\nOpening {request.agent.value.title()}...")
            await self.bug_hunter.open_ide(request.agent.value, repo_path, should_wait_for_focus=True)
            print(f"SUCCESS: {request.agent.value.title()} opened successfully")
            
            # Step 4: Get input field and send prompt
            print(f"\nSending prompt to {request.agent.value.title()}...")
            input_coords = await self.bug_hunter.get_input_field_coordinates(request.agent.value)
            if not input_coords:
                print("ERROR: Could not locate input field")
                return False
            
            await self.send_custom_prompt(input_coords, request.prompt)
            print("SUCCESS: Prompt sent successfully")
            
            # Step 5: Wait for completion
            print(f"\nWaiting for {request.agent.value.title()} to complete...")
            await self.wait_for_completion(request.agent.value)
            print("SUCCESS: Agent completed the task")
            
            # Step 6: Extract results
            print("\nExtracting results...")
            results = await self.bug_hunter.get_last_message(request.agent.value)
            print("SUCCESS: Results extracted")
            
            # Step 7: Create pull request
            if request.create_pr:
                print("\nCreating pull request...")
                pr_url = self.github_integration.full_workflow(
                    repo_path=repo_path,
                    repo_url=request.repo_url,
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
    
    async def send_custom_prompt(self, input_coords, prompt: str):
        """Send a custom prompt to the IDE input field"""
        import pyautogui
        import time
        
        # Move to input field and click
        print(f"Moving to input field at ({input_coords.coordinates.x}, {input_coords.coordinates.y})...")
        pyautogui.moveTo(input_coords.coordinates.x, input_coords.coordinates.y, duration=1.0)
        time.sleep(0.5)
        pyautogui.click(input_coords.coordinates.x, input_coords.coordinates.y)
        time.sleep(1.0)
        
        # Type the prompt
        print("Typing custom prompt...")
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            pyautogui.write(line)
            if i < len(lines) - 1:
                pyautogui.hotkey('shift', 'enter')
        
        pyautogui.press('enter')
        time.sleep(1.0)
    
    async def wait_for_completion(self, agent_name: str):
        """Wait for the agent to complete processing"""
        from ide_completion_detector import wait_until_ide_finishes
        from bug_hunter import INTERFACE_CONFIG
        
        if agent_name in INTERFACE_CONFIG:
            interface_state_prompt = INTERFACE_CONFIG[agent_name]["interface_state_prompt"]
            await wait_until_ide_finishes(agent_name, interface_state_prompt, timeout_in_seconds=300)
        else:
            print(f"WARNING: No interface config found for {agent_name}, using generic wait...")
            import time
            time.sleep(30)  # Generic fallback


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run AI coding agents on GitHub repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py https://github.com/user/repo "Fix responsive table design" cursor
  python main.py https://github.com/user/repo "Add error handling" windsurf
  python main.py https://github.com/user/repo "Optimize performance" cloud_code
  
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
        choices=[agent.value for agent in CodingAgent],
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
        
        # Create project request
        request = ProjectRequest(
            repo_url=args.repo_url,
            prompt=args.prompt,
            agent=CodingAgent(args.agent),
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