#!/usr/bin/env python3
"""
Base Role Module

This module defines the abstract base class for all agent roles in the multi-agent system.
Each role (Planner, Coder, Tester) inherits from this base class and implements
role-specific prompt generation and execution logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from agents import AgentDefinition, AgentContext, AgentRole


class BaseRole(ABC):
    """Abstract base class for all agent roles"""
    
    def __init__(self, role: AgentRole):
        self.role = role
    
    @abstractmethod
    def create_prompt(self, task: str, context: AgentContext, 
                     agent_definition: AgentDefinition) -> str:
        """
        Create a role-specific prompt for the agent.
        
        Args:
            task: The main task description
            context: Current execution context with previous outputs
            agent_definition: Definition of the agent to execute
            
        Returns:
            str: The formatted prompt for this role
        """
        pass
    
    def get_role_description(self) -> str:
        """Get a human-readable description of this role"""
        return f"{self.role.value.title()} Role"
    
    def should_retry_on_failure(self) -> bool:
        """Determine if this role should be retried on failure"""
        return True
    
    def get_max_retries(self) -> int:
        """Get the maximum number of retries for this role"""
        return 1
    
    def post_execution_hook(self, result: Dict[str, Any], 
                          context: AgentContext) -> Dict[str, Any]:
        """
        Hook called after agent execution to modify or validate results.
        
        Args:
            result: The execution result from the agent
            context: Current execution context
            
        Returns:
            Dict[str, Any]: Modified result (or original if no changes)
        """
        return result 