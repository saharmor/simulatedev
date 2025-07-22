from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentConfig(BaseModel):
    """Configuration for a coding agent"""
    coding_ide: str = Field(..., description="Agent IDE type")
    model: str = Field(..., description="AI model to use")
    role: str = Field(..., description="Agent role")


class TaskCreate(BaseModel):
    """Request schema for creating a new task"""
    issue_url: str = Field(..., description="GitHub repository URL or issue URL")
    agents: List[AgentConfig] = Field(..., description="Agent configurations")
    create_pr: bool = Field(True, description="Whether to create a pull request")
    workflow_type: str = Field("custom", description="Workflow type")
    options: Optional[Dict[str, Any]] = Field(None, description="Additional options")
    task_prompt: Optional[str] = Field(None, description="Custom task prompt")
    issue_number: Optional[int] = Field(None, description="GitHub issue number")
    issue_title: Optional[str] = Field(None, description="GitHub issue title")


class TaskResponse(BaseModel):
    """Response schema for task information"""
    task_id: str
    status: TaskStatus
    repo_url: str
    issue_number: Optional[int]
    issue_title: Optional[str]
    workflow_type: str
    agents: List[AgentConfig]
    progress: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_completion: Optional[datetime]
    current_phase: Optional[str]
    pr_url: Optional[str]
    error_message: Optional[str]


class TaskList(BaseModel):
    """Response schema for paginated task list"""
    tasks: List[TaskResponse]
    total_count: int
    page: int
    per_page: int
    has_next: bool


class LogEntry(BaseModel):
    """Schema for task execution log entries"""
    timestamp: datetime
    level: str
    message: str
    phase: str


class TaskLogsResponse(BaseModel):
    """Response schema for task execution logs"""
    logs: List[LogEntry]
    total_count: int
    has_more: bool 