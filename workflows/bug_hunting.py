#!/usr/bin/env python3
"""
Bug Hunting Module

This module provides specialized functionality for AI-powered bug discovery,
extending the unified orchestrator with bug-specific prompts and workflows.
"""

import pyautogui
import pyperclip
import time
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import Orchestrator
from coding_agents import CodingAgentIdeType


class BugHunter:
    """Specialized orchestrator for bug hunting workflows"""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
    
    def generate_bug_hunting_prompt(self, repo_url: str) -> str:
        """Generate a bug hunting prompt that maps, ranks, and implements one bug"""
        return f"""You are a world-class security researcher and software engineer with expertise in discovering subtle, high-impact bugs. Your task is to find sophisticated bugs that demonstrate deep technical understanding while remaining fixable within a single PR.

## Repository
Working on: {repo_url}

## Bug Hunting Process

### Phase 1: MAPPING - Deep Technical Bug Discovery
Perform thorough analysis to identify sophisticated bugs that would impress experienced developers:

1. **Security Vulnerabilities**: Path traversal, timing attacks, insecure randomness, JWT flaws, SSRF, prototype pollution, insecure deserialization
2. **Concurrency Issues**: TOCTOU bugs, missing locks, race conditions, double-checked locking anti-patterns
3. **Resource Management**: Resource exhaustion, connection leaks, missing cleanup in error paths, memory issues
4. **Cryptographic Weaknesses**: Weak hash algorithms, predictable tokens, missing constant-time comparisons, hardcoded secrets
5. **Business Logic Flaws**: Integer overflow in calculations, missing rate limiting, incorrect state transitions, authorization gaps
6. **Type Safety Issues**: Unsafe type assertions, missing null checks, type confusion bugs
7. **API Contract Violations**: Missing pagination limits, information leakage, GraphQL attacks, missing field authorization

### Phase 2: RANKING - Technical Sophistication Assessment
Score each bug (1-10 scale):

**Implementation Feasibility:**
- Testable? Something an automated coding agent can fix without human supervision?

**Technical Impressiveness:**
- Would impress senior engineers? Shows deep understanding? Hard to detect automatically? Real production impact?

**Final Score = (Feasibility × 0.5) + (Impressiveness × 0.5)**

### Phase 3: SELECTION - Choose the Most Impressive Fixable Bug
Select the bug that best demonstrates deep technical knowledge, real-world impact, and clean implementation.

### Phase 4: IMPLEMENTATION - Professional Bug Fix
1. Implement complete, secure fix following best practices
2. Add comprehensive test cases
3. Include detailed comments explaining vulnerability and fix
4. Add defensive programming practices
5. Update documentation and consider logging/monitoring

## Output Format
Structure your response as follows:

```
# ADVANCED BUG HUNTING ANALYSIS

## PHASE 1: MAPPING
[List all sophisticated bugs found with technical descriptions]

## PHASE 2: RANKING
[For each bug, show detailed scoring with technical justification]

## PHASE 3: SELECTION
**CHOSEN BUG:** [Technical name and CVE-style description]
**TECHNICAL IMPACT:** [Detailed explanation of what could go wrong]
**ATTACK SCENARIO:** [How this could be exploited in practice]
**FIX APPROACH:** [Industry-standard solution pattern]

## PHASE 4: IMPLEMENTATION
[Implement the fix with professional code and comprehensive explanation]
```

## Important Guidelines
- Focus on bugs that require technical sophistication to identify
- Avoid trivial issues like missing error messages or simple null checks
- Choose bugs that have real security or reliability implications
- Ensure your fix follows security best practices and design patterns
- Make the PR description compelling enough to impress senior engineers
- Include enough technical detail to demonstrate expertise

Please proceed with this advanced bug hunting process."""

    async def hunt_bugs(self, agent_type: CodingAgentIdeType, repo_url: str, project_path: str = None) -> str:
        """Execute a bug hunting workflow that maps, ranks, and implements one high-value bug"""
        prompt = self.generate_bug_hunting_prompt(repo_url)
        
        # Create single-agent request using unified orchestrator
        request = Orchestrator.create_single_agent_request(
            task_description=prompt,
            agent_type=agent_type.value,
            workflow_type="bug_hunting",
            repo_url=repo_url,
            work_directory=project_path
        )
        
        response = await self.orchestrator.execute_task(request)
        return response.final_output