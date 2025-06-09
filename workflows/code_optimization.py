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
        return f"""You are a senior staff engineer with expertise in identifying high-impact improvements that demonstrate technical excellence while remaining achievable in a single PR. Your task is to find sophisticated yet implementable improvements that would impress code reviewers.

## Repository
Working on: {repo_url}

## Advanced Low-Hanging Fruit Process

### Phase 1: MAPPING - Sophisticated Improvement Discovery
Analyze the codebase for improvements that demonstrate technical depth and professional engineering. Focus on:

1. **Performance Optimizations with Measurable Impact**:
   - Database query optimizations (N+1 queries, missing indexes, inefficient joins)
   - Caching opportunities for expensive computations or API calls
   - Algorithmic improvements (O(n²) to O(n log n) conversions)
   - Memory allocation optimizations in hot paths
   - Async/await conversions for blocking I/O operations
   - Connection pooling implementations
   - Lazy loading for heavy resources

2. **Security Hardening**:
   - Adding rate limiting to prevent abuse
   - Implementing proper input sanitization
   - Adding CSRF protection where missing
   - Secure headers implementation (CSP, HSTS, etc.)
   - Replacing insecure random with cryptographically secure alternatives
   - Adding constant-time string comparisons for secrets
   - Implementing proper session timeout handling

3. **Error Handling & Resilience**:
   - Circuit breaker patterns for external service calls
   - Retry logic with exponential backoff
   - Graceful degradation for feature flags
   - Proper error boundaries in React/frontend code
   - Structured error responses with appropriate status codes
   - Dead letter queue implementations
   - Timeout handling for long-running operations

4. **Type Safety & Code Contracts**:
   - Adding comprehensive TypeScript types to JavaScript code
   - Implementing runtime validation with libraries like Zod/Joi
   - Adding generic constraints to prevent type errors
   - Creating type guards for external data
   - Implementing branded types for domain modeling
   - Adding exhaustive switch statements with never types

5. **API & Data Model Improvements**:
   - Adding pagination to unbounded list endpoints
   - Implementing field-level GraphQL resolvers
   - Adding database migrations for missing indexes
   - Implementing soft deletes where appropriate
   - Adding audit trails for sensitive operations
   - Versioning APIs properly
   - Adding OpenAPI/Swagger documentation

6. **Developer Experience Enhancements**:
   - Creating custom hooks/utilities for repeated patterns
   - Adding comprehensive JSDoc with examples
   - Implementing builder patterns for complex objects
   - Creating type-safe event emitters
   - Adding telemetry/observability hooks
   - Implementing feature flags infrastructure
   - Creating development mode helpers

7. **Architecture & Design Patterns**:
   - Implementing dependency injection for better testability
   - Adding facade patterns for complex subsystems
   - Creating adapters for third-party integrations
   - Implementing repository patterns for data access
   - Adding command/query separation (CQRS lite)
   - Creating domain events for decoupling
   - Implementing strategy patterns for algorithms

### Phase 2: RANKING - Professional Impact Assessment
For each improvement found, evaluate it on these criteria:

**Implementation Feasibility (1-10 scale):**
- Can it be implemented in 1-3 files? (more contained scores higher)
- Is there a clear, well-established pattern? (established patterns score higher)
- Can it be done without breaking changes? (backward compatible scores higher)
- Is it testable with existing infrastructure? (easily testable scores higher)
- Risk of introducing regressions? (lower risk scores higher)

**Professional Impressiveness (1-10 scale):**
- Would this impress a staff/principal engineer? (more impressive scores higher)
- Does it demonstrate system-level thinking? (holistic thinking scores higher)
- Does it show knowledge of best practices? (best practices score higher)
- Would it improve metrics (performance/reliability)? (measurable impact scores higher)
- Does it prevent future bugs/issues? (preventive measures score higher)
- Is this something that shows "senior+" level thinking? (advanced thinking scores higher)

**Combined Score Calculation:**
- Final Score = (Implementation Feasibility × 0.4) + (Professional Impressiveness × 0.6)
- This prioritizes impressive improvements while ensuring they're achievable

### Phase 3: SELECTION - Choose the Most Impressive Improvement
Select the improvement that best demonstrates:
- Senior+ level engineering judgment
- Understanding of production systems
- Knowledge of industry best practices
- Measurable positive impact
- Clean, maintainable implementation

### Phase 4: IMPLEMENTATION - Production-Quality Code
For the chosen improvement:
1. Implement using industry best practices and design patterns
2. Add comprehensive tests including edge cases
3. Include detailed documentation explaining the improvement
4. Add metrics/logging to measure the impact
5. Consider backward compatibility and migration paths
6. Follow SOLID principles and clean code practices
7. Include performance benchmarks if applicable

## Output Format
Structure your response as follows:

```
# ADVANCED IMPROVEMENT ANALYSIS

## PHASE 1: MAPPING
[List all sophisticated improvements with technical details]

## PHASE 2: RANKING
[For each improvement, show detailed scoring with professional justification]

## PHASE 3: SELECTION
**CHOSEN IMPROVEMENT:** [Technical name with clear value proposition]
**BUSINESS IMPACT:** [Quantifiable benefits - performance, reliability, security]
**TECHNICAL APPROACH:** [Industry-standard pattern or technique used]
**METRICS:** [How to measure the improvement's success]

## PHASE 4: IMPLEMENTATION
[Production-quality code with comprehensive explanation]
```

## Important Guidelines
- Focus on improvements that demonstrate senior+ engineering skills
- Avoid trivial changes like renaming variables or removing comments
- Choose improvements with measurable business/technical impact
- Implement using established patterns and best practices
- Make the PR compelling with clear before/after benefits
- Include enough context to educate reviewers on the approach
- Ensure the code is production-ready, not a proof of concept

Please proceed with this advanced improvement analysis."""

    def generate_performance_optimization_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing one high-value performance optimization"""
        return f"""You are a principal performance engineer with expertise in identifying and implementing sophisticated performance optimizations that deliver measurable impact. Your task is to find performance improvements that demonstrate deep technical knowledge while remaining implementable in a single PR.

