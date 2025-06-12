"""
SimulateDev Core Module

This package contains the core orchestration and integration components
for the SimulateDev AI coding assistant.
"""

from .orchestrator import Orchestrator, TaskRequest
from .github_integration import GitHubIntegration

__all__ = [
    'Orchestrator',
    'TaskRequest', 
    'GitHubIntegration'
] 