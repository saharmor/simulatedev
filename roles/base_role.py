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
    
    def create_prompt_with_workflow(self, task: str, context: AgentContext, 
                                  agent_definition: AgentDefinition, 
                                  workflow_type: str = None) -> str:
        """
        Create a workflow-aware role-specific prompt for the agent.
        
        Args:
            task: The main task description
            context: Current execution context with previous outputs
            agent_definition: Definition of the agent to execute
            workflow_type: Type of workflow (bug_hunting, code_optimization, etc.)
            
        Returns:
            str: The formatted prompt for this role with workflow context
        """
        # Default implementation calls standard create_prompt
        # Subclasses can override this for workflow-specific behavior
        base_prompt = self.create_prompt(task, context, agent_definition)
        
        if workflow_type:
            workflow_context = self._get_workflow_context(workflow_type)
            if workflow_context:
                base_prompt = f"{workflow_context}\n\n{base_prompt}"
        
        return base_prompt
    
    def _get_workflow_context(self, workflow_type: str) -> str:
        """Get workflow-specific context for prompt generation"""
        workflow_contexts = {
            "bug_hunting": f"""
## WORKFLOW CONTEXT: BUG HUNTING
You are working on a bug hunting and security vulnerability detection workflow.
Focus on finding and fixing security issues, bugs, and potential vulnerabilities.
Prioritize code safety, error handling, and security best practices.
""",
            "code_optimization": f"""
## WORKFLOW CONTEXT: CODE OPTIMIZATION  
You are working on a code optimization and performance improvement workflow.
Focus on improving performance, reducing complexity, and enhancing code quality.
Look for opportunities to optimize algorithms, reduce memory usage, and improve efficiency.
""",
            "general_coding": f"""
## WORKFLOW CONTEXT: GENERAL CODING
You are working on a general coding task.
Focus on implementing clean, maintainable, and well-documented code.
Follow best practices and ensure the solution meets the specified requirements.
"""
        }
        
        return workflow_contexts.get(workflow_type, "")
    
    def get_role_description(self) -> str:
        """Get a human-readable description of this role"""
        return f"{self.role.value.title()} Role"
    

    
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