import asyncio
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.progress import TaskProgress
from app.schemas.progress import (
    PhaseType, StepType, StepStatus, AgentContext, 
    ProgressEvent, WebSocketProgressMessage, PreGeneratedStep, TaskStepsPlan
)


class ProgressMonitor:
    """
    Event-based progress monitoring component that:
    1. Sends progress events to database and WebSocket
    2. No state management - just event notifications
    3. Decouples backend logic from frontend messages
    """
    
    def __init__(self, task_id: str, websocket_callback: Optional[Callable] = None, steps_plan: Optional[Dict[str, PreGeneratedStep]] = None):
        self.task_id = task_id
        self.websocket_callback = websocket_callback
        self.steps_plan = steps_plan or {}  # Map of step_id -> PreGeneratedStep
        
    async def mark_step_in_progress(self, phase: PhaseType, step: StepType, agent_context: Optional[AgentContext] = None) -> None:
        """
        Mark a step as currently in progress
        
        Args:
            phase: The execution phase
            step: The step within the phase
            agent_context: Optional agent context for agent-specific steps
        """
        
        try:
            await self._send_status_update(phase, step, StepStatus.IN_PROGRESS, agent_context, None)
            print(f"[ProgressMonitor] Step in progress: {phase.value}.{step.value}")
            
        except Exception as e:
            print(f"[ProgressMonitor] ERROR marking step in progress for task {self.task_id}: {e}")
            raise
    
    async def mark_step_failed(self, phase: PhaseType, step: StepType, error_message: str, agent_context: Optional[AgentContext] = None) -> None:
        """
        Mark a step as failed with an error message
        
        Args:
            phase: The execution phase
            step: The step within the phase
            error_message: Description of the failure
            agent_context: Optional agent context for agent-specific steps
        """
        
        try:
            await self._send_status_update(phase, step, StepStatus.FAILED, agent_context, error_message)
            print(f"[ProgressMonitor] Step failed: {phase.value}.{step.value} - {error_message}")
            
        except Exception as e:
            print(f"[ProgressMonitor] ERROR marking step failed for task {self.task_id}: {e}")
            raise
    
    async def mark_step_completed(self, phase: PhaseType, step: StepType, agent_context: Optional[AgentContext] = None) -> None:
        """
        Mark a step as completed successfully
        
        Args:
            phase: The execution phase
            step: The step within the phase
            agent_context: Optional agent context for agent-specific steps
        """
        
        try:
            await self._send_status_update(phase, step, StepStatus.COMPLETED, agent_context, None)
            print(f"[ProgressMonitor] Step completed: {phase.value}.{step.value}")
            
        except Exception as e:
            print(f"[ProgressMonitor] ERROR marking step completed for task {self.task_id}: {e}")
            raise
    
    async def _send_status_update(self, 
                                 phase: PhaseType,
                                 step: StepType,
                                 status: StepStatus, 
                                 agent_context: Optional[AgentContext],
                                 error_message: Optional[str]) -> None:
        """Send status update to both database and WebSocket"""
        
        # Generate step_id from the parameters
        agent_id = agent_context.agent_id if agent_context else None
        step_id = self.generate_step_id(phase, step, agent_id)
        
        # Verify step exists in plan
        step_info = self.steps_plan.get(step_id)
        if not step_info:
            print(f"[ProgressMonitor] WARNING: Step {step_id} not found in plan")
            return
        
        # 1. ALWAYS persist to database first (crash recovery)
        await self._persist_to_database(step_id, status, phase, step, agent_context, error_message)
        
        # 2. Send WebSocket update (may fail, but that's OK)
        await self._send_websocket_update(step_id, status, phase, step, agent_context, error_message)
    
    async def _persist_to_database(self, 
                                  step_id: str,
                                  status: StepStatus,
                                  phase: PhaseType, 
                                  step: StepType, 
                                  agent_context: Optional[AgentContext],
                                  error_message: Optional[str]) -> None:
        """Persist progress status to database for crash recovery"""
        
        db = SessionLocal()
        try:
            # Convert agent_context to dict for JSON storage
            agent_context_dict = None
            if agent_context:
                agent_context_dict = agent_context.dict()
                
            progress_record = TaskProgress(
                task_id=self.task_id,
                step_id=step_id,
                status=status.value,
                phase_type=phase.value,
                step_type=step.value,
                agent_context=agent_context_dict,
                error_message=error_message,
                timestamp=datetime.utcnow()
            )
            
            db.add(progress_record)
            db.commit()
            
            print(f"[ProgressMonitor] Persisted: {status.value} - {step_id}")
            
        except Exception as e:
            print(f"[ProgressMonitor] Database persistence failed: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    async def _send_websocket_update(self, 
                                    step_id: str,
                                    status: StepStatus,
                                    phase: PhaseType, 
                                    step: StepType, 
                                    agent_context: Optional[AgentContext],
                                    error_message: Optional[str]) -> None:
        """Send progress update via WebSocket (may fail if connection lost)"""
        
        if not self.websocket_callback:
            print(f"[ProgressMonitor] No WebSocket callback available for task {self.task_id}")
            return
        
        try:
            # Create WebSocket message
            message = WebSocketProgressMessage(
                task_id=self.task_id,
                step_id=step_id,
                status=status,
                phase=phase,
                step=step,
                agent_context=agent_context,
                error_message=error_message,
                timestamp=datetime.utcnow()
            )
            
            # Send via WebSocket
            await self.websocket_callback(message.dict())
            
            print(f"[ProgressMonitor] WebSocket sent: {status.value} - {step_id}")
            
        except Exception as e:
            print(f"[ProgressMonitor] WebSocket send failed for task {self.task_id}: {e}")
            # Don't raise - database persistence already succeeded
    
    async def get_current_progress(self) -> Optional[Dict[str, Any]]:
        """Get latest progress status from database"""
        
        db = SessionLocal()
        try:
            # Get latest progress record for this task
            latest_progress = db.query(TaskProgress).filter(
                TaskProgress.task_id == self.task_id
            ).order_by(TaskProgress.timestamp.desc()).first()
            
            if not latest_progress:
                return None
            
            return {
                "step_id": latest_progress.step_id,
                "status": latest_progress.status,
                "phase": latest_progress.phase_type,
                "step": latest_progress.step_type,
                "agent_context": latest_progress.agent_context,
                "error_message": latest_progress.error_message,
                "timestamp": latest_progress.timestamp
            }
            
        except Exception as e:
            print(f"[ProgressMonitor] Failed to get current progress: {e}")
            return None
        finally:
            db.close()
    
    def generate_steps_plan(self, agents_config: List[Dict[str, Any]], workflow_type: str = "custom") -> TaskStepsPlan:
        """
        Pre-generate all steps that will be executed for this task based on configuration
        
        Args:
            agents_config: List of agent configurations from the task
            workflow_type: Type of workflow (sequential, custom, etc.)
            
        Returns:
            TaskStepsPlan with all pre-generated steps
        """
        
        steps = []
        step_order = 0
        
        # Phase 1: Initialization (always the same steps)
        initialization_steps = [
            StepType.CONNECTING_SERVER,
            StepType.INITIALIZING_EXECUTION,
            StepType.CREATING_REQUEST
        ]
        
        for step_type in initialization_steps:
            step_id = self.generate_step_id(PhaseType.INITIALIZATION, step_type)
            steps.append(PreGeneratedStep(
                step_id=step_id,
                phase=PhaseType.INITIALIZATION,
                step=step_type,
                step_order=step_order
            ))
            step_order += 1
        
        # Phase 2: Agent Execution (varies based on agents_config)
        for i, agent_config in enumerate(agents_config):
            # Generate unique agent ID for this instance
            agent_id = f"{agent_config.get('role', 'coder').lower()}_{i+1}"
            
            agent_context = AgentContext(
                agent_id=agent_id,
                agent_ide=agent_config.get('coding_ide'),
                agent_role=agent_config.get('role', 'Coder'),
                agent_model=agent_config.get('model', 'claude-sonnet-4')
            )
            
            # Each agent has 3 steps: starting, working, finishing
            agent_steps = [
                StepType.AGENT_STARTING,
                StepType.AGENT_WORKING,
                StepType.AGENT_FINISHING
            ]
            
            for step_type in agent_steps:
                step_id = self.generate_step_id(PhaseType.AGENT_EXECUTION, step_type, agent_id)
                steps.append(PreGeneratedStep(
                    step_id=step_id,
                    phase=PhaseType.AGENT_EXECUTION,
                    step=step_type,
                    agent_context=agent_context,
                    step_order=step_order
                ))
                step_order += 1
        
        # Phase 3: Completion (always the same steps)
        completion_steps = [
            StepType.PROCESSING_RESULTS,
            StepType.CREATING_PR
        ]
        
        for step_type in completion_steps:
            step_id = self.generate_step_id(PhaseType.COMPLETION, step_type)
            steps.append(PreGeneratedStep(
                step_id=step_id,
                phase=PhaseType.COMPLETION,
                step=step_type,
                step_order=step_order
            ))
            step_order += 1
        
        # Estimate duration based on number of agents (rough estimate)
        estimated_duration = 30 + (len(agents_config) * 120) + 30  # init + agents + completion
        
        # Create lookup map for the ProgressMonitor instance
        self.steps_plan = {step.step_id: step for step in steps}
        
        steps_plan = TaskStepsPlan(
            task_id=self.task_id,
            steps=steps,
            total_steps=len(steps),
            estimated_duration_seconds=estimated_duration
        )
        
        print(f"[ProgressMonitor] Generated {len(steps)} steps for task {self.task_id}")
        return steps_plan
    
    @staticmethod
    def generate_step_id(phase: PhaseType, step: StepType, agent_id: Optional[str] = None) -> str:
        """
        Generate a unique step ID based on phase, step, and optional agent_id
        
        Format:
        - Non-agent steps: "{phase}_{step}"
        - Agent steps: "{phase}_{step}_{agent_id}"
        """
        if agent_id:
            return f"{phase.value}_{step.value}_{agent_id}"
        else:
            return f"{phase.value}_{step.value}"
