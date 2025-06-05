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
    
    def generate_low_hanging_fruit_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing one high-value, easy improvement"""
        return f"""You are a pragmatic senior developer with expertise in identifying and implementing quick wins that deliver maximum value with minimal risk. Your task is to systematically find and implement one high-impact, easily achievable improvement.

## Repository
Working on: {repo_url}

## Low-Hanging Fruit Process

### Phase 1: MAPPING - Comprehensive Opportunity Discovery
First, scan the entire codebase to identify ALL potential low-hanging fruit improvements. Look for:

1. **Quick Bug Fixes**: Simple logical errors, obvious edge cases, typos in code
2. **Code Cleanup**: Unused imports, commented-out code, dead functions, inconsistent formatting
3. **Performance Quick Wins**: Simple optimizations with big impact (caching, avoiding loops, etc.)
4. **Missing Error Handling**: Basic try-catch blocks, null checks, input validation
5. **Documentation Gaps**: Missing docstrings, unclear variable names, confusing logic
6. **Type Safety**: Missing type hints in Python/TypeScript, obvious type mismatches
7. **Configuration Improvements**: Hardcoded values that should be configurable
8. **Security Quick Wins**: Simple security improvements (input sanitization, secure defaults)
9. **Code Readability**: Complex one-liners that could be simplified, magic numbers
10. **Best Practices**: Missing const declarations, inconsistent naming, simple refactors

Create a comprehensive list of ALL potential improvements you find.

### Phase 2: RANKING - Prioritization
For each improvement found, evaluate it on these criteria:

**Implementation Likelihood (1-10 scale):**
- How simple is the implementation? (1-5 line changes score 10, complex changes score lower)
- How localized is the change? (single file/function scores higher)
- How confident are you that you can implement it perfectly? (higher confidence scores higher)
- Is it a well-established pattern/fix? (common patterns score higher)
- Risk of breaking existing functionality? (lower risk scores higher)

**Impact & Impressiveness (1-10 scale):**
- How visible is the improvement to users/developers? (more visible scores higher)
- How much does it improve code quality/maintainability? (more improvement scores higher)
- How much does it improve performance/security? (more improvement scores higher)
- How professionally impressive is this improvement? (more impressive scores higher)
- How much technical debt does it remove? (more debt removal scores higher)

**Combined Score Calculation:**
- Final Score = (Implementation Likelihood × 0.7) + (Impact & Impressiveness × 0.3)
- This heavily prioritizes achievable improvements while still valuing impact

### Phase 3: SELECTION - Choose the Best Candidate
Select the improvement with the highest combined score. This should be:
- Something you can implement confidently in under 30 minutes
- Low risk of introducing bugs or breaking functionality
- Provides clear, measurable value to the codebase
- Demonstrates professional development practices

### Phase 4: IMPLEMENTATION - Implement the Selected Improvement
For the chosen improvement:
1. Implement a complete, production-ready solution
2. Add appropriate comments explaining the improvement
3. Follow existing code style and conventions
4. Ensure the change integrates seamlessly with existing code
5. Test the change if possible within the codebase

## Output Format
Structure your response as follows:

```
# LOW-HANGING FRUIT ANALYSIS

## PHASE 1: MAPPING
[List all potential improvements found with brief descriptions]

## PHASE 2: RANKING
[For each improvement, show the scoring breakdown]

## PHASE 3: SELECTION
**CHOSEN IMPROVEMENT:** [Name/description of selected improvement]
**REASONING:** [Why this improvement was selected based on the scoring criteria]

## PHASE 4: IMPLEMENTATION
[Implement the improvement with clear explanation of changes made]
```

## Important Guidelines
- Focus on changes that any senior developer would obviously approve
- Prioritize improvements that make the codebase more maintainable
- Avoid anything that requires extensive testing or design decisions
- Choose improvements that demonstrate clear professional value
- Ensure your implementation is complete and production-ready

