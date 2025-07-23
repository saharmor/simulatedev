import { useState, useEffect } from "react";
import { ExternalLink, FileText, Plus, Minus, GitPullRequest, GitMerge, X } from "lucide-react";
import { Button } from "./ui/button";

interface TaskScreenProps {
  taskId: string;
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

export function TaskScreen({ taskId }: TaskScreenProps) {
  const [currentTime, setCurrentTime] = useState(Date.now());
  const task = mockTaskData[taskId as keyof typeof mockTaskData];

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
      <div className="flex-1 bg-background flex items-center justify-center">
        <p className="text-gray-500">Task not found</p>
      </div>
    );
  }

  const duration = currentTime - task.startTime;

  return (
    <div className="flex-1 bg-background">
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

        {/* Status */}
        {task.isRunning ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
            <div className="flex items-center justify-center gap-3 mb-2">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
              <span className="text-sm text-gray-600">Agent is working on this task...</span>
            </div>
            <p className="text-xs text-gray-500">
              Duration: {formatDuration(duration)}
            </p>
          </div>
        ) : (
          task.pr && (
            <div>
              <h2 className="text-lg font-medium text-gray-900 mb-4">Pull Request</h2>
              <PRComponent pr={task.pr} />
            </div>
          )
        )}
      </div>
    </div>
  );
}