// Backend schema types - matching the backend exactly

export enum PhaseType {
  INITIALIZATION = "initialization",
  AGENT_EXECUTION = "agent_execution", 
  COMPLETION = "completion"
}

export enum StepType {
  // Initialization steps
  CONNECTING_SERVER = "connecting_server",
  INITIALIZING_EXECUTION = "initializing_execution",
  CREATING_REQUEST = "creating_request",
  
  // Agent execution steps
  AGENT_STARTING = "agent_starting",
  AGENT_WORKING = "agent_working", 
  AGENT_FINISHING = "agent_finishing",
  
  // Completion steps
  PROCESSING_RESULTS = "processing_results",
  CREATING_PR = "creating_pr"
}

export enum StepStatus {
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
  FAILED = "failed"
}

export interface AgentContext {
  agent_id?: string;
  agent_ide?: string;
  agent_role?: string;
  agent_model?: string;
}

export interface PreGeneratedStep {
  step_id: string;
  phase: PhaseType;
  step: StepType;
  agent_context?: AgentContext;
  step_order: number;
  description?: string;
}

export interface TaskStepsPlan {
  task_id: string;
  steps: PreGeneratedStep[];
  total_steps: number;
  estimated_duration_seconds?: number;
}

export interface WebSocketProgressMessage {
  type: string;
  task_id: string;
  step_id: string;
  status: StepStatus;
  phase: PhaseType;
  step: StepType;
  agent_context?: AgentContext;
  error_message?: string;
  timestamp: string;
}

// Frontend-specific types for display

export interface StepDisplay {
  id: string;
  title: string;
  status: StepStatus;
  duration?: string;
  completed: boolean;
  inProgress: boolean;
  failed: boolean;
  agent_context?: AgentContext;
  startTime?: Date;
  endTime?: Date;
}

export interface PhaseDisplay {
  name: string;
  icon: 'rocket' | 'check' | 'test' | 'initialization' | 'code' | 'completion';
  steps: StepDisplay[];
  agent_context?: AgentContext;
}

export interface TaskProgress {
  phases: PhaseDisplay[];
  currentStepId?: string;
  totalSteps: number;
  completedSteps: number;
  failedSteps: number;
}