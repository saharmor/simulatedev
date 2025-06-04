#!/usr/bin/env python3
"""
Code Optimization Workflow Module

This module provides specialized functionality for finding and implementing
code optimizations, performance improvements, and refactoring opportunities.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_orchestrator import AgentOrchestrator
from coding_agents import CodingAgentType


class CodeOptimizer(AgentOrchestrator):
    """Specialized orchestrator for code optimization workflows"""
    
    def generate_performance_analysis_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding performance optimization opportunities"""
        return f"""You are a senior performance engineer analyzing code for optimization opportunities. Your task is to identify and implement performance improvements.

## Analysis Focus Areas
1. **Algorithm Complexity**: Look for O(n²) or worse algorithms that can be optimized
2. **Database Queries**: Identify N+1 queries, missing indexes, or inefficient queries
3. **Memory Usage**: Find memory leaks, unnecessary object creation, or large allocations
4. **I/O Operations**: Optimize file operations, network calls, or blocking operations
5. **Caching Opportunities**: Identify where caching could improve performance
6. **Inefficient Loops**: Find loops that can be optimized or eliminated

## Repository
Working on: {repo_url}

## Instructions
- First, scan the codebase to understand the architecture
- Identify the most impactful optimization opportunities (low-hanging fruit first)
- Implement 2-3 optimizations that will provide the biggest performance gains
- Add comments explaining the optimization rationale
- Ensure optimizations don't break existing functionality
- Provide before/after explanations for each optimization

Please proceed with your analysis and implementation."""

    def generate_refactoring_prompt(self, repo_url: str) -> str:
        """Generate a prompt for code refactoring and cleanup"""
        return f"""You are an expert software architect tasked with improving code quality and maintainability.

## Refactoring Focus Areas
1. **Code Duplication**: Identify and eliminate duplicate code
2. **Long Methods/Functions**: Break down complex functions into smaller ones
3. **Naming**: Improve variable, function, and class names for clarity
4. **Code Structure**: Reorganize code for better modularity
5. **Design Patterns**: Apply appropriate design patterns where beneficial
6. **Error Handling**: Improve error handling and edge case management

## Repository
Working on: {repo_url}

## Instructions
- Analyze the codebase for maintainability issues
- Focus on changes that improve readability and reduce complexity
- Implement 3-5 refactoring improvements
- Ensure all refactoring maintains existing functionality
- Add documentation where it improves understanding
- Follow the existing code style and conventions

Please proceed with your refactoring analysis and implementation."""

    def generate_low_hanging_fruit_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding easy wins and quick improvements"""
        return f"""You are a pragmatic developer looking for quick wins and easy improvements that can be implemented with minimal risk.

## Low-Hanging Fruit Focus
1. **Simple Bug Fixes**: Fix obvious bugs or edge cases
2. **Code Cleanup**: Remove commented code, unused imports, dead code
3. **Quick Performance Wins**: Simple optimizations with big impact
4. **Missing Error Handling**: Add basic error handling where obviously missing
5. **Documentation**: Add missing docstrings or comments for confusing code
6. **Type Hints**: Add type hints where they improve code clarity
7. **Configuration**: Move hardcoded values to configuration

## Repository
Working on: {repo_url}

## Selection Criteria
- Must be implementable in under 30 minutes each
- Low risk of breaking existing functionality
- High visibility/impact improvements
- Clear benefit to code quality or performance

## Instructions
- Identify 5-8 low-hanging fruit improvements
- Implement the changes with clear commit messages
- Focus on changes that future developers will appreciate
- Avoid anything that requires extensive testing or design decisions

Please proceed with identifying and implementing these quick wins."""

    async def optimize_performance(self, agent_type: CodingAgentType, repo_url: str, 
                                  project_path: str = None) -> str:
        """Execute a performance optimization workflow"""
        prompt = self.generate_performance_analysis_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)
    
    async def refactor_code(self, agent_type: CodingAgentType, repo_url: str, 
                           project_path: str = None) -> str:
        """Execute a code refactoring workflow"""
        prompt = self.generate_refactoring_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)
    
    async def find_low_hanging_fruit(self, agent_type: CodingAgentType, repo_url: str, 
                                    project_path: str = None) -> str:
        """Execute a low-hanging fruit identification and implementation workflow"""
        prompt = self.generate_low_hanging_fruit_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path) 