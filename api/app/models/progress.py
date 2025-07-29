from sqlalchemy import Column, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class TaskProgress(Base):
    """Task progress tracking - stores step status updates"""
    __tablename__ = "task_progress"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    
    # Progress structure
    step_id = Column(String(100), nullable=False)    # Unique step identifier
    status = Column(String(50), nullable=False)      # StepStatus enum value
    phase_type = Column(String(50), nullable=False)  # PhaseType enum value
    step_type = Column(String(50), nullable=False)   # StepType enum value
    
    # Context and timing
    agent_context = Column(JSON, nullable=True)      # Agent-specific info (AgentContext)
    error_message = Column(Text, nullable=True)      # If status=failed
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    task = relationship("Task", back_populates="progress_updates")