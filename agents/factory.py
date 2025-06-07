#!/usr/bin/env python3
"""
Agent Factory for creating coding agent instances
"""

from .base import CodingAgent, CodingAgentType
from .cursor_agent import CursorAgent
from .windsurf_agent import WindsurfAgent
from .claude_code_agent import ClaudeCodeAgent
from .test_agent import TestAgent


class AgentFactory:
    """Factory for creating coding agent instances"""
    
    @staticmethod
    def create_agent(agent_type: CodingAgentType, claude_computer_use) -> CodingAgent:
        """Create an agent instance based on the agent type"""
        if agent_type == CodingAgentType.CURSOR:
            return CursorAgent(claude_computer_use)
        elif agent_type == CodingAgentType.WINDSURF:
            return WindsurfAgent(claude_computer_use)
        elif agent_type == CodingAgentType.CLAUDE_CODE:
            return ClaudeCodeAgent(claude_computer_use)
        elif agent_type == CodingAgentType.TEST:
            return TestAgent(claude_computer_use)
        else:
            raise ValueError(f"Unsupported agent: {agent_type}")
    
    @staticmethod
    def create_agent_from_string(agent_name: str, claude_computer_use) -> CodingAgent:
        """Create an agent instance based on a string name (for backward compatibility)"""
        agent_name = agent_name.lower()
        
        if agent_name == "cursor":
            return CursorAgent(claude_computer_use)
        elif agent_name == "windsurf":
            return WindsurfAgent(claude_computer_use)
        elif agent_name == "claude_code" or agent_name == "cloud_code":
            return ClaudeCodeAgent(claude_computer_use)
        elif agent_name == "test":
            return TestAgent(claude_computer_use)
        else:
            raise ValueError(f"Unsupported agent: {agent_name}")
    
    @staticmethod
    def get_supported_agents() -> list:
        """Get list of supported agent types"""
        return list(CodingAgentType) 