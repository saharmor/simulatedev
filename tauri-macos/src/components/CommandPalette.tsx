import { useState, useEffect } from "react";
import { Search, Home, GitBranch, Palette } from "lucide-react";
import { useTheme } from "next-themes";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskSelect: (taskId: string) => void;
  onHomeSelect: () => void;
}

const mockWorkspaces = [
  'Dhaka', 'Tunis', 'Khartoum', 'Kingston', 'Dublin', 
  'Hyderabad', 'Tikal', 'Albany', 'Asmara', 'Bangui'
];

export function CommandPalette({ isOpen, onClose, onTaskSelect: _onTaskSelect, onHomeSelect }: CommandPaletteProps) {
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

  const filteredWorkspaces = mockWorkspaces.filter(workspace =>
    workspace.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-start justify-center pt-32">
      <div className="bg-card border border-gray-300 rounded-lg shadow-2xl w-full max-w-md mx-4">
        {/* Search Input */}
        <div className="flex items-center gap-3 p-4 border-b border-gray-200">
          <Search className="w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Type a command or search..."
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

          {/* Workspaces */}
          {filteredWorkspaces.length > 0 && (
            <div className="p-2">
              <div className="px-3 py-1">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  WORKSPACES
                </h3>
              </div>
              {filteredWorkspaces.map((workspace) => (
                <button
                  key={workspace}
                  onClick={() => {
                    // Handle workspace selection
                    onClose();
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm hover:bg-gray-100"
                >
                  <GitBranch className="w-4 h-4 text-gray-600" />
                  <span>{workspace}</span>
                </button>
              ))}
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