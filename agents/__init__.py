#!/usr/bin/env python3
"""
Agents package for AI coding assistants.
"""

from .base import (
    CodingAgent, CodingAgentIdeType, AgentResponse,
    AgentRole, MultiAgentTask, AgentDefinition, 
    AgentContext, MultiAgentResponse
)

# Conditionally import WebAgent only if botright is available
try:
    from .web_agent import WebAgent
    WEB_AGENT_AVAILABLE = True
except ImportError:
    WebAgent = None
    WEB_AGENT_AVAILABLE = False

from .cursor_agent import CursorAgent
from .windsurf_agent import WindsurfAgent
from .claude_code_agent import ClaudeCodeAgent
from .openai_codex_agent import OpenAICodexAgent
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
    'OpenAICodexAgent',
    'TestAgent',
    'AgentFactory'
]

# Only add WebAgent to __all__ if it's available
if WEB_AGENT_AVAILABLE:
    __all__.append('WebAgent') 