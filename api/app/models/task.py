from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Task(Base):
    """Task model for SimulateDev task execution tracking"""
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    repo_url = Column(String(500), nullable=False)
    repo_owner = Column(String(100), nullable=False)
    repo_name = Column(String(100), nullable=False)
    issue_number = Column(Integer)
    issue_title = Column(String(500))
    issue_url = Column(String(500))
    workflow_type = Column(String(50), nullable=False)
    agents_config = Column(JSON, nullable=False)
    steps_plan = Column(JSON, nullable=True)  # Pre-generated steps plan (TaskStepsPlan)
    task_description = Column(Text)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    execution_logs = Column(Text)
    pr_url = Column(String(500))
    error_message = Column(Text)
    progress = Column(Integer, default=0)
    estimated_duration = Column(Integer, default=600)
    
    # Relationships
    user = relationship("User", back_populates="tasks")
    history = relationship("ExecutionHistory", back_populates="task", cascade="all, delete-orphan")
    progress_updates = relationship("TaskProgress", back_populates="task", cascade="all, delete-orphan")


class ExecutionHistory(Base):
    """Execution history model for tracking task progress events"""
    __tablename__ = "execution_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    message = Column(Text)
    data = Column(JSON)
    
    # Relationships
    task = relationship("Task", back_populates="history") 