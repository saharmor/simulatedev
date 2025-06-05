#!/usr/bin/env python3
"""
Coding Agents Module

This module provides backward compatibility by importing from the new agents package.
All agent classes have been moved to separate files in the agents/ directory.
"""

# Import everything from the new agents package for backward compatibility
from agents import (
    CodingAgent,
    CodingAgentType,
    AgentResponse,
    CursorAgent,
    WindsurfAgent,
    ClaudeCodeAgent,
    AgentFactory
)

# Export all classes for backward compatibility
__all__ = [
    'CodingAgent',
    'CodingAgentType',
    'AgentResponse',
    'CursorAgent',
    'WindsurfAgent',
    'ClaudeCodeAgent',
    'AgentFactory'
] 