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

from src.agent_orchestrator import AgentOrchestrator
from coding_agents import CodingAgentIdeType


class CodeOptimizer(AgentOrchestrator):
    """Specialized orchestrator for code optimization workflows"""
    
    def generate_low_hanging_fruit_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing one high-value, easy improvement"""
        return f"""You are a senior staff engineer identifying high-impact improvements that demonstrate technical excellence while remaining achievable in a single PR.

## Repository
Working on: {repo_url}

## Advanced Low-Hanging Fruit Process

### Phase 1: MAPPING - Sophisticated Improvement Discovery
Analyze the codebase for improvements demonstrating technical depth:

1. **Performance Optimizations**:
   - Database: N+1 queries, missing indexes, inefficient joins, connection pooling
   - Algorithms: O(n²) to O(n log n) conversions, missing memoization
   - I/O: Async/await conversions, lazy loading, caching expensive operations

2. **Security Hardening**:
   - Rate limiting, input sanitization, CSRF protection
   - Secure headers (CSP, HSTS), cryptographically secure random
   - Session timeout, constant-time comparisons

3. **Error Handling & Resilience**:
   - Circuit breakers, retry with exponential backoff
   - Error boundaries, structured responses, timeout handling
   - Graceful degradation, dead letter queues

4. **Type Safety & Code Contracts**:
   - TypeScript types, runtime validation (Zod/Joi)
   - Type guards, generic constraints, branded types
   - Exhaustive switch statements

5. **API & Data Model Improvements**:
   - Pagination, GraphQL resolvers, database indexes
   - Soft deletes, audit trails, API versioning
   - OpenAPI documentation

6. **Developer Experience**:
   - Custom hooks/utilities, comprehensive JSDoc
   - Builder patterns, type-safe event emitters
   - Feature flags, telemetry hooks

7. **Architecture & Design Patterns**:
   - Dependency injection, facade patterns, adapters
   - Repository patterns, CQRS lite, domain events
   - Strategy patterns

### Phase 2: RANKING - Professional Impact Assessment
Score each improvement (1-10):

**Implementation Feasibility:**
- Implementable in 1-3 files with established patterns
- Backward compatible and easily testable
- Low regression risk

**Professional Impressiveness:**
- Impresses staff/principal engineers
- Shows system-level thinking and best practices
- Measurable impact and prevents future issues

**Final Score = (Feasibility × 0.4) + (Impressiveness × 0.6)**

### Phase 3: SELECTION - Choose the Most Impressive Improvement
Select improvement demonstrating:
- Senior+ engineering judgment and production system understanding
- Industry best practices with measurable positive impact

### Phase 4: IMPLEMENTATION - Production-Quality Code
1. Implement using best practices and design patterns
2. Add comprehensive tests and detailed documentation
3. Include metrics/logging and consider backward compatibility
4. Follow SOLID principles with performance benchmarks if applicable

## Output Format
```
# ADVANCED IMPROVEMENT ANALYSIS

## PHASE 1: MAPPING
[List sophisticated improvements with technical details]

## PHASE 2: RANKING
[Show detailed scoring with professional justification]

## PHASE 3: SELECTION
**CHOSEN IMPROVEMENT:** [Technical name with value proposition]
**BUSINESS IMPACT:** [Quantifiable benefits]
**TECHNICAL APPROACH:** [Industry-standard pattern used]
**METRICS:** [Success measurement approach]

## PHASE 4: IMPLEMENTATION
[Production-quality code with comprehensive explanation]
```

## Guidelines
- Focus on senior+ engineering skills, avoid trivial changes
- Choose measurable business/technical impact improvements
- Use established patterns, make PR compelling with clear benefits
- Ensure production-ready code, not proof of concept

