#!/usr/bin/env python3
"""
General Coding Workflow Module

This module provides the default workflow for handling user-provided coding prompts,
extending the unified orchestrator with general-purpose coding functionality.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import Orchestrator
from coding_agents import CodingAgentIdeType


class GeneralCodingWorkflow:
    """General-purpose orchestrator for user-defined coding tasks"""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
    
    def enhance_user_prompt(self, user_prompt: str, repo_url: str) -> str:
        """Enhance a user prompt with additional context and instructions"""
        enhanced_prompt = f"""You are an expert developer working on a codebase. Please help with the following task:

## Task
{user_prompt}

## Instructions
- Analyze the codebase structure first to understand the project
- Implement the changes following the existing code style and patterns
- Add appropriate comments and documentation
- Ensure your changes are compatible with existing functionality
- Test your implementation if applicable
- Provide a brief explanation of what you did

## Repository
Working on: {repo_url}

Please proceed with implementing this task."""
        
        return enhanced_prompt
    
    async def execute_coding_task(self, agent_type: CodingAgentIdeType, repo_url: str, 
                                 user_prompt: str, project_path: str = None) -> str:
        """Execute a general coding task workflow"""
        enhanced_prompt = self.enhance_user_prompt(user_prompt, repo_url)
        
        # Create single-agent request using unified orchestrator
        request = Orchestrator.create_single_agent_request(
            task_description=enhanced_prompt,
            agent_type=agent_type.value,
            workflow_type="general_coding",
            repo_url=repo_url,
            work_directory=project_path
        )
        
        response = await self.orchestrator.execute_task(request)
        return response.final_output
    
    def create_simple_prompt(self, user_request: str) -> str:
        """Create a simple, direct prompt without additional enhancement"""
        return user_request
    
    async def execute_simple_task(self, agent_type: CodingAgentIdeType, repo_url: str,
                                 user_prompt: str, project_path: str = None) -> str:
        """Execute a simple task without prompt enhancement"""
        # Create single-agent request using unified orchestrator
        request = Orchestrator.create_single_agent_request(
            task_description=user_prompt,
            agent_type=agent_type.value,
            workflow_type="general_coding",
            repo_url=repo_url,
            work_directory=project_path
        )
        
        response = await self.orchestrator.execute_task(request)
        return response.final_output