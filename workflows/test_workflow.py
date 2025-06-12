#!/usr/bin/env python3
"""
Test Workflow Module

A simple test workflow that prints "hello world" to test agent end-to-end execution,
including environment setup, running prompts, and reading output.
"""

class TestWorkflow:
    """Simple test workflow prompt generator for end-to-end agent testing"""
    
    def __init__(self):
        pass
    
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
    
    def create_simple_hello_world_prompt(self) -> str:
        """Create a very simple hello world test prompt without repository context"""
        return """Create a Python file called 'hello_world.py' that prints "hello world" when executed. 
        
Please:
1. Create the file
2. Add the print statement
3. Confirm the file was created
4. Show me the content of the file

This is a simple test of the agent's basic functionality."""