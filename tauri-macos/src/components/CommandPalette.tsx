import { useState, useEffect } from "react";
import { Search, Home, GitBranch, GitPullRequest, GitMerge, X, Palette } from "lucide-react";
import { useTheme } from "next-themes";

interface Task {
  id: string;
  name: string;
  status: "ongoing" | "pending_pr" | "merged" | "rejected" | "failed";
  branch: string;
  repo: string;
  isRunning?: boolean;
  issueNumber?: number;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskSelect: (taskId: string) => void;
  onHomeSelect: () => void;
  tasks: Task[];
}

function getStatusIcon(status: Task["status"]) {
  switch (status) {
    case "ongoing":
      return <GitBranch className="w-4 h-4 text-gray-500" />;
    case "pending_pr":
      return <GitPullRequest className="w-4 h-4 text-green-600" />;
    case "merged":
      return <GitMerge className="w-4 h-4 text-green-600" />;
    case "rejected":
      return <X className="w-4 h-4 text-red-500" />;
    case "failed":
      return <X className="w-4 h-4 text-red-500" />;
  }
}

export function CommandPalette({ isOpen, onClose, onTaskSelect, onHomeSelect, tasks }: CommandPaletteProps) {
  const [search, setSearch] = useState('');
  const { theme, setTheme } = useTheme();
  
  const mockActions = [
    { 
      id: 'theme', 
      label: `Toggle Theme (Current: ${theme || 'system'})`, 
      icon: Palette,
      action: () => {
        const themes = ['light', 'dark', 'system'];
        const currentIndex = themes.indexOf(theme || 'system');
        const nextIndex = (currentIndex + 1) % themes.length;
        setTheme(themes[nextIndex]);
      }
    }
  ];

  useEffect(() => {
    if (isOpen) {
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose();
        }
      };
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Filter tasks based on search query (task name or issue number)
  const filteredTasks = tasks.filter(task => {
    const searchLower = search.toLowerCase();
    const taskNameLower = task.name.toLowerCase();
    const issueNumber = task.issueNumber?.toString() || '';
    
    return taskNameLower.includes(searchLower) || issueNumber.includes(searchLower);
  });

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-start justify-center pt-32">
      <div className="bg-card border border-gray-300 rounded-lg shadow-2xl w-full max-w-md mx-4">
        {/* Search Input */}
        <div className="flex items-center gap-3 p-4 border-b border-gray-200">
          <Search className="w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search tasks by name or issue number..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm"
            autoFocus
          />
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {/* Navigation */}
          <div className="p-2">
            <div className="px-3 py-1">
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                NAVIGATION
              </h3>
            </div>
            <button
              onClick={() => {
                onHomeSelect();
                onClose();
              }}
              className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm hover:bg-gray-100"
            >
              <Home className="w-4 h-4 text-gray-600" />
              <span>Home</span>
            </button>
          </div>

          {/* Tasks */}
          {filteredTasks.length > 0 && (
            <div className="p-2">
              <div className="px-3 py-1">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  TASKS
                </h3>
              </div>
              {filteredTasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => {
                    onTaskSelect(task.id);
                    onClose();
                  }}
                  className="w-full flex items-start gap-3 px-3 py-2 rounded text-sm hover:bg-gray-100 text-left"
                >
                  {getStatusIcon(task.status)}
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-gray-500 font-mono mb-1">
                      {task.issueNumber ? `issue #${task.issueNumber}` : task.branch}
                    </div>
                    <div className="text-sm text-gray-900 leading-relaxed">
                      {task.name}
                    </div>
                    {task.isRunning && (
                      <div className="flex items-center gap-2 mt-1">
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
                        <span className="text-xs text-gray-500">
                          Working...
                        </span>
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Show message when no tasks match search */}
          {search && filteredTasks.length === 0 && (
            <div className="p-2">
              <div className="px-3 py-2 text-sm text-gray-500">
                No tasks found matching "{search}"
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="p-2">
            <div className="px-3 py-1">
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                ACTIONS
              </h3>
            </div>
            {mockActions.map((action) => (
              <button
                key={action.id}
                onClick={() => {
                  action.action();
                  onClose();
                }}
                className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm hover:bg-gray-100"
              >
                <action.icon className="w-4 h-4 text-gray-600" />
                <span>{action.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}