#!/usr/bin/env python3
"""
General Coding Workflow Module

This module provides the default workflow for handling user-provided coding prompts,
extending the unified orchestrator with general-purpose coding functionality.
"""


class GeneralCodingWorkflow:
    """General-purpose prompt generator for user-defined coding tasks"""
    
    def __init__(self):
        pass
    
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
    
    def create_simple_prompt(self, user_request: str) -> str:
        """Create a simple, direct prompt without additional enhancement"""
        return user_request