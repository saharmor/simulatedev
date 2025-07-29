import { StepType, PhaseType, AgentContext } from '../types/progress';

export interface StepMessage {
  title: string;
  agentName: string;
  agentIcon: 'rocket' | 'check' | 'test' | 'initialization' | 'code' | 'completion';
  phase: string;
}

/**
 * Generates user-friendly messages for backend step types
 */
export class StepMessageGenerator {
  
  /**
   * Check if this is the second coder in a sequential workflow
   */
  private static isSecondCoder(agentContext?: AgentContext): boolean {
    if (!agentContext?.agent_id) return false;
    
    // Check if this is a coder agent that comes after other agents
    // In sequential workflows: coder_1 -> tester_1 -> coder_2
    return agentContext.agent_id.includes('coder_2') || 
           agentContext.agent_id.includes('coder_3') ||
           (agentContext.agent_id.includes('coder') && 
            (agentContext.agent_id.includes('_2') || agentContext.agent_id.includes('_3')));
  }
  
  /**
   * Generate a user-friendly message for a step
   */
  static generateStepMessage(
    stepType: StepType,
    phaseType: PhaseType,
    agentContext?: AgentContext,
    workflowType: string = 'custom'
  ): StepMessage {
    const isSequential = workflowType === 'sequential';
    const agentRole = agentContext?.agent_role || 'Coder';
    
    // Determine agent icon based on phase and role
    let agentIcon: 'rocket' | 'check' | 'test' | 'initialization' | 'code' | 'completion' = 'code';
    
    if (phaseType === PhaseType.INITIALIZATION) {
      agentIcon = 'initialization';
    } else if (phaseType === PhaseType.COMPLETION) {
      agentIcon = 'completion';
    } else if (phaseType === PhaseType.AGENT_EXECUTION) {
      if (agentRole.toLowerCase().includes('review') || agentRole.toLowerCase().includes('reviewer')) {
        agentIcon = 'check';
      } else if (agentRole.toLowerCase().includes('test')) {
        agentIcon = 'test';
      } else {
        agentIcon = 'code';  // For all coding agents
      }
    }
    
    // Generate phase name
    let phase = '';
    if (phaseType === PhaseType.INITIALIZATION) {
      phase = 'Initialization';
    } else if (phaseType === PhaseType.COMPLETION) {
      phase = 'Completion';
    } else if (phaseType === PhaseType.AGENT_EXECUTION) {
      if (isSequential) {
        // For sequential workflows, use specific names based on agent type
        if (agentRole.toLowerCase().includes('test')) {
          phase = 'Testing Agent';
        } else if (this.isSecondCoder(agentContext)) {
          phase = 'Review Implementation Coding Agent';
        } else if (agentRole.toLowerCase().includes('coder') || agentRole.toLowerCase().includes('code')) {
          phase = 'Implementation Coding Agent';
        } else {
          phase = `${agentRole} Agent`;
        }
      } else {
        // For single agent workflows, just use "Coding Agent"
        phase = 'Coding Agent';
      }
    }
    
    // Generate step title based on step type
    let title = '';
    switch (stepType) {
      // Initialization steps
      case StepType.CONNECTING_SERVER:
        title = 'Initializing task execution environment...';
        break;
      case StepType.INITIALIZING_EXECUTION:
        title = 'Setting up task parameters and validation...';
        break;
      case StepType.CREATING_REQUEST:
        title = 'Preparing agent execution pipeline...';
        break;
        
      // Agent execution steps
      case StepType.AGENT_STARTING:
        if (isSequential && agentRole.toLowerCase().includes('review')) {
          title = 'Starting code review process...';
        } else if (isSequential && agentRole.toLowerCase().includes('test')) {
          title = 'Starting test execution...';
        } else if (isSequential && this.isSecondCoder(agentContext)) {
          title = 'Starting implementation fixes based on review feedback...';
        } else {
          title = 'Starting initial implementation...';
        }
        break;
        
      case StepType.AGENT_WORKING:
        if (isSequential && agentRole.toLowerCase().includes('review')) {
          title = 'Reviewing the implementation for quality and correctness...';
        } else if (isSequential && agentRole.toLowerCase().includes('test')) {
          title = 'Running comprehensive tests and validation...';
        } else if (isSequential && this.isSecondCoder(agentContext)) {
          title = 'Fixing issues and implementing improvements from review...';
        } else {
          title = 'Implementing the solution for the issue...';
        }
        break;
        
      case StepType.AGENT_FINISHING:
        if (isSequential && agentRole.toLowerCase().includes('review')) {
          title = 'Finalizing code review and providing feedback...';
        } else if (isSequential && agentRole.toLowerCase().includes('test')) {
          title = 'Finalizing test results and validation report...';
        } else if (isSequential && this.isSecondCoder(agentContext)) {
          title = 'Finalizing implementation fixes and improvements...';
        } else {
          title = 'Finalizing initial implementation...';
        }
        break;
        
      // Completion steps
      case StepType.PROCESSING_RESULTS:
        title = 'Processing final results and creating output...';
        break;
      case StepType.CREATING_PR:
        title = 'Finalizing task completion...';
        break;
        
      default:
        title = `Executing ${String(stepType).replace(/_/g, ' ').toLowerCase()}...`;
        break;
    }
    
    return {
      title,
      agentName: phase,
      agentIcon,
      phase
    };
  }
  
  /**
   * Group steps by phase/agent for display, using agent_id to create separate phases for each agent
   */
  static groupStepsByPhase(steps: any[], workflowType: string = 'custom'): { [key: string]: any[] } {
    const grouped: { [key: string]: any[] } = {};
    
    for (const step of steps) {
      const message = this.generateStepMessage(
        step.step,
        step.phase,
        step.agent_context,
        workflowType
      );
      
      // Create unique phase key using agent_id for agent execution phases
      let phaseKey = message.phase;
      if (step.phase === 'agent_execution' && step.agent_context?.agent_id) {
        // For agent execution, append agent_id to make each agent its own phase
        phaseKey = `${message.phase}_${step.agent_context.agent_id}`;
      }
      
      if (!grouped[phaseKey]) {
        grouped[phaseKey] = [];
      }
      
      grouped[phaseKey].push({
        ...step,
        message: {
          ...message,
          phase: phaseKey // Update the phase name to include agent_id
        }
      });
    }
    
    return grouped;
  }
}