Please proceed with this low-hanging fruit identification and implementation process."""

    def generate_performance_optimization_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing one high-value performance optimization"""
        return f"""You are a senior performance engineer with expertise in identifying and implementing performance optimizations autonomously. Your task is to systematically find and implement one high-impact, achievable performance improvement.

## Repository
Working on: {repo_url}

## Performance Optimization Process

### Phase 1: MAPPING - Comprehensive Performance Analysis
First, scan the entire codebase to identify ALL potential performance optimization opportunities. Look for:

1. **Algorithm Complexity**: O(n²) or worse algorithms that can be optimized to O(n log n) or O(n)
2. **Database Issues**: N+1 queries, missing indexes, inefficient queries, unnecessary joins
3. **Memory Inefficiencies**: Memory leaks, unnecessary object creation, large allocations
4. **I/O Bottlenecks**: Synchronous operations that could be async, file I/O optimizations
5. **Caching Opportunities**: Repeated calculations, expensive operations that could be cached
6. **Loop Optimizations**: Inefficient loops, nested loops that could be flattened
7. **Data Structure Inefficiencies**: Wrong data structures for the use case
8. **Lazy Loading**: Missing lazy loading where it would help
9. **Resource Management**: Unclosed resources, inefficient resource usage

Create a comprehensive list of ALL performance optimization opportunities you find.

### Phase 2: RANKING - Prioritization
For each optimization found, evaluate it on these criteria:

**Implementation Likelihood (1-10 scale):**
- How complex is the optimization? (simple changes score higher)
- How well-contained is the change? (localized optimizations score higher)
- How confident are you that you can implement it without breaking functionality? (higher confidence scores higher)
- Are there clear, established patterns for this optimization? (yes scores higher)

**Impact & Impressiveness (1-10 scale):**
- How significant is the performance improvement? (bigger improvements score higher)
- How measurable is the improvement? (easily measurable scores higher)
- How technically impressive is this optimization? (more impressive scores higher)
- How much does it improve user experience? (more improvement scores higher)

**Combined Score Calculation:**
- Final Score = (Implementation Likelihood × 0.6) + (Impact & Impressiveness × 0.4)
- This prioritizes achievable optimizations while still valuing high-impact improvements

### Phase 3: SELECTION - Choose the Best Candidate
Select the optimization with the highest combined score. This should be:
- Something you can confidently implement end-to-end
- Provides measurable performance improvement
- Low risk of introducing bugs or architectural issues

### Phase 4: IMPLEMENTATION - Implement the Selected Optimization
For the chosen optimization:
1. Implement a complete, working optimization
2. Add clear comments explaining the performance improvement
3. Ensure the optimization doesn't break existing functionality
4. Follow existing code style and conventions
5. Document the expected performance gain

## Output Format
Structure your response as follows:

```
# PERFORMANCE OPTIMIZATION ANALYSIS

## PHASE 1: MAPPING
[List all optimization opportunities found with brief descriptions]

## PHASE 2: RANKING
[For each optimization, show the scoring breakdown]

## PHASE 3: SELECTION
**CHOSEN OPTIMIZATION:** [Name/description of selected optimization]
**REASONING:** [Why this optimization was selected based on the scoring criteria]

## PHASE 4: IMPLEMENTATION
[Implement the optimization with clear explanation of changes made]
```

## Important Notes
- Focus on optimizations you can implement confidently and completely
- Prioritize changes that provide clear, measurable performance benefits
- Avoid optimizations that require extensive architectural changes
- Ensure your implementation is production-ready and well-tested

Please proceed with this performance optimization process."""

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

    async def optimize_performance(self, agent_type: CodingAgentType, repo_url: str, 
                                  project_path: str = None) -> str:
        """Execute a performance optimization workflow that maps, ranks, and implements one high-value optimization"""
        prompt = self.generate_performance_optimization_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)
    
    async def refactor_code(self, agent_type: CodingAgentType, repo_url: str, 
                           project_path: str = None) -> str:
        """Execute a code refactoring workflow"""
        prompt = self.generate_refactoring_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)
    
    async def find_low_hanging_fruit(self, agent_type: CodingAgentType, repo_url: str, 
                                    project_path: str = None) -> str:
        """Execute a low-hanging fruit workflow that maps, ranks, and implements one high-value improvement"""
        prompt = self.generate_low_hanging_fruit_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path) 