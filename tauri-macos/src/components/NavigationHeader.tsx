import { Home, ChevronRight } from "lucide-react";
import { Button } from "./ui/button";

interface NavigationHeaderProps {
  currentScreen: 'home' | 'task';
  taskName?: string;
  onHomeClick: () => void;
}

export function NavigationHeader({ currentScreen, taskName, onHomeClick }: NavigationHeaderProps) {
  if (currentScreen === 'home') {
    return null; // Don't show navigation on home screen
  }

  return (
    <div className="border-b border-border bg-background px-6 py-3">
      <div className="flex items-center gap-2 text-sm">
        <Button
          variant="ghost"
          size="sm"
          onClick={onHomeClick}
          className="text-gray-600 hover:text-gray-900 p-1 h-auto"
        >
          <Home className="w-4 h-4" />
        </Button>
        
        {currentScreen === 'task' && taskName && (
          <>
            <ChevronRight className="w-3 h-3 text-gray-400" />
            <span className="text-gray-900 font-medium truncate max-w-md">
              {taskName}
            </span>
          </>
        )}
      </div>
    </div>
  );
}