Please proceed with this advanced improvement analysis."""

    def generate_performance_optimization_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing one high-value performance optimization"""
        return f"""You are a principal performance engineer identifying sophisticated performance optimizations that deliver measurable impact. Find improvements demonstrating deep technical knowledge while remaining implementable in a single PR.

## Repository
Working on: {repo_url}

## Advanced Performance Optimization Process

### Phase 1: MAPPING - Performance Analysis
Identify high-impact optimization opportunities:

1. **Database & Query**: N+1 queries, missing indexes, inefficient pagination, connection pooling
2. **Algorithms**: Quadratic algorithms, poor data structures, missing memoization, unnecessary loops
3. **Memory & I/O**: Memory leaks, large allocations in hot paths, missing streaming, inefficient I/O
4. **Concurrency**: Sequential operations that could be parallel, blocking I/O, missing async patterns
5. **Caching**: Missing HTTP caching, expensive computations without memoization, cache strategies
6. **Network**: Missing compression, inefficient serialization, unnecessary API round trips
7. **Frontend**: Missing React.memo, unnecessary re-renders, missing virtualization, blocking JS

### Phase 2: RANKING - Impact Assessment
Score each optimization (1-10):

**Implementation Feasibility:**
- Testable and implementable by automated agent without supervision
- Impresses senior engineers with deep understanding and real production impact

**Performance Impact:**
- Expected improvement >20%
- Demonstrates deep system knowledge
- Reduces infrastructure costs or improves UX

**Final Score = (Feasibility × 0.4) + (Impact × 0.6)**

### Phase 3: SELECTION - Choose High-Impact Optimization
Select optimization with:
- Significant measurable gains (>20% improvement)
- Professional implementation approach
- Clear before/after metrics

### Phase 4: IMPLEMENTATION - Production-Grade Code
1. Implement using performance best practices
2. Add benchmarks showing before/after metrics
3. Include performance tests and monitoring for production validation
4. Document optimization approach

## Output Format
```
# ADVANCED PERFORMANCE OPTIMIZATION ANALYSIS

## PHASE 1: MAPPING
[List sophisticated optimization opportunities with technical details]

## PHASE 2: RANKING
[Show detailed scoring with performance projections]

## PHASE 3: SELECTION
**CHOSEN OPTIMIZATION:** [Technical description with expected gains]
**PERFORMANCE METRICS:** [Specific before/after measurements expected]
**TECHNICAL APPROACH:** [Detailed explanation of optimization technique]
**RISK ASSESSMENT:** [Potential downsides and mitigation strategies]

## PHASE 4: IMPLEMENTATION
[Production-quality implementation with benchmarks and explanation]
```

## Guidelines
- Focus on principal-level thinking, avoid micro-optimizations
- Choose optimizations with measurable, significant improvements (>20%)
- Use established performance engineering patterns
- Include benchmarks and consider both latency and throughput
- Ensure optimization is maintainable and well-documented

Please proceed with this advanced performance optimization analysis."""

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

    async def optimize_performance(self, agent_type: CodingAgentIdeType, repo_url: str, 
                                  project_path: str = None) -> str:
        """Execute a performance optimization workflow that maps, ranks, and implements one high-value optimization"""
        prompt = self.generate_performance_optimization_prompt(repo_url)
        agent_execution_report_summary = await self.execute_workflow(agent_type, repo_url, prompt, project_path)
        return agent_execution_report_summary
    
    async def refactor_code(self, agent_type: CodingAgentIdeType, repo_url: str, 
                           project_path: str = None) -> str:
        """Execute a code refactoring workflow"""
        prompt = self.generate_refactoring_prompt(repo_url)
        agent_execution_report_summary = await self.execute_workflow(agent_type, repo_url, prompt, project_path)
        return agent_execution_report_summary
    
    async def find_low_hanging_fruit(self, agent_type: CodingAgentIdeType, repo_url: str, 
                                    project_path: str = None) -> str:
        """Execute a low-hanging fruit workflow that maps, ranks, and implements one high-value improvement"""
        prompt = self.generate_low_hanging_fruit_prompt(repo_url)
        agent_execution_report_summary = await self.execute_workflow(agent_type, repo_url, prompt, project_path) 
        return agent_execution_report_summary