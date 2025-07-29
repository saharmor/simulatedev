import { fetch } from "@tauri-apps/plugin-http";
import { TaskStepsPlan, PhaseDisplay, StepDisplay, TaskProgress, StepStatus } from '../types/progress';
import { StepMessageGenerator } from '../utils/stepMessageGenerator';

const API_BASE_URL = "http://localhost:8000";

export class StepsService {
  private stepsCache: Map<string, TaskStepsPlan> = new Map();
  private progressCache: Map<string, TaskProgress> = new Map();

  /**
   * Fetch the pre-generated steps plan for a task
   */
  async fetchTaskStepsPlan(taskId: string): Promise<TaskStepsPlan> {
    console.log(`[StepsService] Fetching steps plan for task: ${taskId}`);
    
    // Check cache first
    if (this.stepsCache.has(taskId)) {
      console.log(`[StepsService] Returning cached steps plan for task: ${taskId}`);
      return this.stepsCache.get(taskId)!;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/steps`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      });

      console.log(`[StepsService] Steps plan response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[StepsService] Steps plan request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch steps plan: ${response.status}`);
      }

      const stepsPlan: TaskStepsPlan = await response.json();
      console.log(`[StepsService] Successfully fetched ${stepsPlan.steps.length} steps for task ${taskId}`);
      console.log(`[StepsService] Steps plan:`, stepsPlan);

      // Cache the result
      this.stepsCache.set(taskId, stepsPlan);
      
      return stepsPlan;
    } catch (error) {
      console.error(`[StepsService] Error fetching steps plan for task ${taskId}:`, error);
      throw error;
    }
  }

  /**
   * Initialize task progress from steps plan
   */
  initializeTaskProgress(stepsPlan: TaskStepsPlan, workflowType: string = 'custom'): TaskProgress {
    console.log(`[StepsService] Initializing task progress for ${stepsPlan.steps.length} steps`);
    
    // Group steps by phase/agent
    const groupedSteps = StepMessageGenerator.groupStepsByPhase(stepsPlan.steps, workflowType);
    
    const phases: PhaseDisplay[] = [];
    
    // Sort phase groups by the minimum step_order in each group to maintain execution order
    const sortedPhaseEntries = Object.entries(groupedSteps).sort(([, stepsA], [, stepsB]) => {
      const minOrderA = Math.min(...stepsA.map(step => step.step_order));
      const minOrderB = Math.min(...stepsB.map(step => step.step_order));
      return minOrderA - minOrderB;
    });
    
    // Process each phase group
    for (const [, steps] of sortedPhaseEntries) {
      const firstStep = steps[0];
      const message = firstStep.message;
      
      // Sort steps within the phase by step_order
      const sortedSteps = steps.sort((a, b) => a.step_order - b.step_order);
      
      const phaseSteps: StepDisplay[] = sortedSteps.map(step => ({
        id: step.step_id,
        title: step.message.title,
        status: StepStatus.IN_PROGRESS, // Will be updated when steps actually start
        completed: false,
        inProgress: false,
        failed: false,
        agent_context: step.agent_context,
        startTime: undefined,
        endTime: undefined
      }));
      
      // Use the original phase name from the message, not the key with agent_id
      const displayName = message.agentName;
      
      phases.push({
        name: displayName,
        icon: message.agentIcon,
        steps: phaseSteps,
        agent_context: firstStep.agent_context
      });
    }
    
    const taskProgress: TaskProgress = {
      phases,
      totalSteps: stepsPlan.steps.length,
      completedSteps: 0,
      failedSteps: 0
    };
    
    // Cache the progress
    this.progressCache.set(stepsPlan.task_id, taskProgress);
    
    console.log(`[StepsService] Initialized task progress with ${phases.length} phases`);
    return taskProgress;
  }

  /**
   * Update step status in task progress
   */
  updateStepStatus(
    taskId: string, 
    stepId: string, 
    status: StepStatus, 
    providedDuration?: string
  ): TaskProgress | null {
    console.log(`[StepsService] Updating step ${stepId} to status ${status} for task ${taskId}`);
    
    const progress = this.progressCache.get(taskId);
    if (!progress) {
      console.warn(`[StepsService] No progress found for task ${taskId}`);
      return null;
    }

    let stepFound = false;

    // Find and update the step
    for (const phase of progress.phases) {
      for (let i = 0; i < phase.steps.length; i++) {
        const step = phase.steps[i];
        
        if (step.id === stepId) {
          console.log(`[StepsService] Found step ${stepId} in phase ${phase.name}`);
          
          // Update step status
          const wasCompleted = step.completed;
          const wasFailed = step.failed;
          
          step.status = status;
          step.completed = status === StepStatus.COMPLETED;
          step.inProgress = status === StepStatus.IN_PROGRESS;
          step.failed = status === StepStatus.FAILED;
          
          // Update timing
          const now = new Date();
          if (status === StepStatus.IN_PROGRESS && !step.startTime) {
            step.startTime = now;
          } else if ((status === StepStatus.COMPLETED || status === StepStatus.FAILED) && !step.endTime) {
            step.endTime = now;
            
            // Calculate duration if we have start time
            if (step.startTime) {
              const durationMs = step.endTime.getTime() - step.startTime.getTime();
              const seconds = Math.round(durationMs / 1000);
              step.duration = `${seconds}s`;
            } else if (providedDuration) {
              step.duration = providedDuration;
            }
          }
          
          // Update counters
          if (step.completed && !wasCompleted) {
            progress.completedSteps++;
          } else if (!step.completed && wasCompleted) {
            progress.completedSteps--;
          }
          
          if (step.failed && !wasFailed) {
            progress.failedSteps++;
          } else if (!step.failed && wasFailed) {
            progress.failedSteps--;
          }
          
          // Update current step
          if (step.inProgress) {
            progress.currentStepId = stepId;
          } else if (progress.currentStepId === stepId) {
            progress.currentStepId = undefined;
          }
          
          stepFound = true;
          
          console.log(`[StepsService] Updated step ${stepId}: completed=${step.completed}, inProgress=${step.inProgress}, failed=${step.failed}`);
          break;
        }
      }
      
      if (stepFound) break;
    }

    if (!stepFound) {
      console.warn(`[StepsService] Step ${stepId} not found in task ${taskId}`);
      return progress;
    }

    // Update cache
    this.progressCache.set(taskId, progress);
    
    console.log(`[StepsService] Task progress updated: ${progress.completedSteps}/${progress.totalSteps} completed, ${progress.failedSteps} failed`);
    return progress;
  }

  /**
   * Get current task progress
   */
  getTaskProgress(taskId: string): TaskProgress | null {
    return this.progressCache.get(taskId) || null;
  }

  /**
   * Clear cache for a task
   */
  clearTaskCache(taskId: string): void {
    this.stepsCache.delete(taskId);
    this.progressCache.delete(taskId);
    console.log(`[StepsService] Cleared cache for task ${taskId}`);
  }

  /**
   * Clear all caches
   */
  clearAllCaches(): void {
    this.stepsCache.clear();
    this.progressCache.clear();
    console.log(`[StepsService] Cleared all caches`);
  }
}

export const stepsService = new StepsService();