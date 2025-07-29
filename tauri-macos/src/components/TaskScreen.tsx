import { useState, useEffect } from "react";
import { ExternalLink, FileText, Plus, Minus, GitPullRequest, GitMerge, X, Rocket, Trash2, Square, Check, Settings, Code, TestTube, Package } from "lucide-react";
import { Button } from "./ui/button";
import { useToast } from "./ui/use-toast";
import { openUrl } from "@tauri-apps/plugin-opener";
import { websocketService } from "../services/websocketService";
import { stepsService } from "../services/stepsService";
import { TaskProgress, PhaseDisplay, StepDisplay } from "../types/progress";

interface TaskScreenProps {
  taskId: string;
  task?: {
    id: string;
    name: string;
    status: "ongoing" | "pending_pr" | "merged" | "rejected" | "failed";
    branch: string;
    repo: string;
    isRunning?: boolean;
    issueId?: string;
    issueNumber?: number;
    createdAt: Date;
    realTaskId?: string;
    progress?: number;
    prUrl?: string;
    errorMessage?: string;
    workflowType?: string;
    pr?: PRData;
  };
  onDeleteTask?: (taskId: string) => void;
  onNavigateHome?: () => void;
}

interface PRData {
  title: string;
  branch: string;
  filesChanged: number;
  additions: number;
  deletions: number;
  status: 'open' | 'merged' | 'closed';
  url?: string;
}

function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / (1000 * 60));
  const hours = Math.floor(minutes / 60);
  
  if (hours > 0) {
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  }
  return `${minutes}m`;
}

function getPRStatusIcon(status: PRData['status']) {
  switch (status) {
    case 'open':
      return <GitPullRequest className="w-4 h-4 text-success flex-shrink-0" />;
    case 'merged':
      return <GitMerge className="w-4 h-4 text-success flex-shrink-0" />;
    case 'closed':
      return <X className="w-4 h-4 text-error flex-shrink-0" />;
    default:
      return <GitPullRequest className="w-4 h-4 text-gray-500 flex-shrink-0" />;
  }
}

function PRComponent({ pr }: { pr: PRData }) {
  const handleOpenPR = async () => {
    if (pr.url) {
      console.log(`[TaskScreen] Opening external link: ${pr.url}`);
      try {
        await openUrl(pr.url);
      } catch (error) {
        console.error("Failed to open external link:", error);
      }
    }
  };

  return (
    <div className="bg-card border border-gray-200 rounded-lg p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          {getPRStatusIcon(pr.status)}
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium text-foreground mb-1">
              {pr.title}
            </h3>
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <span className="font-mono">{pr.branch}</span>
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" />
                {pr.filesChanged} files
              </span>
              <span className="flex items-center gap-1 text-success">
                <Plus className="w-3 h-3" />
                {pr.additions}
              </span>
              <span className="flex items-center gap-1 text-error">
                <Minus className="w-3 h-3" />
                {pr.deletions}
              </span>
            </div>
          </div>
        </div>
        <Button 
          variant="ghost" 
          size="sm" 
          className="text-gray-500 hover:text-gray-700 ml-2"
          onClick={handleOpenPR}
          disabled={!pr.url}
        >
          <ExternalLink className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}


function ExecutionStepComponent({ step }: { step: StepDisplay }) {

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex-shrink-0">
        {step.completed ? (
          <div className="w-5 h-5 bg-foreground rounded-full flex items-center justify-center">
            <Rocket className="w-3 h-3 text-background" />
          </div>
        ) : step.inProgress ? (
          <div className="w-5 h-5 bg-foreground rounded-full flex items-center justify-center">
            <Rocket className="w-3 h-3 text-background animate-pulse" />
          </div>
        ) : step.failed ? (
          <div className="w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
            <X className="w-3 h-3 text-white" />
          </div>
        ) : (
          <div className="w-5 h-5 border-2 border-border rounded-full" />
        )}
      </div>
      
      <div className="flex-1">
        <span className={`text-sm ${step.failed ? 'text-red-500' : 'text-foreground'}`}>
          {step.title}
        </span>
      </div>
    </div>
  );
}

function PhaseComponent({ phase }: { phase: PhaseDisplay }) {
  const getPhaseIcon = () => {
    switch (phase.icon) {
      case 'initialization':
        return <Settings className="w-5 h-5 text-blue-600" />;
      case 'code':
        return <Code className="w-5 h-5 text-purple-600" />;
      case 'test':
        return <TestTube className="w-5 h-5 text-green-600" />;
      case 'check':
        return <Check className="w-5 h-5 text-orange-600" />;
      case 'completion':
        return <Package className="w-5 h-5 text-emerald-600" />;
      default:
        return <Rocket className="w-5 h-5 text-foreground" />;
    }
  };

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-6">
        {getPhaseIcon()}
        <h2 className="text-lg font-medium text-foreground font-mono">{phase.name}</h2>
      </div>
      <div className="space-y-1">
        {phase.steps.map((step) => (
          <ExecutionStepComponent 
            key={step.id} 
            step={step} 
          />
        ))}
      </div>
    </div>
  );
}

