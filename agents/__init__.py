#!/usr/bin/env python3
"""
Agents package for AI coding assistants.
"""

from .base import (
    CodingAgent, CodingAgentIdeType, AgentResponse,
    AgentRole, MultiAgentTask, AgentDefinition, 
    AgentContext, MultiAgentResponse
)
from .cursor_agent import CursorAgent
from .windsurf_agent import WindsurfAgent
from .claude_code_agent import ClaudeCodeAgent
from .test_agent import TestAgent
from .factory import AgentFactory

__all__ = [
    'CodingAgent',
    'CodingAgentIdeType', 
    'AgentResponse',
    'AgentRole',
    'MultiAgentTask',
    'AgentDefinition',
    'AgentContext',
    'MultiAgentResponse',
    'CursorAgent',
    'WindsurfAgent',
    'ClaudeCodeAgent',
    'TestAgent',
    'AgentFactory'
] 