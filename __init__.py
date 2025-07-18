#!/usr/bin/env python3
"""
SimulateDev - Public API for Single Agent Execution

This module provides a clean, simple API for running a single coding agent
on a GitHub repository with a custom prompt.
"""

import os
import time
import asyncio
import re
from typing import Optional
from dataclasses import dataclass

from utils.computer_use_utils import LLMComputerUse, close_ide_window_for_project
from agents import AgentFactory, CodingAgentIdeType
from agents.web_agent import WebAgent
from utils.clone_repo import clone_repository
from src.github_integration import GitHubIntegration
from common.config import config


@dataclass
class SimulateDevResponse:
    """Response from SimulateDev agent execution"""
    success: bool
    output: str
    error_message: Optional[str] = None
    pr_url: Optional[str] = None
    execution_time_seconds: Optional[float] = None


class SimulateDevError(Exception):
    """Base exception for SimulateDev errors"""
    pass


class SimulateDevAPI:
    """Core API implementation for single agent execution"""
    
    def __init__(self):
        self.computer_use_client = LLMComputerUse()
        self.github_integration = GitHubIntegration()
        
        # Create necessary directories
        self.base_dir = config.scanned_repos_path
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.responses_dir = config.reports_path
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def _validate_inputs(self, agent: str, prompt: str, repo_url: str):
        """Validate input parameters"""
        if not agent:
            raise SimulateDevError("Agent parameter is required")
        
        if not prompt:
            raise SimulateDevError("Prompt parameter is required")
        
        if not repo_url:
            raise SimulateDevError("Repository URL parameter is required")
        
        # Validate agent type
        try:
            CodingAgentIdeType(agent.lower().strip())
        except ValueError:
            valid_agents = [e.value for e in CodingAgentIdeType]
            raise SimulateDevError(f"Unsupported agent type: {agent}. Valid types: {', '.join(valid_agents)}")
    
    def _is_web_agent(self, agent_type: str) -> bool:
        """Check if the agent type is a web agent"""
        try:
            agent_enum = CodingAgentIdeType(agent_type.lower().strip())
            temp_agent = AgentFactory.create_agent(agent_enum, self.computer_use_client)
            return isinstance(temp_agent, WebAgent)
        except Exception:
            return False
    
    def _handle_web_agent_repo_setup(self, repo_url: str, agent_type: str) -> tuple[str, str]:
        """Handle repository setup for web agents (forking if necessary)
        
        Returns:
            tuple: (working_repo_url, original_repo_url)
        """
        if not self._is_web_agent(agent_type):
            return repo_url, repo_url
        
        print("INFO: Web agent detected, checking repository ownership...")
        
        # Check if we own the repository (required for web agents)
        is_owner = self.github_integration.check_repository_ownership(repo_url)
        
        if is_owner:
            print(f"SUCCESS: You own the repository {repo_url}, no forking needed")
            return repo_url, repo_url
        
        print(f"INFO: You don't own {repo_url}, attempting to fork...")
        
        # Fork the repository
        fork_url = self.github_integration.fork_repository(repo_url)
        
        if fork_url:
            print(f"SUCCESS: Repository forked to {fork_url}")
            print(f"INFO: Web agent will use fork: {fork_url}")
            print(f"INFO: Original repository: {repo_url}")
            return fork_url, repo_url
        else:
            print("ERROR: Failed to fork repository")
            print("WARNING: Web agent may not be able to make changes to the repository")
            return repo_url, repo_url
    
    def _setup_repository(self, repo_url: str) -> str:
        """Clone repository and return the local path"""
        repo_name = os.path.splitext(os.path.basename(repo_url.rstrip('/')))[0]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        repo_path = os.path.join(self.base_dir, repo_name)
        success = clone_repository(repo_url, repo_path, delete_existing_repo_env=True)
        
        if not success:
            raise SimulateDevError(f"Failed to clone repository: {repo_url}")
        
        return repo_path
    
    async def _execute_agent(self, agent_type: str, prompt: str, work_directory: str, 
                            working_repo_url: str, original_repo_url: str) -> SimulateDevResponse:
        """Execute a single agent with the given prompt"""
        start_time = time.time()
        
        try:
            # Create agent instance
            agent_enum = CodingAgentIdeType(agent_type.lower().strip())
            agent = AgentFactory.create_agent(agent_enum, self.computer_use_client)
            
            # Set current project for window management
            agent.set_current_project(work_directory)
            
            # Set repository context for web agents
            if isinstance(agent, WebAgent):
                agent.set_repository_context(working_repo_url, original_repo_url)
            
            # Change to work directory
            original_cwd = os.getcwd()
            os.chdir(work_directory)
            
            try:
                # Close any existing IDE window to ensure clean state
                repo_name = os.path.basename(work_directory)
                close_ide_window_for_project(agent.window_name, repo_name)
                time.sleep(2)  # Wait for window to close
                
                # Open coding interface
                await agent.open_coding_interface()
                
                # Execute the prompt
                response = await agent.execute_prompt(prompt)
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Close the coding interface
                try:
                    close_success = await agent.close_coding_interface()
                    if not close_success:
                        print(f"WARNING: Failed to close {agent_type} interface")
                except Exception as e:
                    print(f"WARNING: Error closing {agent_type} interface: {str(e)}")
                
                return SimulateDevResponse(
                    success=response.success,
                    output=response.content,
                    error_message=response.error_message,
                    execution_time_seconds=execution_time
                )
                
            finally:
                os.chdir(original_cwd)
                
        except Exception as e:
            execution_time = time.time() - start_time
            return SimulateDevResponse(
                success=False,
                output="",
                error_message=f"Agent execution failed: {str(e)}",
                execution_time_seconds=execution_time
            )
    
    def _create_pull_request(self, original_repo_url: str, work_directory: str, 
                           agent_type: str, output: str, execution_time: float) -> Optional[str]:
        """Create a pull request with the changes"""
        try:
            return self.github_integration.smart_workflow(
                repo_path=work_directory,
                original_repo_url=original_repo_url,
                workflow_name=f"SimulateDev-{agent_type}",
                agent_execution_report_summary=output[:1000] + "..." if len(output) > 1000 else output,
                coding_ides_info=f"{agent_type} agent",
                execution_time_seconds=execution_time
            )
        except Exception as e:
            print(f"WARNING: Pull request creation failed: {e}")
            return None
    
    def _extract_pr_url_from_web_agent_output(self, output: str) -> Optional[str]:
        """Extract PR URL from web agent output if available"""
        pr_pattern = r'PR created: (https://github\.com/[^\s]+)'
        pr_match = re.search(pr_pattern, output)
        if pr_match:
            return pr_match.group(1)
        return None
    
    async def run(self, agent: str, prompt: str, repo_url: str, 
                  create_pr: bool = True) -> SimulateDevResponse:
        """
        Run a single coding agent on a GitHub repository with a custom prompt.
        
        Args:
            agent: The agent type (e.g., "cursor", "windsurf", "claude_code")
            prompt: The task description for the agent
            repo_url: URL of the GitHub repository to work on
            create_pr: Whether to create a pull request with the changes (default: True)
            
        Returns:
            SimulateDevResponse: Response containing the agent's output and metadata
            
        Raises:
            SimulateDevError: If validation fails or execution encounters an error
        """
        # Validate inputs
        self._validate_inputs(agent, prompt, repo_url)
        
        # Validate API key
        if not config.validate_required_keys():
            raise SimulateDevError("Missing required API keys. Please check your .env file.")
        
        try:
            # Handle web agent repository setup (forking if necessary)
            working_repo_url, original_repo_url = self._handle_web_agent_repo_setup(repo_url, agent)
            
            # Setup repository
            work_directory = self._setup_repository(working_repo_url)
            
            # Execute agent
            response = await self._execute_agent(agent, prompt, work_directory, working_repo_url, original_repo_url)
            
            # Handle pull request creation
            if create_pr and response.success and response.execution_time_seconds:
                is_web_agent = self._is_web_agent(agent)
                
                if is_web_agent:
                    # For web agents, try to extract PR URL from output first
                    pr_url = self._extract_pr_url_from_web_agent_output(response.output)
                    if pr_url:
                        print(f"\nINFO: Web agent created PR: {pr_url}")
                        response.pr_url = pr_url
                    else:
                        print("\nINFO: Web agent detected - skipping orchestrator PR creation")
                else:
                    # For non-web agents, create PR using orchestrator
                    pr_url = self._create_pull_request(
                        original_repo_url, work_directory, agent, 
                        response.output, response.execution_time_seconds
                    )
                    response.pr_url = pr_url
            
            return response
            
        except SimulateDevError:
            raise
        except Exception as e:
            raise SimulateDevError(f"Unexpected error during execution: {str(e)}")


