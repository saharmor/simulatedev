import { useState } from "react";
import { LoginScreen } from "../components/LoginScreen";
import { Sidebar } from "../components/Sidebar";
import { HomeScreen } from "../components/HomeScreen";
import { TaskScreen } from "../components/TaskScreen";
import { CommandPalette } from "../components/CommandPalette";
import { NavigationHeader } from "../components/NavigationHeader";

type Screen = 'login' | 'home' | 'task';

const Index = () => {
  const [currentScreen, setCurrentScreen] = useState<Screen>('login');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  const handleLogin = () => {
    setCurrentScreen('home');
  };

  const handleLogout = () => {
    setCurrentScreen('login');
    setSelectedTaskId(null);
  };

  const handleTaskSelect = (taskId: string) => {
    setSelectedTaskId(taskId);
    setCurrentScreen('task');
  };

  const handleTaskStart = (issueId: string) => {
    // In a real app, this would create a new task
    // For now, just select an existing task for demo
    setSelectedTaskId('1');
    setCurrentScreen('task');
  };

  const handleHomeSelect = () => {
    setCurrentScreen('home');
    setSelectedTaskId(null);
  };

  const handleCommandK = () => {
    setIsCommandPaletteOpen(true);
  };

  // Get current task name for navigation
  const getCurrentTaskName = () => {
    if (!selectedTaskId) return undefined;
    const mockTaskData = {
      '1': 'Implement Playwright best practices for robust web automation',
      '2': 'Improve README formatting', 
      '3': 'Add DiffUtil to RecyclerView for better performance',
      '4': 'Integrate MonsterAPI for Advanced Audio Transcription'
    };
    return mockTaskData[selectedTaskId as keyof typeof mockTaskData];
  };

  if (currentScreen === 'login') {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        tasks={[]}
        onTaskSelect={handleTaskSelect}
        onLogout={handleLogout}
        selectedTaskId={selectedTaskId}
      />
      
      <div className="flex-1 flex flex-col">
        <NavigationHeader
          currentScreen={currentScreen}
          taskName={getCurrentTaskName()}
          onHomeClick={handleHomeSelect}
        />
        
        {currentScreen === 'home' && (
          <HomeScreen 
            onTaskStart={handleTaskStart}
            onCommandK={handleCommandK}
          />
        )}
        
        {currentScreen === 'task' && selectedTaskId && (
          <TaskScreen taskId={selectedTaskId} />
        )}
      </div>

      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onTaskSelect={handleTaskSelect}
        onHomeSelect={handleHomeSelect}
      />
    </div>
  );
};

export default Index;