## Repository
Working on: {repo_url}

## Advanced Performance Optimization Process

### Phase 1: MAPPING - Performance Analysis
Identify high-impact optimization opportunities:

1. **Database & Query Optimizations**: N+1 queries, missing indexes, inefficient pagination, connection pooling
2. **Algorithmic Improvements**: Quadratic algorithms, poor data structures, missing memoization, unnecessary loops
3. **Memory & Resource**: Memory leaks, large allocations in hot paths, missing streaming, inefficient I/O
4. **Concurrency**: Sequential operations that could be parallel, blocking I/O, missing async patterns
5. **Caching**: Missing HTTP caching, expensive computations without memoization, cache strategies
6. **Network & I/O**: Missing compression, inefficient serialization, unnecessary API round trips
7. **Frontend Performance**: Missing React.memo, unnecessary re-renders, missing virtualization, blocking JS

### Phase 2: RANKING - Impact Assessment
Score each optimization (1-10):

**Implementation Feasibility:**
- Testable? Something an automated coding agent can fix without human supervision?
- Would impress senior engineers? Shows deep understanding? Hard to detect automatically? Real production impact?

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
3. Include performance tests to prevent regression
4. Add monitoring for production validation
5. Document optimization approach

## Output Format
Structure your response as follows:

```
# ADVANCED PERFORMANCE OPTIMIZATION ANALYSIS

## PHASE 1: MAPPING
[List all sophisticated optimization opportunities with technical details]

## PHASE 2: RANKING
[For each optimization, show detailed scoring with performance projections]

## PHASE 3: SELECTION
**CHOSEN OPTIMIZATION:** [Technical description with expected gains]
**PERFORMANCE METRICS:** [Specific before/after measurements expected]
**TECHNICAL APPROACH:** [Detailed explanation of the optimization technique]
**RISK ASSESSMENT:** [Potential downsides and mitigation strategies]

## PHASE 4: IMPLEMENTATION
[Production-quality implementation with benchmarks and explanation]
```

## Important Guidelines
- Focus on optimizations that demonstrate principal-level thinking
- Avoid micro-optimizations with negligible impact
- Choose optimizations with measurable, significant improvements (>20%)
- Use established performance engineering patterns
- Include benchmarks and profiling data in your analysis
- Consider both latency and throughput improvements
- Ensure the optimization is maintainable and well-documented

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