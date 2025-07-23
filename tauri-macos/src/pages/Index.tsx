import { useState, useEffect } from "react";
import { LoginScreen } from "../components/LoginScreen";
import { StartupScreen } from "../components/StartupScreen";
import { ConnectionFailedScreen } from "../components/ConnectionFailedScreen";
import { Sidebar } from "../components/Sidebar";
import { HomeScreen } from "../components/HomeScreen";
import { TaskScreen } from "../components/TaskScreen";
import { CommandPalette } from "../components/CommandPalette";
import { NavigationHeader } from "../components/NavigationHeader";
import { useDeepLink } from "../hooks/useDeepLink";
import { healthCheckService, HealthCheckResult } from "../services/healthCheck";

type Screen = 'startup' | 'connection-failed' | 'login' | 'home' | 'task';

const Index = () => {
  const [currentScreen, setCurrentScreen] = useState<Screen>('startup');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isServerHealthy, setIsServerHealthy] = useState(false);
  const [hasStartedUp, setHasStartedUp] = useState(false);
  const { deepLinkUrl, parseDeepLink, clearDeepLink } = useDeepLink();

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

  const handleTaskStart = (_issueId: string) => {
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

  // Handle retry connection
  const handleRetryConnection = async () => {
    setCurrentScreen('startup');
    healthCheckService.resetFailureCount();
    const result = await healthCheckService.checkHealth();
    handleHealthCheck(result);
  };

  // Handle health check results
  const handleHealthCheck = (result: HealthCheckResult) => {
    const consecutiveFailures = result.consecutiveFailures || 0;
    setIsServerHealthy(result.isHealthy);
    
    if (result.isHealthy && (currentScreen === 'startup' || currentScreen === 'connection-failed')) {
      if (!hasStartedUp) {
        setHasStartedUp(true);
      }
      setCurrentScreen('login');
    } else if (!result.isHealthy) {
      // If we're in initial startup phase, show connection failed after 3 consecutive failures
      if (!hasStartedUp && currentScreen === 'startup' && consecutiveFailures >= 3) {
        setCurrentScreen('connection-failed');
      }
      // If app has already started up and connection is lost, show startup with reconnecting message
      else if (hasStartedUp && currentScreen !== 'startup' && currentScreen !== 'connection-failed') {
        setCurrentScreen('startup');
      }
    }
  };

  // Initialize health checks on component mount
  useEffect(() => {
    const initializeHealthCheck = async () => {
      // Perform initial health check
      const initialResult = await healthCheckService.checkHealth();
      handleHealthCheck(initialResult);
      
      // Start periodic health checks
      healthCheckService.startPeriodicHealthChecks(handleHealthCheck);
    };

    initializeHealthCheck();

    // Cleanup on unmount
    return () => {
      healthCheckService.stopPeriodicHealthChecks();
    };
  }, []);

  // Handle health check affecting current screen
  useEffect(() => {
    if (!isServerHealthy && currentScreen !== 'startup' && currentScreen !== 'connection-failed') {
      setCurrentScreen('startup');
    }
  }, [isServerHealthy, currentScreen]);

  // Handle deep link navigation
  useEffect(() => {
    if (deepLinkUrl && isServerHealthy) {
      const parsed = parseDeepLink(deepLinkUrl);
      if (parsed) {
        switch (parsed.path) {
          case '/login':
            setCurrentScreen('login');
            break;
          case '/home':
            setCurrentScreen('home');
            break;
          case '/task':
            const taskId = parsed.params.id;
            if (taskId) {
              setSelectedTaskId(taskId);
              setCurrentScreen('task');
            } else {
              setCurrentScreen('home');
            }
            break;
          default:
            // Unknown path, default to home if logged in, login otherwise
            setCurrentScreen(currentScreen === 'login' ? 'login' : 'home');
            break;
        }
      }
      clearDeepLink();
    }
  }, [deepLinkUrl, parseDeepLink, clearDeepLink, currentScreen, isServerHealthy]);

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

  if (currentScreen === 'startup') {
    const message = hasStartedUp ? "CONNECTION WITH SERVER LOST, REESTABLISHING..." : "STARTING UP...";
    return <StartupScreen message={message} />;
  }

  if (currentScreen === 'connection-failed') {
    return <ConnectionFailedScreen onRetry={handleRetryConnection} />;
  }

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
