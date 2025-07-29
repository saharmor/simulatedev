#!/usr/bin/env python3
"""
Custom Exception Classes for SimulateDev

This module defines custom exceptions used throughout the SimulateDev codebase
for better error handling and more specific exception catching.
"""


class SimulateDevException(Exception):
    """Base exception class for all SimulateDev-related errors"""
    pass


class AgentTimeoutException(SimulateDevException):
    """Exception raised when an AI coding agent times out during execution"""
    
    def __init__(self, agent_name: str, timeout_seconds: int, message: str = None):
        self.agent_name = agent_name
        self.timeout_seconds = timeout_seconds
        
        if message is None:
            message = f"{agent_name} did not complete within {timeout_seconds} seconds. This may indicate the task was too complex or the agent encountered an issue."
        
        super().__init__(message)
        
    def get_user_friendly_message(self) -> str:
        """Get a user-friendly explanation of the timeout"""
        return f"""TIMEOUT: The {self.agent_name} agent timed out.
The agent did not complete the task within the expected timeframe ({self.timeout_seconds} seconds).
This could happen for several reasons:
  • The task was more complex than anticipated
  • The repository structure was difficult to analyze

You can try:
  • Running the command again (sometimes it works on retry)
  • Using a different agent (cursor, windsurf, claude_cli, etc.)
  • Breaking down the task into smaller parts
"""


class WorkflowTimeoutException(SimulateDevException):
    """Exception raised when a workflow times out during execution"""
    
    def __init__(self, workflow_type: str, agent_name: str, timeout_seconds: int, message: str = None):
        self.workflow_type = workflow_type
        self.agent_name = agent_name
        self.timeout_seconds = timeout_seconds
        
        if message is None:
            message = f"The {workflow_type} workflow using {agent_name} timed out after {timeout_seconds} seconds"
        
        super().__init__(message)
        
    def get_user_friendly_message(self) -> str:
        """Get a user-friendly explanation of the workflow timeout"""
        return f"""TIMEOUT: The {self.workflow_type} workflow timed out.
The {self.agent_name} agent did not complete the task within the expected timeframe ({self.timeout_seconds} seconds).
This could happen for several reasons:
  • The task was more complex than anticipated
  • The repository structure was difficult to analyze

You can try:
  • Running the workflow again (sometimes it works on retry)
  • Using a different agent (cursor, windsurf, claude_cli, etc.)
  • Breaking down the task into smaller parts
"""


class AgentExecutionException(SimulateDevException):
    """Exception raised when an agent fails to execute properly (non-timeout related)"""
    
    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        super().__init__(f"Agent {agent_name} execution failed: {message}")


class RepositoryException(SimulateDevException):
    """Exception raised for repository-related errors"""
    pass


class IDEException(SimulateDevException):
    """Exception raised for IDE-related errors"""
    pass 