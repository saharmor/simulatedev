from fastapi import APIRouter, HTTPException
from typing import List

from app.services.agent_service import AgentService
from app.schemas.agent import AgentType, AgentValidationRequest, AgentValidationResponse

router = APIRouter()
agent_service = AgentService()


@router.get("/types", response_model=dict)
async def get_agent_types():
    """Get available coding agent types"""
    try:
        agents = agent_service.get_agent_types()
        return {"agents": agents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent types: {str(e)}")


@router.post("/validate", response_model=AgentValidationResponse)
async def validate_agents(request: AgentValidationRequest):
    """Validate agent configuration"""
    try:
        result = agent_service.validate_agents(request.agents)
        return AgentValidationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate agents: {str(e)}") 