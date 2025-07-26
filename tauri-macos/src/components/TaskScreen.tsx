import { useState, useEffect } from "react";
import { ExternalLink, FileText, Plus, Minus, GitPullRequest, GitMerge, X, Rocket, Trash2, Square } from "lucide-react";
import { Button } from "./ui/button";
import { useToast } from "./ui/use-toast";
import { openUrl } from "@tauri-apps/plugin-opener";
import { websocketService } from "../services/websocketService";

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
    // Task execution phases
    phase?: "working" | "creating_pr" | "completed" | "failed";
    workingCompletedAt?: Date;
    prCreatedAt?: Date;
    completedAt?: Date;
    // Real task properties
    realTaskId?: string;
    currentPhase?: string;
    progress?: number;
    prUrl?: string;
    errorMessage?: string;
    pr?: PRData;
    // Phase history for accumulating phases
    phaseHistory?: Array<{
      phase: string;
      timestamp: Date;
      completed?: boolean;
      completedAt?: Date;
    }>;
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

function formatDurationInSeconds(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  return `${seconds}s`;
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
            <h3 className="text-sm font-medium text-gray-900 mb-1">
              {pr.title}
            </h3>
            <div className="flex items-center gap-4 text-xs text-gray-600">
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

function LoadingDots() {
  return (
    <div className="flex space-x-1">
      <div
        className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"
        style={{ animationDelay: "0ms" }}
      ></div>
      <div
        className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"
        style={{ animationDelay: "150ms" }}
      ></div>
      <div
        className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"
        style={{ animationDelay: "300ms" }}
      ></div>
    </div>
  );
}

export function TaskScreen({ taskId, task: passedTask, onDeleteTask, onNavigateHome }: TaskScreenProps) {
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [isStopped, setIsStopped] = useState(false);
  const { toast } = useToast();
  
  // Only use passed task data - no mock fallbacks
  const task = passedTask;

  useEffect(() => {
    if (task?.isRunning && !isStopped) {
      const interval = setInterval(() => {
        setCurrentTime(Date.now());
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [task?.isRunning, isStopped]);

  if (!task) {
    return (
      <div className="flex-1 bg-background overflow-y-auto flex items-center justify-center">
        <p className="text-gray-500">Task not found</p>
      </div>
    );
  }

  const duration = task.createdAt ? currentTime - task.createdAt.getTime() : 0;

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
            <h1 className="text-2xl font-semibold text-gray-900">
              {task.name}
            </h1>
            {/* Stop/Delete Task Button - Integrated in header */}
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
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span className="font-mono">{task.issueNumber ? `issue #${task.issueNumber}` : task.branch}</span>
            <span>•</span>
            <span>
              {task.isRunning && !isStopped ? 'Running for' : 'Completed in'} {formatDuration(duration)}
            </span>
            <span>•</span>
            <span>{task?.progress !== undefined ? `${task.progress}%` : '0%'} complete</span>
          </div>
        </div>

        {/* Task Execution Phases */}
        <div className="space-y-4">
          {/* Phase History - Show all phases that have occurred */}
          {task.phaseHistory && task.phaseHistory.length > 0 && (
            <>
              {task.phaseHistory.map((phaseEntry, index) => (
                <div key={index} className={`flex items-center ${phaseEntry.phase === "Task execution failed" ? "justify-between" : "gap-3"}`}>
                  <div className="flex items-center gap-3 flex-1">
                    <Rocket className={`w-4 h-4 ${phaseEntry.phase === "Task execution failed" ? "text-red-500" : "text-foreground"} ${!phaseEntry.completed ? "animate-pulse" : ""}`} />
                    <div className="flex items-center gap-4 flex-1">
                      <span className={`text-sm ${phaseEntry.phase === "Task execution failed" ? "text-red-500 font-medium" : "text-foreground"}`}>
                        {phaseEntry.completed ? phaseEntry.phase : phaseEntry.phase}
                      </span>
                      {phaseEntry.completed && phaseEntry.completedAt && phaseEntry.phase !== "Task execution failed" && phaseEntry.phase !== "Task completed successfully!" ? (
                        <span className={`text-xs font-mono ${phaseEntry.phase === "Task execution failed" ? "text-red-600" : "text-gray-500"}`}>
                          Completed in: {formatDurationInSeconds(phaseEntry.completedAt.getTime() - phaseEntry.timestamp.getTime())}
                        </span>
                      ) : !phaseEntry.completed && phaseEntry.phase !== "Task execution failed" && (
                        <span className="text-xs text-gray-500 font-mono">
                          Duration: {formatDurationInSeconds(currentTime - phaseEntry.timestamp.getTime())}
                        </span>
                      )}
                    </div>
                    {phaseEntry.phase === "Task execution failed" && task.errorMessage && (
                      <p className="text-xs text-red-600">
                        Error: {task.errorMessage}
                      </p>
                    )}
                  </div>
                  {phaseEntry.phase === "Task execution failed" && (
                    <div className="flex items-center">
                      <Button 
                        variant="destructive" 
                        onClick={handleDeleteTask}
                        className="flex items-center gap-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        Delete Task
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

          {/* Current Active Phase (if not in history yet) */}
          {task.phase !== "failed" && task?.currentPhase && !task.phaseHistory?.some(p => p.phase === task.currentPhase) && (
            <div className="flex items-center gap-3">
              <Rocket className={`w-4 h-4 text-foreground ${task.isRunning && !isStopped ? "animate-pulse" : ""}`} />
              <div className="flex items-center gap-4 flex-1">
                <span className="text-sm text-foreground">{task.currentPhase}</span>
                {task?.isRunning && !isStopped && (
                  <span className="text-xs text-gray-500 font-mono">
                    Duration: {formatDurationInSeconds(currentTime - task.createdAt.getTime())}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Legacy Phase Display for Backward Compatibility */}
          {task.phase !== "failed" && !task?.currentPhase && !task.phaseHistory && (
            <>
              {/* Phase 1: Connecting to server */}
              <div className="flex items-center gap-3">
                <Rocket className={`w-4 h-4 text-foreground ${task.phase === "working" && !isStopped ? "animate-pulse" : ""}`} />
                <div className="flex items-center gap-4 flex-1">
                  <span className="text-sm text-foreground">Connecting to server...</span>
                  {task.phase === "working" && !isStopped ? (
                    <span className="text-xs text-gray-500 font-mono">
                      Duration: {formatDurationInSeconds(currentTime - task.createdAt.getTime())}
                    </span>
                  ) : task?.workingCompletedAt ? (
                    <span className="text-xs text-gray-500 font-mono">
                      Completed in: {formatDurationInSeconds(task.workingCompletedAt.getTime() - task.createdAt.getTime())}
                    </span>
                  ) : null}
                </div>
              </div>

              {/* Phase 2: Creating PR */}
              {(task.phase === "creating_pr" || task.phase === "completed") && (
                <div className="flex items-center gap-3">
                  <Rocket className={`w-4 h-4 text-foreground ${task.phase === "creating_pr" && !isStopped ? "animate-pulse" : ""}`} />
                  <div className="flex items-center gap-4 flex-1">
                    <span className="text-sm text-foreground">Creating PR...</span>
                    {task.phase === "creating_pr" && !isStopped ? (
                      <span className="text-xs text-gray-500 font-mono">
                        Duration: {formatDurationInSeconds(currentTime - (task.workingCompletedAt?.getTime() || task.createdAt.getTime()))}
                      </span>
                    ) : task?.prCreatedAt && task?.workingCompletedAt ? (
                      <span className="text-xs text-gray-500 font-mono">
                        Completed in: {formatDurationInSeconds(task.prCreatedAt.getTime() - task.workingCompletedAt.getTime())}
                      </span>
                    ) : null}
                  </div>
                </div>
              )}

              {/* Phase 3: PR Created */}
              {task.phase === "completed" && (
                <div className="flex items-center gap-3">
                  <Rocket className="w-4 h-4 text-foreground" />
                  <div className="flex items-center gap-4 flex-1">
                    <span className="text-sm text-foreground">PR Created!</span>
                    {task?.completedAt && task?.prCreatedAt && (
                      <span className="text-xs text-gray-500 font-mono">
                        Completed in: {formatDurationInSeconds(task.completedAt.getTime() - task.prCreatedAt.getTime())}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Show PR Component when completed or show Fetching PR with loading */}
        {task.phase === "completed" && (
          <div className="mt-8">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Pull Request</h2>
            {task?.pr ? (
              <PRComponent pr={task.pr} />
            ) : (
              <div className="bg-card border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <Rocket className="w-4 h-4 text-foreground animate-pulse" />
                  <div>
                    <span className="text-sm text-foreground">Fetching PR...</span>
                    <div className="mt-2">
                      <LoadingDots />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}