export function TaskScreen({ taskId, task: passedTask, onDeleteTask, onNavigateHome }: TaskScreenProps) {
  const [isStopped, setIsStopped] = useState(false);
  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null);
  const [isLoadingSteps, setIsLoadingSteps] = useState(true);
  const { toast } = useToast();
  
  const task = passedTask;

  // Initialize steps when task loads
  useEffect(() => {
    const initializeSteps = async () => {
      if (!task?.realTaskId) {
        console.log(`[TaskScreen] No real task ID available yet for task ${taskId}`);
        return;
      }

      try {
        console.log(`[TaskScreen] Initializing steps for task ${task.realTaskId}`);
        setIsLoadingSteps(true);
        
        const stepsPlan = await stepsService.fetchTaskStepsPlan(task.realTaskId);
        const initialProgress = stepsService.initializeTaskProgress(stepsPlan, task.workflowType);
        
        console.log(`[TaskScreen] Initialized task progress:`, initialProgress);
        setTaskProgress(initialProgress);
        
      } catch (error) {
        console.error(`[TaskScreen] Failed to initialize steps:`, error);
        toast({
          title: "Failed to load task steps",
          description: "Unable to fetch task execution plan",
          variant: "destructive"
        });
      } finally {
        setIsLoadingSteps(false);
      }
    };

    initializeSteps();
  }, [task?.realTaskId, task?.workflowType, taskId, toast]);

  // Update task progress when steps change
  useEffect(() => {
    if (task?.realTaskId) {
      const currentProgress = stepsService.getTaskProgress(task.realTaskId);
      if (currentProgress && currentProgress !== taskProgress) {
        console.log(`[TaskScreen] Updating task progress from steps service`);
        setTaskProgress(currentProgress);
      }
    }
  }, [task?.realTaskId, taskProgress]);


  if (!task) {
    return (
      <div className="flex-1 bg-background overflow-y-auto flex items-center justify-center">
        <p className="text-gray-500">Task not found</p>
      </div>
    );
  }

  const duration = task.createdAt ? Date.now() - task.createdAt.getTime() : 0;
  const progressPercentage = taskProgress ? 
    Math.round((taskProgress.completedSteps / taskProgress.totalSteps) * 100) : 
    (task.progress || 0);

  const handleStopTask = () => {
    console.log(`[TaskScreen] Stopping task: ${taskId}`);
    websocketService.disconnect();
    setIsStopped(true);
    toast({
      title: "Task stopped successfully.",
      description: "The task has been stopped and the connection closed.",
    });
  };

  const handleDeleteTask = () => {
    if (onDeleteTask) {
      // Clear task cache when deleting
      if (task.realTaskId) {
        stepsService.clearTaskCache(task.realTaskId);
      }
      
      onDeleteTask(taskId);
      if (onNavigateHome) {
        onNavigateHome();
      }
      toast({
        title: "Task deleted successfully.",
        description: "The task has been removed from your list.",
      });
    }
  };

  return (
    <div className="flex-1 bg-background overflow-y-auto">
      <div className="max-w-4xl mx-auto py-8 px-8">
        {/* Task Header */}
        <div className="mb-8">
          <div className="flex items-start justify-between mb-2">
            <h1 className="text-2xl font-semibold text-foreground">
              {task.name}
            </h1>
            {/* Stop/Delete Task Button */}
            {task.isRunning && (
              <div>
                {!isStopped ? (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={handleStopTask}
                    className="flex items-center gap-2"
                  >
                    <Square className="w-4 h-4" />
                    Stop Task
                  </Button>
                ) : (
                  <Button 
                    variant="destructive" 
                    size="sm"
                    onClick={handleDeleteTask}
                    className="flex items-center gap-2"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete Task
                  </Button>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span className="font-mono">
              {task.issueNumber ? `issue #${task.issueNumber}` : task.branch}
            </span>
            <span>•</span>
            <span>
              {task.isRunning && !isStopped ? 'Running for' : 'Completed in'} {formatDuration(duration)}
            </span>
            <span>•</span>
            <span>{progressPercentage}% complete</span>
          </div>
        </div>

        {/* Task Execution Steps */}
        {isLoadingSteps ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-3">
              <Rocket className="w-5 h-5 text-muted-foreground animate-pulse" />
              <span className="text-gray-500">Loading execution plan...</span>
            </div>
          </div>
        ) : taskProgress ? (
          <div className="space-y-4">
            {taskProgress.phases.map((phase, index) => (
              <PhaseComponent 
                key={`${phase.name}-${index}`}
                phase={phase} 
              />
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <X className="w-8 h-8 text-red-500 mx-auto mb-2" />
              <p className="text-gray-500">Failed to load execution plan</p>
              <p className="text-sm text-gray-500">Unable to fetch task steps</p>
            </div>
          </div>
        )}

        {/* Pull Request Section */}
        {task.pr && (
          <div className="mt-8">
            <h2 className="text-lg font-medium text-foreground mb-4">Pull Request</h2>
            <PRComponent pr={task.pr} />
          </div>
        )}

        {/* Error State */}
        {task.status === "failed" && task.errorMessage && (
          <div className="mt-8">
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-sm font-medium text-red-800 dark:text-red-200 mb-1">
                    Task execution failed
                  </h3>
                  <p className="text-sm text-red-700 dark:text-red-300">
                    {task.errorMessage}
                  </p>
                </div>
                <Button 
                  variant="destructive" 
                  size="sm"
                  onClick={handleDeleteTask}
                  className="flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete Task
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}