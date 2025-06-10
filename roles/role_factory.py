#!/usr/bin/env python3
"""
Role Factory Module

This module provides a factory for creating role instances based on agent roles.
It centralizes role creation and management for the multi-agent system.
"""

from typing import Dict, Type
from agents import AgentRole
from .base_role import BaseRole
from .planner_role import PlannerRole
from .coder_role import CoderRole
from .tester_role import TesterRole


class RoleFactory:
    """Factory for creating role instances"""
    
    # Registry of available roles
    _role_registry: Dict[AgentRole, Type[BaseRole]] = {
        AgentRole.PLANNER: PlannerRole,
        AgentRole.CODER: CoderRole,
        AgentRole.TESTER: TesterRole
    }
    
    @classmethod
    def create_role(cls, role: AgentRole) -> BaseRole:
        """
        Create a role instance based on the agent role.
        
        Args:
            role: The AgentRole enum value
            
        Returns:
            BaseRole: An instance of the appropriate role class
            
        Raises:
            ValueError: If the role is not supported
        """
        if role not in cls._role_registry:
            raise ValueError(f"Unsupported role: {role}. Available roles: {list(cls._role_registry.keys())}")
        
        role_class = cls._role_registry[role]
        return role_class()
    
    @classmethod
    def get_available_roles(cls) -> list:
        """Get a list of all available roles"""
        return list(cls._role_registry.keys())
    
    @classmethod
    def register_role(cls, role: AgentRole, role_class: Type[BaseRole]):
        """
        Register a new role class with the factory.
        
        Args:
            role: The AgentRole enum value
            role_class: The role class to register
        """
        cls._role_registry[role] = role_class
    
    @classmethod
    def is_role_supported(cls, role: AgentRole) -> bool:
        """Check if a role is supported by the factory"""
        return role in cls._role_registry 