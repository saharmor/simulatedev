from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class PhaseType(str, Enum):
    """High-level execution phases"""
    INITIALIZATION = "initialization"
    AGENT_EXECUTION = "agent_execution"
    COMPLETION = "completion"


class StepType(str, Enum):
    """Individual steps within phases"""
    # Initialization steps
    CONNECTING_SERVER = "connecting_server"
    INITIALIZING_EXECUTION = "initializing_execution"  
    CREATING_REQUEST = "creating_request"
    
    # Agent execution steps
    AGENT_STARTING = "agent_starting"
    AGENT_WORKING = "agent_working"
    AGENT_FINISHING = "agent_finishing"
    
    # Completion steps
    PROCESSING_RESULTS = "processing_results"
    CREATING_PR = "creating_pr"


class StepStatus(str, Enum):
    """Status of individual steps"""
    IN_PROGRESS = "in_progress"   # Step is currently being executed
    COMPLETED = "completed"       # Step completed successfully
    FAILED = "failed"            # Step failed with error


class AgentContext(BaseModel):
    """Context information for agent steps"""
    agent_id: Optional[str] = None            # Unique ID for this agent instance
    agent_ide: Optional[str] = None           # "cursor", "windsurf", etc.
    agent_role: Optional[str] = None          # "Coder", "Tester", etc.
    agent_model: Optional[str] = None         # "claude-sonnet-4", etc.


class ProgressEvent(BaseModel):
    """Single progress event - for internal use"""
    task_id: str
    step_id: str
    status: StepStatus
    phase_type: PhaseType
    step_type: StepType
    agent_context: Optional[AgentContext] = None
    error_message: Optional[str] = None
    timestamp: datetime


class WebSocketProgressMessage(BaseModel):
    """Message sent over WebSocket to frontend"""
    type: str = "progress"
    task_id: str
    step_id: str
    status: StepStatus
    phase: PhaseType
    step: StepType
    agent_context: Optional[AgentContext] = None
    error_message: Optional[str] = None
    timestamp: datetime


class PreGeneratedStep(BaseModel):
    """A pre-generated step that will be executed"""
    step_id: str  # Unique identifier for this step
    phase: PhaseType
    step: StepType
    agent_context: Optional[AgentContext] = None
    step_order: int  # Order within the entire task execution
    description: Optional[str] = None  # Human-readable description


class TaskStepsPlan(BaseModel):
    """Complete pre-generated plan of all steps for a task"""
    task_id: str
    steps: List[PreGeneratedStep]
    total_steps: int
    estimated_duration_seconds: Optional[int] = None