import sys
import os
from typing import List, Dict, Any

# Add the parent SimulateDev directory to the path to import existing modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

try:
    from agents import CodingAgentIdeType, AgentRole
    from agents.factory import AgentFactory
except ImportError:
    # Fallback if SimulateDev modules aren't available
    CodingAgentIdeType = None
    AgentRole = None
    AgentFactory = None


class AgentService:
    """Service for managing coding agents and their configurations"""
    
    def __init__(self):
        self.supported_agents = self._get_supported_agents()
    
    def _get_supported_agents(self) -> List[Dict[str, Any]]:
        """Get list of supported coding agents"""
        
        # Fallback agent definitions if SimulateDev modules aren't available
        fallback_agents = [
            {
                "id": "cursor",
                "name": "Cursor",
                "description": "AI-powered code editor with advanced completion",
                "supported_models": ["claude-sonnet-4", "gpt-4", "gpt-3.5-turbo"],
                "default_model": "claude-sonnet-4",
                "capabilities": ["code_completion", "refactoring", "debugging", "documentation"]
            },
            {
                "id": "windsurf",
                "name": "Windsurf",
                "description": "Advanced AI coding assistant",
                "supported_models": ["claude-sonnet-4", "gpt-4"],
                "default_model": "claude-sonnet-4",
                "capabilities": ["code_completion", "refactoring", "debugging"]
            },
            {
                "id": "claude_code",
                "name": "Claude Code",
                "description": "Direct Claude API integration for coding tasks",
                "supported_models": ["claude-sonnet-4", "claude-haiku", "claude-opus"],
                "default_model": "claude-sonnet-4",
                "capabilities": ["code_generation", "analysis", "refactoring", "documentation"]
            }
        ]
        
        if CodingAgentIdeType and AgentFactory:
            try:
                # Use actual SimulateDev agent definitions if available
                agents = []
                for agent_type in CodingAgentIdeType:
                    agent_info = {
                        "id": agent_type.value,
                        "name": agent_type.value.title(),
                        "description": f"{agent_type.value.title()} coding agent",
                        "supported_models": ["claude-sonnet-4", "gpt-4", "gpt-3.5-turbo"],
                        "default_model": "claude-sonnet-4",
                        "capabilities": ["code_completion", "refactoring", "debugging"]
                    }
                    agents.append(agent_info)
                return agents
            except Exception:
                pass
        
        return fallback_agents
    
    def get_agent_types(self) -> List[Dict[str, Any]]:
        """Get available coding agent types"""
        return self.supported_agents
    
    def validate_agent_config(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate agent configuration"""
        required_fields = ['coding_ide', 'model', 'role']
        
        for field in required_fields:
            if field not in agent_config:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate agent type
        supported_agent_ids = [agent['id'] for agent in self.supported_agents]
        if agent_config['coding_ide'] not in supported_agent_ids:
            raise ValueError(f"Unsupported agent type: {agent_config['coding_ide']}")
        
        # Validate model
        agent_info = next((agent for agent in self.supported_agents if agent['id'] == agent_config['coding_ide']), None)
        if agent_info and agent_config['model'] not in agent_info['supported_models']:
            # Allow the model but warn
            pass
        
        # Validate role
        valid_roles = ['coder', 'reviewer', 'tester', 'planner']
        if agent_config['role'].lower() not in valid_roles:
            raise ValueError(f"Invalid role: {agent_config['role']}. Must be one of: {valid_roles}")
        
        return {
            "valid": True,
            "agent_config": agent_config,
            "warnings": []
        }
    
    def get_default_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Get default configuration for an agent"""
        agent_info = next((agent for agent in self.supported_agents if agent['id'] == agent_id), None)
        
        if not agent_info:
            raise ValueError(f"Unknown agent type: {agent_id}")
        
        return {
            "coding_ide": agent_id,
            "model": agent_info['default_model'],
            "role": "coder"
        } 