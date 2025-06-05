#!/usr/bin/env python3
"""
Bug Hunting Module

This module provides specialized functionality for AI-powered bug discovery,
extending the agent orchestrator with bug-specific prompts and workflows.
"""

import pyautogui
import pyperclip
import time
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_orchestrator import AgentOrchestrator
from coding_agents import CodingAgentType


class BugHunter(AgentOrchestrator):
    """Specialized orchestrator for bug hunting workflows"""
    
    def generate_bug_hunting_prompt(self, repo_url: str) -> str:
        """Generate a bug hunting prompt that maps, ranks, and implements one bug"""
        return f"""You are a world-class developer with expertise in bug discovery and autonomous implementation. Your task is to find bugs systematically and implement a fix for the best candidate.

## Repository
Working on: {repo_url}

## Bug Hunting Process

### Phase 1: MAPPING - Comprehensive Bug Discovery
First, scan the entire codebase to identify ALL potential bugs. Look for:

1. **Security Vulnerabilities**: SQL injection, XSS, authentication bypasses, input validation issues
2. **Memory Issues**: Memory leaks, buffer overflows, dangling pointers
3. **Logic Errors**: Off-by-one errors, incorrect conditionals, race conditions
4. **Error Handling Gaps**: Missing try-catch blocks, unhandled exceptions, silent failures
5. **Data Validation Issues**: Missing input validation, type conversion errors
6. **Concurrency Bugs**: Race conditions, deadlocks, thread safety issues
7. **Performance Bugs**: Inefficient algorithms, resource leaks, blocking operations

Create a comprehensive list of ALL bugs you find, no matter how small.

### Phase 2: RANKING - Prioritization
For each bug found, evaluate it on these criteria:

**Implementation Likelihood (1-10 scale):**
- How complex is the fix? (simple fixes score higher)
- How well-contained is the bug? (localized bugs score higher)
- How likely are you to successfully implement it autonomously? (higher certainty scores higher)
- Are there clear, well-established patterns for fixing this type of bug? (yes scores higher)

**Impact & Impressiveness (1-10 scale):**
- How severe is the potential damage? (more severe scores higher)
- How visible would the fix be to users/developers? (more visible scores higher)
- How much would this improve code quality/security? (more improvement scores higher)
- How technically impressive is identifying and fixing this bug? (more impressive scores higher)

**Combined Score Calculation:**
- Final Score = (Implementation Likelihood × 0.6) + (Impact & Impressiveness × 0.4)
- This prioritizes achievable fixes while still valuing high-impact improvements

### Phase 3: SELECTION - Choose the Best Candidate
Select the bug with the highest combined score. This should be:
- Something you can confidently implement end-to-end
- Impressive enough to demonstrate real value
- Achievable within the autonomous workflow constraints

### Phase 4: IMPLEMENTATION - Fix the Selected Bug
For the chosen bug:
1. Implement a complete, working fix
2. Add appropriate tests if the codebase has testing infrastructure
3. Add clear comments explaining the fix
4. Ensure the fix doesn't break existing functionality
5. Follow the existing code style and conventions

## Output Format
Structure your response as follows:

```
# BUG HUNTING ANALYSIS

## PHASE 1: MAPPING
[List all bugs found with brief descriptions]

## PHASE 2: RANKING
[For each bug, show the scoring breakdown]

## PHASE 3: SELECTION
**CHOSEN BUG:** [Name/description of selected bug]
**REASONING:** [Why this bug was selected based on the scoring criteria]

## PHASE 4: IMPLEMENTATION
[Implement the fix with clear explanation of changes made]
```

## Important Notes
- Focus on bugs you can implement confidently and completely
- Prioritize fixes that demonstrate clear value and technical competence
- Ensure your implementation is production-ready, not just a proof-of-concept
- Don't attempt fixes that require extensive architectural changes or external dependencies

Please proceed with this bug hunting process."""

    async def hunt_bugs(self, agent_type: CodingAgentType, repo_url: str, project_path: str = None) -> str:
        """Execute a bug hunting workflow that maps, ranks, and implements one high-value bug"""
        prompt = self.generate_bug_hunting_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)