# Global API instance
_api = SimulateDevAPI()


async def run(agent: str, prompt: str, repo_url: str, 
              create_pr: bool = True) -> SimulateDevResponse:
    """
    Run a single coding agent on a GitHub repository with a custom prompt.
    
    This is the main async interface for SimulateDev.
    
    Args:
        agent: The agent type (e.g., "cursor", "windsurf", "claude_code")
        prompt: The task description for the agent
        repo_url: URL of the GitHub repository to work on
        create_pr: Whether to create a pull request with the changes (default: True)
        
    Returns:
        SimulateDevResponse: Response containing the agent's output and metadata
        
    Raises:
        SimulateDevError: If validation fails or execution encounters an error
        
    Example:
        >>> import simulatedev
        >>> response = await run(
        ...     agent="cursor",
        ...     prompt="Find and fix a single bug",
        ...     repo_url="https://github.com/saharmor/simulatedev"
        ... )
        >>> print(response.output)
        >>> print(response.pr_url)
    """
    return await _api.run(agent, prompt, repo_url, create_pr)


def run_sync(agent: str, prompt: str, repo_url: str, 
             create_pr: bool = True) -> SimulateDevResponse:
    """
    Run a single coding agent on a GitHub repository with a custom prompt (synchronous).
    
    This is a synchronous wrapper around the async `run` function.
    
    Args:
        agent: The agent type (e.g., "cursor", "windsurf", "claude_code")
        prompt: The task description for the agent
        repo_url: URL of the GitHub repository to work on
        create_pr: Whether to create a pull request with the changes (default: True)
        
    Returns:
        SimulateDevResponse: Response containing the agent's output and metadata
        
    Raises:
        SimulateDevError: If validation fails or execution encounters an error
        
    Example:
        >>> import simulatedev
        >>> response = run_sync(
        ...     agent="cursor",
        ...     prompt="Find and fix a single bug",
        ...     repo_url="https://github.com/saharmor/simulatedev"
        ... )
        >>> print(response.output)
        >>> print(response.pr_url)
    """
    return asyncio.run(run(agent, prompt, repo_url, create_pr))

