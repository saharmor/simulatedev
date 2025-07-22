from pydantic import BaseModel, Field
from typing import List, Optional


class AgentType(BaseModel):
    """Schema for available agent types"""
    id: str
    name: str
    description: str
    supported_models: List[str]
    supported_roles: List[str]
    default_model: str


class AgentValidationRequest(BaseModel):
    """Request schema for agent configuration validation"""
    agents: List[dict] = Field(..., description="Agent configurations to validate")


class ValidatedAgent(BaseModel):
    """Schema for validated agent configuration"""
    coding_ide: str
    model: str
    role: str
    validated: bool


class AgentValidationResponse(BaseModel):
    """Response schema for agent validation"""
    valid: bool
    agents: List[ValidatedAgent]
    errors: List[str] = [] 