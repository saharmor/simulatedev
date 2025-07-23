import { LogOut, GitBranch, GitPullRequest, GitMerge, X } from "lucide-react";
import { Button } from "./ui/button";

interface Task {
  id: string;
  name: string;
  status: 'ongoing' | 'pending_pr' | 'merged' | 'rejected';
  branch: string;
  repo: string;
  isRunning?: boolean;
}

interface SidebarProps {
  tasks: Task[];
  onTaskSelect: (taskId: string) => void;
  onLogout: () => void;
  selectedTaskId?: string;
}

const mockTasks: Task[] = [
  {
    id: '1',
    name: 'Implement Playwright best practices for robust web automation',
    status: 'ongoing',
    branch: 'ethanzrd/simulatedev',
    repo: 'simulatedev',
    isRunning: true
  },
  {
    id: '2',
    name: 'Improve README formatting',
    status: 'pending_pr',
    branch: 'feature/readme-update',
    repo: 'simulatedev'
  },
  {
    id: '3',
    name: 'Add DiffUtil to RecyclerView for better performance',
    status: 'merged',
    branch: 'devin/performance-improvements',
    repo: 'expense-tracker'
  },
  {
    id: '4',
    name: 'Integrate MonsterAPI for Advanced Audio Transcription',
    status: 'ongoing',
    branch: 'saharmor/whisper-playground',
    repo: 'whisper-playground'
  }
];

function getStatusIcon(status: Task['status']) {
  switch (status) {
    case 'ongoing':
      return <GitBranch className="w-3 h-3 text-warning" />;
    case 'pending_pr':
      return <GitPullRequest className="w-3 h-3 text-gray-500" />;
    case 'merged':
      return <GitMerge className="w-3 h-3 text-success" />;
    case 'rejected':
      return <X className="w-3 h-3 text-error" />;
  }
}

function LoadingDots() {
  return (
    <div className="flex space-x-1">
      <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
      <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
      <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
    </div>
  );
}

export function Sidebar({ onTaskSelect, onLogout, selectedTaskId }: SidebarProps) {
  const tasksByRepo = mockTasks.reduce((acc, task) => {
    if (!acc[task.repo]) {
      acc[task.repo] = [];
    }
    acc[task.repo].push(task);
    return acc;
  }, {} as Record<string, Task[]>);

  return (
    <div className="w-80 bg-sidebar border-r border-border flex flex-col h-screen">
      {/* Tasks */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {Object.entries(tasksByRepo).map(([repo, tasks]) => (
          <div key={repo} className="space-y-2">
            <h3 className="text-sm font-medium text-sidebar-foreground uppercase tracking-wide">
              {repo}
            </h3>
            <div className="space-y-1">
              {tasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => onTaskSelect(task.id)}
                  className={`w-full p-3 rounded-lg text-left hover:bg-gray-100 transition-colors ${
                    selectedTaskId === task.id ? 'bg-gray-100' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {getStatusIcon(task.status)}
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-500 font-mono mb-1">
                        {task.branch}
                      </div>
                      <div className="text-sm text-gray-900 leading-relaxed">
                        {task.name}
                      </div>
                      {task.isRunning && (
                        <div className="flex items-center gap-2 mt-2">
                          <LoadingDots />
                          <span className="text-xs text-gray-500">Working...</span>
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Logout */}
      <div className="p-4 border-t border-border">
        <Button
          onClick={onLogout}
          variant="ghost"
          className="w-full justify-start text-gray-600 hover:text-gray-900 hover:bg-gray-100"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Log out
        </Button>
      </div>
    </div>
  );
}