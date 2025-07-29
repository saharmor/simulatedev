#!/usr/bin/env python3
"""
Agents package for AI coding assistants.
"""

from .base import (
    CodingAgent, CodingAgentIdeType, AgentResponse,
    AgentRole, MultiAgentTask, AgentDefinition, 
    AgentContext, MultiAgentResponse
)

from .web_agent import WebAgent

from .cursor_agent import CursorAgent
from .windsurf_agent import WindsurfAgent
from .openai_codex_agent import OpenAICodexAgent
from .test_agent import TestAgent
from .factory import AgentFactory
from .gemini_cli_agent import GeminiCliAgent
from .claude_cli_agent import ClaudeCliAgent

__all__ = [
    'CodingAgent',
    'CodingAgentIdeType', 
    'AgentResponse',
    'AgentRole',
    'MultiAgentTask',
    'AgentDefinition',
    'AgentContext',
    'MultiAgentResponse',
    'WebAgent',
    'CursorAgent',
    'WindsurfAgent',
    'OpenAICodexAgent',
    'TestAgent',
    'AgentFactory',
    'GeminiCliAgent',
    'ClaudeCliAgent'
] 