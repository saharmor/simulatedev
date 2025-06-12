#!/usr/bin/env python3
"""
Test Workflow Module

A simple test workflow that prints "hello world" to test agent end-to-end execution,
including environment setup, running prompts, and reading output.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import Orchestrator
from coding_agents import CodingAgentIdeType


class TestWorkflow:
    """Simple test workflow for end-to-end agent testing"""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
    
    def create_test_prompt(self) -> str:
        """Create a simple test prompt that asks the agent to print hello world"""
        return """Please create a simple Python script that prints "hello world" to test the coding agent functionality.

## Task Details
1. Create a file called `test_hello.py` in the current directory
2. The file should contain a simple Python script that prints "hello world"
3. Add a comment explaining that this is a test script
4. Confirm that the file was created successfully

## Expected Output
The script should simply print: hello world

This is a basic test to verify that the coding agent can:
- Create files
- Write simple code
- Provide confirmation of completed tasks

Please implement this simple task and confirm completion."""
    
    async def execute_test(self, agent_type: CodingAgentIdeType, repo_url: str = None, 
                          project_path: str = None) -> str:
        """Execute the test workflow"""
        print("Starting test workflow execution...")
        
        # Use current directory if no repo_url provided
        if not repo_url:
            repo_url = "test_repo"
        
        test_prompt = self.create_test_prompt()
        print(f"Test prompt: {test_prompt[:100]}...")
        
        # Create single-agent request using unified orchestrator
        request = Orchestrator.create_single_agent_request(
            task_description=test_prompt,
            agent_type=agent_type.value,
            workflow_type="test",
            repo_url=repo_url,
            work_directory=project_path
        )
        
        response = await self.orchestrator.execute_task(request)
        return response.final_output
    
    async def execute_simple_hello_world(self, agent_type: CodingAgentIdeType, 
                                        project_path: str = None) -> str:
        """Execute a very simple hello world test without repository context"""
        simple_prompt = """Create a Python file called 'hello_world.py' that prints "hello world" when executed. 
        
Please:
1. Create the file
2. Add the print statement
3. Confirm the file was created
4. Show me the content of the file

This is a simple test of the agent's basic functionality."""
        
        print("Executing simple hello world test...")
        print(f"Working directory: {project_path or os.getcwd()}")
        
        # Create single-agent request using unified orchestrator
        request = Orchestrator.create_single_agent_request(
            task_description=simple_prompt,
            agent_type=agent_type.value,
            workflow_type="test",
            repo_url="test_simple",
            work_directory=project_path
        )
        
        response = await self.orchestrator.execute_task(request)
        return response.final_output