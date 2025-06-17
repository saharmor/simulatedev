#!/usr/bin/env python3
"""
Code Optimization Module

This module provides specialized functionality for AI-powered code optimization,
extending the unified orchestrator with optimization-specific prompts and workflows.
"""


class CodeOptimizer:
    """Prompt generator for code optimization workflows"""
    
    def __init__(self):
        pass
    
    def generate_low_hanging_fruit_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing ONE high-value, easy improvement"""
        return f"""You are a senior staff engineer identifying THE SINGLE MOST IMPACTFUL improvement that demonstrates technical excellence while remaining achievable in a focused, reviewable PR.

## Repository
Working on: {repo_url}

## CRITICAL CONSTRAINT: SINGLE IMPROVEMENT ONLY
Your goal is to find and implement EXACTLY ONE improvement. This is not about finding multiple improvements - it's about finding THE BEST ONE that maximizes impact while keeping the PR focused and reviewable.

## Focused Low-Hanging Fruit Process

### Phase 1: TARGETED DISCOVERY (Limit: 3-5 candidates maximum)
Identify only the most promising improvements in these high-impact categories:

1. **Critical Performance Wins**: N+1 queries, missing database indexes, O(n²) algorithms
2. **High-Value Security**: Missing rate limiting, input validation gaps, authentication flaws  
3. **Reliability Improvements**: Missing error handling in critical paths, resource leaks
4. **Type Safety Wins**: Missing null checks in critical flows, unsafe type assertions

**STOP HERE** - Do not explore every possible improvement. Focus on finding 3-5 candidates maximum.

### Phase 2: STRICT RANKING (Score 1-10, be selective)
For each candidate, apply rigorous scoring:

**Implementation Feasibility (40%):**
- Can be implemented in 1-2 files maximum
- Zero breaking changes, minimal test updates needed
- Low complexity, high confidence in correctness

**Business Impact (60%):**
- Prevents production incidents OR improves key metrics by >15%
- Addresses a pain point developers/users actually experience
- Creates measurable value (performance, security, reliability)

**Minimum threshold: 8.0/10 total score required**

### Phase 3: SELECTION - Choose THE Winner
Select the SINGLE improvement with the highest score. If no improvement scores 8.0+, respond with "No high-impact improvements found that meet the focused PR criteria."

### Phase 4: FOCUSED IMPLEMENTATION
Implement ONLY the selected improvement:
1. Make the minimal necessary changes
2. Add focused tests for the specific improvement
3. Include clear metrics showing the impact
4. Document the specific problem solved

## Output Format
```
# FOCUSED IMPROVEMENT ANALYSIS

## PHASE 1: TARGETED DISCOVERY
[List 3-5 high-impact candidates only, with brief technical descriptions]

## PHASE 2: STRICT RANKING
[Show scoring for each candidate with clear justification]
**HIGHEST SCORING IMPROVEMENT:** [Name and score]

## PHASE 3: SELECTION
**CHOSEN IMPROVEMENT:** [Technical name with clear value proposition]
**WHY THIS ONE:** [Specific reason this beats other candidates]
**EXPECTED IMPACT:** [Quantifiable benefit - performance %, error reduction, etc.]
**SCOPE:** [Exactly which files will be modified]

## PHASE 4: FOCUSED IMPLEMENTATION
[Implement ONLY the chosen improvement with clear explanation]
```

## Success Criteria
- PR touches 1-2 files maximum
- Single, clear improvement that any reviewer can understand quickly
- Measurable impact that justifies the change
- Zero scope creep - resist the urge to "fix other things while you're there"

Please proceed with this focused improvement analysis."""

    def generate_performance_optimization_prompt(self, repo_url: str) -> str:
        """Generate a prompt for finding and implementing ONE high-value performance optimization"""
        return f"""You are a principal performance engineer identifying THE SINGLE MOST IMPACTFUL performance optimization that delivers measurable results in a focused, reviewable PR.

## Repository
Working on: {repo_url}

## CRITICAL CONSTRAINT: ONE OPTIMIZATION ONLY
Your goal is to find and implement EXACTLY ONE performance optimization. Focus on the highest-impact change that can be clearly measured and reviewed, not multiple smaller optimizations.

## Focused Performance Optimization Process

### Phase 1: TARGETED ANALYSIS (Limit: 3-4 candidates maximum)
Identify only the most promising optimizations in critical performance areas:

1. **Database Critical Path**: N+1 queries in hot paths, missing indexes on frequent queries
2. **Algorithm Bottlenecks**: O(n²) operations in loops, inefficient data structures in hot code
3. **I/O Blocking**: Synchronous operations that could be async, missing caching of expensive calls
4. **Memory/CPU Hot Spots**: Large object allocations in loops, unnecessary computations

**Focus Rule**: Only analyze code paths that are actually performance-critical (user-facing, high-frequency, or resource-intensive).

### Phase 2: IMPACT-FIRST RANKING (Score 1-10)
For each candidate, prioritize measurable impact:

**Performance Impact (70%):**
- Expected improvement >30% in critical metrics (latency, throughput, resource usage)
- Affects user-facing performance or reduces infrastructure costs
- Addresses a known performance bottleneck

**Implementation Feasibility (30%):**
- Can be implemented and tested in 1-2 files
- Low risk of introducing bugs or breaking changes
- Clear before/after measurement possible

**Minimum threshold: 8.5/10 total score required**

### Phase 3: SELECTION - Choose THE Optimization
Select the SINGLE optimization with the highest score. If no optimization scores 8.5+, respond with "No high-impact optimizations found that meet the focused PR criteria."

### Phase 4: FOCUSED IMPLEMENTATION
Implement ONLY the selected optimization:
1. Make the specific performance improvement
2. Add benchmarks showing before/after metrics
3. Include performance tests to prevent regression
4. Document the specific bottleneck solved

## Output Format
```
# FOCUSED PERFORMANCE OPTIMIZATION

## PHASE 1: TARGETED ANALYSIS
[List 3-4 critical performance candidates only]

## PHASE 2: IMPACT-FIRST RANKING
[Show scoring focused on measurable performance gains]
**HIGHEST IMPACT OPTIMIZATION:** [Name and score]

## PHASE 3: SELECTION
**CHOSEN OPTIMIZATION:** [Technical description with expected performance gain]
**PERFORMANCE TARGET:** [Specific improvement expected - "Reduce query time from 200ms to 60ms"]
**MEASUREMENT APPROACH:** [How the improvement will be validated]
**SCOPE:** [Exactly which files/functions will be optimized]

## PHASE 4: FOCUSED IMPLEMENTATION
[Implement ONLY the chosen optimization with benchmarks and clear explanation]
```

## Success Criteria
- Single, measurable performance improvement >30%
- PR focuses on one specific bottleneck
- Clear before/after metrics included
- Implementation is surgical - no scope creep

Please proceed with this focused performance optimization analysis."""

    def generate_refactoring_prompt(self, repo_url: str) -> str:
        """Generate a prompt for implementing ONE focused refactoring improvement"""
        return f"""You are an expert software architect tasked with implementing THE SINGLE MOST VALUABLE refactoring that improves code quality while keeping the PR focused and reviewable.

## Repository
Working on: {repo_url}

## CRITICAL CONSTRAINT: ONE REFACTORING ONLY
Your goal is to find and implement EXACTLY ONE refactoring improvement. Focus on the change that provides the highest maintainability benefit while remaining easy to review and validate.

## Focused Refactoring Process

### Phase 1: TARGETED ANALYSIS (Limit: 3-4 candidates maximum)
Identify only the most impactful refactoring opportunities:

1. **Critical Code Duplication**: Repeated logic in 3+ places that causes maintenance burden
2. **Complex Function Breakdown**: Single function >50 lines doing multiple responsibilities
3. **Naming Clarity**: Confusing names in core business logic that slow down development
4. **Structural Improvement**: Poor separation of concerns in a key module

**Focus Rule**: Only consider refactoring that addresses actual developer pain points or maintenance issues.

### Phase 2: VALUE-BASED RANKING (Score 1-10)
For each candidate, prioritize developer experience impact:

**Maintainability Impact (60%):**
- Reduces future bug risk or development time
- Makes code significantly easier to understand/modify
- Addresses a known source of developer confusion

**Implementation Safety (40%):**
- Can be refactored with high confidence in correctness
- Existing tests provide good coverage for validation
- Low risk of introducing subtle bugs

**Minimum threshold: 8.0/10 total score required**

### Phase 3: SELECTION - Choose THE Refactoring
Select the SINGLE refactoring with the highest score. If no refactoring scores 8.0+, respond with "No high-value refactoring found that meets the focused PR criteria."

### Phase 4: FOCUSED IMPLEMENTATION
Implement ONLY the selected refactoring:
1. Make the specific structural improvement
2. Ensure all existing tests still pass
3. Add documentation if the change affects public interfaces
4. Maintain existing functionality exactly

## Output Format
```
# FOCUSED REFACTORING ANALYSIS

## PHASE 1: TARGETED ANALYSIS
[List 3-4 high-value refactoring candidates only]

## PHASE 2: VALUE-BASED RANKING
[Show scoring focused on maintainability benefits]
**HIGHEST VALUE REFACTORING:** [Name and score]

## PHASE 3: SELECTION
**CHOSEN REFACTORING:** [Description of the specific improvement]
**MAINTAINABILITY BENEFIT:** [How this makes the code easier to work with]
**VALIDATION APPROACH:** [How to ensure functionality is preserved]
**SCOPE:** [Exactly which files/functions will be refactored]

## PHASE 4: FOCUSED IMPLEMENTATION
[Implement ONLY the chosen refactoring with clear explanation]
```

## Success Criteria
- Single, focused refactoring that improves maintainability
- All existing functionality preserved
- PR is easy to review and understand the benefit
- No scope creep - resist fixing unrelated issues

Please proceed with this focused refactoring analysis."""