async def test_api_async():
    """Test the async API"""
    print("Testing async API...")
    
    try:
        # Test with a simple repository and task
        response = await run(
            agent="cursor",  # Can also use "windsurf", "claude_code", "openai_codex", "test"
            prompt="Add a comment to the main function explaining what it does",
            repo_url="https://github.com/saharmor/simulatedev",
            create_pr=False  # Skip PR creation for testing
        )
        
        print(f"Success: {response.success}")
        print(f"Output length: {len(response.output)} characters")
        print(f"Execution time: {response.execution_time_seconds:.2f} seconds")
        
        if response.error_message:
            print(f"Error: {response.error_message}")
        
        return response.success
        
    except SimulateDevError as e:
        print(f"SimulateDevError: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def test_api_sync():
    """Test the sync API"""
    print("Testing sync API...")
    
    try:
        response = run_sync(
            agent="cursor",
            prompt="Add a comment to the main function explaining what it does",
            repo_url="https://github.com/saharmor/simulatedev",
            create_pr=False
        )
        
        print(f"Success: {response.success}")
        print(f"Output length: {len(response.output)} characters")
        print(f"Execution time: {response.execution_time_seconds:.2f} seconds")
        
        if response.error_message:
            print(f"Error: {response.error_message}")
        
        return response.success
        
    except SimulateDevError as e:
        print(f"SimulateDevError: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def test_web_agent():
    """Test web agent specifically"""
    print("Testing web agent (OpenAI Codex)...")
    
    try:
        response = run_sync(
            agent="openai_codex",  # Web agent that handles forking automatically
            prompt="Add a comment to the main function explaining what it does",
            repo_url="https://github.com/saharmor/simulatedev",
            create_pr=False
        )
        
        print(f"Success: {response.success}")
        print(f"Output length: {len(response.output)} characters")
        print(f"Execution time: {response.execution_time_seconds:.2f} seconds")
        
        if response.error_message:
            print(f"Error: {response.error_message}")
        
        return response.success
        
    except SimulateDevError as e:
        print(f"SimulateDevError: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def test_validation():
    """Test input validation"""
    print("Testing input validation...")
    
    # Test empty agent
    try:
        run_sync("", "prompt", "https://github.com/user/repo")
        print("ERROR: Should have failed for empty agent")
        return False
    except SimulateDevError as e:
        print(f"✓ Correctly caught empty agent: {e}")
    
    # Test invalid agent
    try:
        run_sync("invalid_agent", "prompt", "https://github.com/user/repo")
        print("ERROR: Should have failed for invalid agent")
        return False
    except SimulateDevError as e:
        print(f"✓ Correctly caught invalid agent: {e}")
    
    # Test empty prompt
    try:
        run_sync("cursor", "", "https://github.com/user/repo")
        print("ERROR: Should have failed for empty prompt")
        return False
    except SimulateDevError as e:
        print(f"✓ Correctly caught empty prompt: {e}")
    
    # Test empty repo_url
    try:
        run_sync("cursor", "prompt", "")
        print("ERROR: Should have failed for empty repo_url")
        return False
    except SimulateDevError as e:
        print(f"✓ Correctly caught empty repo_url: {e}")
    
    return True


if __name__ == "__main__":
    print("SimulateDev Public API Test")
    print("=" * 50)
    
    # Test validation first
    validation_passed = test_validation()
    
    if validation_passed:
        print("\n" + "=" * 50)
        print("Validation tests passed!")
        print("=" * 50)
        
        # Choose which test to run
        print("\nSelect test to run:")
        print("1. Async API test")
        print("2. Sync API test")
        print("3. Web agent test (OpenAI Codex)")
        print("4. Skip execution tests (validation only)")
        
        choice = input("Enter choice (1-4): ").strip()
        
        if choice == "1":
            success = asyncio.run(test_api_async())
        elif choice == "2":
            success = test_api_sync()
        elif choice == "3":
            success = test_web_agent()
        else:
            print("Skipping execution tests.")
            success = True
        
        if success:
            print("\n✓ All tests passed!")
        else:
            print("\n✗ Some tests failed.")
    else:
        print("\n✗ Validation tests failed.")


# Export public API
__all__ = ['run', 'run_sync', 'SimulateDevResponse', 'SimulateDevError']