import { useState, useEffect } from "react";
import { ExternalLink, FileText, Plus, Minus, GitPullRequest, GitMerge, X, Rocket } from "lucide-react";
import { Button } from "./ui/button";

interface TaskScreenProps {
  taskId: string;
  task?: {
    id: string;
    name: string;
    status: "ongoing" | "pending_pr" | "merged" | "rejected";
    branch: string;
    repo: string;
    isRunning?: boolean;
    issueId?: string;
    issueNumber?: number;
    createdAt: Date;
    // Task execution phases
    phase?: "working" | "creating_pr" | "completed";
    workingCompletedAt?: Date;
    prCreatedAt?: Date;
    completedAt?: Date;
    // Mock task properties for compatibility
    startTime?: number;
    pr?: any;
  };
}

interface PRData {
  title: string;
  branch: string;
  filesChanged: number;
  additions: number;
  deletions: number;
  status: 'open' | 'merged' | 'closed';
}

const mockTaskData = {
  '1': {
    name: 'Implement Playwright best practices for robust web automation',
    branch: 'ethanzrd/simulatedev',
    isRunning: true,
    startTime: Date.now() - 1000 * 60 * 23, // 23 minutes ago
    pr: null
  },
  '3': {
    name: 'Add DiffUtil to RecyclerView for better performance',
    branch: 'devin/performance-improvements',
    isRunning: false,
    startTime: Date.now() - 1000 * 60 * 60 * 2, // 2 hours ago
    pr: {
      title: 'Performance improvements: Add DiffUtil to RecyclerView',
      branch: 'devin/1751818808-efficiency-improvements',
      filesChanged: 2,
      additions: 202,
      deletions: 3,
      status: 'open' as const
    }
  }
};

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
        <Button variant="ghost" size="sm" className="text-gray-500 hover:text-gray-700 ml-2">
          <ExternalLink className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

export function TaskScreen({ taskId, task: passedTask }: TaskScreenProps) {
  const [currentTime, setCurrentTime] = useState(Date.now());
  
  // Use passed task data if available, otherwise fall back to mock data
  const task = passedTask || mockTaskData[taskId as keyof typeof mockTaskData];
  
  // For real tasks, calculate duration from createdAt, for mock tasks use startTime
  const startTime = passedTask ? passedTask.createdAt.getTime() : (task as any)?.startTime;

  useEffect(() => {
    if (task?.isRunning) {
      const interval = setInterval(() => {
        setCurrentTime(Date.now());
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [task?.isRunning]);

  if (!task) {
    return (
      <div className="flex-1 bg-background overflow-y-auto flex items-center justify-center">
        <p className="text-gray-500">Task not found</p>
      </div>
    );
  }

  const duration = startTime ? currentTime - startTime : 0;

  return (
    <div className="flex-1 bg-background overflow-y-auto">
      <div className="max-w-4xl mx-auto py-8 px-8">
        {/* Task Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">
            {task.name}
          </h1>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span className="font-mono">{task.branch}</span>
            <span>•</span>
            <span>
              {task.isRunning ? 'Running for' : 'Completed in'} {formatDuration(duration)}
            </span>
          </div>
        </div>

        {/* Task Execution Phases */}
        <div className="space-y-4">
          {/* Phase 1: Agent Working */}
          <div className="flex items-center gap-3">
            <Rocket className={`w-6 h-6 text-foreground ${passedTask?.phase === "working" ? "animate-pulse" : ""}`} />
            <div>
              <span className="text-sm text-foreground">Agent is working...</span>
              {passedTask?.phase === "working" ? (
                <p className="text-xs text-gray-500 mt-1">
                  Duration: {formatDurationInSeconds(currentTime - passedTask.createdAt.getTime())}
                </p>
              ) : passedTask?.workingCompletedAt ? (
                <p className="text-xs text-gray-500 mt-1">
                  Completed in: {formatDurationInSeconds(passedTask.workingCompletedAt.getTime() - passedTask.createdAt.getTime())}
                </p>
              ) : null}
            </div>
          </div>

          {/* Phase 2: Creating PR */}
          {(passedTask?.phase === "creating_pr" || passedTask?.phase === "completed") && (
            <div className="flex items-center gap-3">
              <Rocket className={`w-6 h-6 text-foreground ${passedTask?.phase === "creating_pr" ? "animate-pulse" : ""}`} />
              <div>
                <span className="text-sm text-foreground">Creating PR...</span>
                {passedTask?.phase === "creating_pr" ? (
                  <p className="text-xs text-gray-500 mt-1">
                    Duration: {formatDurationInSeconds(currentTime - (passedTask.workingCompletedAt?.getTime() || passedTask.createdAt.getTime()))}
                  </p>
                ) : passedTask?.prCreatedAt && passedTask?.workingCompletedAt ? (
                  <p className="text-xs text-gray-500 mt-1">
                    Completed in: {formatDurationInSeconds(passedTask.prCreatedAt.getTime() - passedTask.workingCompletedAt.getTime())}
                  </p>
                ) : null}
              </div>
            </div>
          )}

          {/* Phase 3: PR Created */}
          {passedTask?.phase === "completed" && (
            <div className="flex items-center gap-3">
              <Rocket className="w-6 h-6 text-foreground" />
              <div>
                <span className="text-sm text-foreground">PR Created!</span>
                {passedTask?.completedAt && passedTask?.prCreatedAt && (
                  <p className="text-xs text-gray-500 mt-1">
                    Completed in: {formatDurationInSeconds(passedTask.completedAt.getTime() - passedTask.prCreatedAt.getTime())}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Show PR Component when completed */}
        {passedTask?.phase === "completed" && passedTask?.pr && (
          <div className="mt-8">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Pull Request</h2>
            <PRComponent pr={passedTask.pr} />
          </div>
        )}

        {/* Fallback for mock tasks */}
        {!passedTask && task.isRunning && (
          <div className="flex items-center gap-3">
            <Rocket className="w-6 h-6 text-foreground animate-pulse" />
            <div>
              <span className="text-sm text-foreground">Agent is working...</span>
              <p className="text-xs text-gray-500 mt-1">
                Duration: {formatDuration(duration)}
              </p>
            </div>
          </div>
        )}

        {/* Fallback for mock tasks with PR */}
        {!passedTask && !task.isRunning && (task as any)?.pr && (
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">Pull Request</h2>
            <PRComponent pr={(task as any).pr} />
          </div>
        )}
      </div>
    </div>
  );
}