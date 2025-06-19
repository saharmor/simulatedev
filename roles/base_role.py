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
        
        # Always append file management guidelines
        base_prompt = self.append_file_management_guidelines(base_prompt)
        
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
            "custom_coding": f"""
## WORKFLOW CONTEXT: CUSTOM CODING
You are working on a custom coding task.
Focus on implementing clean, maintainable, and well-documented code.
Follow best practices and ensure the solution meets the specified requirements.
"""
        }
        
        return workflow_contexts.get(workflow_type, "")
    
    def _get_file_management_guidelines(self) -> str:
        """Get file management guidelines to prevent unwanted commits"""
        return """
## FILE MANAGEMENT RULES

**DO NOT CREATE:**
- Summary markdown files (CHANGES.md, SUMMARY.md, IMPLEMENTATION.md, etc.)
- Temporary files (test_temp.py, debug.log, temp_*, *_temp.*, scratch_*)
- Exception: Only if explicitly required as deliverables

**CREATE ONLY:**
- Source code files (.py, .js, .html, .css, etc.)
- Config files (requirements.txt, package.json, etc.)
- Documentation only if explicitly requested
- Test files only if required as deliverables

**COMMIT HYGIENE:** Review staged files - include only necessary files for functionality.
"""
    
    def get_role_description(self) -> str:
        """Get a human-readable description of this role"""
        return f"{self.role.value.title()} Role"
    
    def append_file_management_guidelines(self, prompt: str) -> str:
        """
        Append file management guidelines to any prompt.
        This should be called by all role implementations.
        
        Args:
            prompt: The base prompt to append guidelines to
            
        Returns:
            str: The prompt with file management guidelines appended
        """
        file_guidelines = self._get_file_management_guidelines()
        return f"{prompt}\n\n{file_guidelines}"
    
    def get_gitignore_patterns_for_unwanted_files(self) -> list:
        """
        Get .gitignore patterns for files that should not be committed.
        
        Returns:
            list: List of gitignore patterns
        """
        return [
            # Markdown summary files
            "*SUMMARY*.md",
            "*CHANGES*.md", 
            "*IMPLEMENTATION*.md",
            "*summary*.md",
            "*changes*.md",
            "*implementation*.md",
            
            # Temporary testing files
            "test_temp*",
            "temp_test*",
            "*_temp.*",
            "*_temporary.*",
            "debug_*",
            "scratch_*",
            "temp.*",
            "*.tmp",
            
            # Log files that might be created during testing
            "debug.log",
            "test.log",
            "temp.log",
            "scratch.log"
        ]
    
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