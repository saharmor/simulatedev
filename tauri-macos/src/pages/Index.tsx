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
import { authService, User } from "../services/authService";
import { apiService, TaskExecutionRequest } from "../services/apiService";
import { websocketService, WebSocketCallbacks } from "../services/websocketService";

type Screen = "startup" | "connection-failed" | "login" | "home" | "task";

interface Task {
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
  phase: "working" | "creating_pr" | "completed" | "failed";
  workingCompletedAt?: Date;
  prCreatedAt?: Date;
  completedAt?: Date;
  pr?: {
    title: string;
    branch: string;
    filesChanged: number;
    additions: number;
    deletions: number;
    status: 'open' | 'merged' | 'closed';
    url?: string;
  };
  // Real task properties
  realTaskId?: string;
  currentPhase?: string;
  progress?: number;
  prUrl?: string;
  errorMessage?: string;
  // Phase history for accumulating phases
  phaseHistory?: Array<{
    phase: string;
    timestamp: Date;
    completed?: boolean;
    completedAt?: Date;
  }>;
}

const Index = () => {
  const [currentScreen, setCurrentScreen] = useState<Screen>("startup");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isServerHealthy, setIsServerHealthy] = useState(false);
  const [hasStartedUp, setHasStartedUp] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const { deepLinkUrl, parseDeepLink, clearDeepLink } = useDeepLink();

  const handleLogin = () => {
    setCurrentScreen("home");
  };

  const handleLogout = () => {
    console.log("[Index] User logout initiated");
    console.log(
      `[Index] Clearing auth data for user: ${user?.github_username}`
    );
    authService.clearAuthData();
    setUser(null);
    console.log("[Index] Navigating to login screen after logout");
    setCurrentScreen("login");
    setSelectedTaskId(null);
    console.log("[Index] Logout completed successfully");
  };

  const handleTaskSelect = (taskId: string) => {
    setSelectedTaskId(taskId);
    setCurrentScreen("task");
  };

  const handleTaskStart = async (issue: { id: string; title: string; number: number; htmlUrl: string; user: string }, agent: { id: string; name: string; description: string; icon: string }, repository?: { name: string; full_name: string }) => {
    console.log(`[Index] Creating task for issue: ${issue.title} with agent: ${agent.name}`);
    
    // Generate a unique task ID for frontend tracking
    const taskId = `task-${Date.now()}-${issue.id}`;
    
    // Create a new task from the issue data
    const newTask: Task = {
      id: taskId,
      name: issue.title,
      status: "ongoing",
      branch: `feature/issue-${issue.number}`,
      repo: repository?.name || "current-repo",
      isRunning: true,
      issueId: issue.id,
      issueNumber: issue.number,
      createdAt: new Date(),
      phase: "working"
    };
    
    // Add the task to the tasks array
    setTasks(prevTasks => [...prevTasks, newTask]);
    
    // Select this task and navigate to task screen
    setSelectedTaskId(taskId);
    setCurrentScreen("task");
    
    console.log(`[Index] Task created with ID: ${taskId}`);
    
    try {
      // Prepare task execution request with hardcoded prompt
      const taskRequest: TaskExecutionRequest = {
        issue_url: issue.htmlUrl,
        agents: [{
          coding_ide: agent.id,
          model: "claude-sonnet-4",
          role: "Coder"
        }],
        workflow_type: "custom",
        create_pr: true,
        task_prompt: "Find grammatical issues in the readme file and fix them",
        issue_number: issue.number,
        issue_title: issue.title
      };

      console.log(`[Index] Executing task with request:`, taskRequest);
      
      // Execute task via backend API
      const response = await apiService.executeTask(taskRequest);
      console.log(`[Index] Task execution response:`, response);
      
      // Update task with real task ID
      setTasks(prevTasks => 
        prevTasks.map(task => 
          task.id === taskId 
            ? { ...task, realTaskId: response.task_id }
            : task
        )
      );
      
      // Start WebSocket connection for real-time updates
      startWebSocketConnection(response.task_id, taskId);
      
    } catch (error) {
      console.error(`[Index] Failed to execute task:`, error);
      // Update task status to failed
      setTasks(prevTasks => 
        prevTasks.map(task => 
          task.id === taskId 
            ? { 
                ...task, 
                isRunning: false, 
                status: "failed" as const,
                phase: "failed" as const,
                errorMessage: error instanceof Error ? error.message : String(error)
              }
            : task
        )
      );
    }
  };

  const startWebSocketConnection = (realTaskId: string, frontendTaskId: string) => {
    console.log(`[Index] Starting WebSocket connection for real task: ${realTaskId}, frontend task: ${frontendTaskId}`);
    
    const callbacks: WebSocketCallbacks = {
      onOpen: () => {
        console.log(`[Index] WebSocket connected for task: ${realTaskId}`);
      },
      onProgress: (data) => {
        console.log(`[Index] Received progress update for task ${realTaskId}:`, data);
        console.log(`[Index] Progress data JSON:`, JSON.stringify(data, null, 2));
        console.log(`[Index] Progress type: ${data.type}`);
        console.log(`[Index] Progress task_id: ${data.task_id}`);
        console.log(`[Index] Progress progress: ${data.progress}`);
        console.log(`[Index] Progress current_phase: ${data.current_phase}`);
        console.log(`[Index] Progress timestamp: ${data.timestamp}`);
        console.log(`[Index] Progress message: ${data.message}`);
        
        setTasks(prevTasks => 
          prevTasks.map(task => {
            if (task.id === frontendTaskId) {
              console.log(`[Index] Updating task: ${task.id}`);
              console.log(`[Index] Current task state:`, task);
              
              const updatedTask = { ...task };
              
              // Update progress
              if (data.progress !== undefined) {
                console.log(`[Index] Updating progress from ${updatedTask.progress} to ${data.progress}`);
                updatedTask.progress = data.progress;
              }
              
              // Update current phase and add to history
              if (data.current_phase) {
                console.log(`[Index] Processing current_phase: ${data.current_phase}`);
                
                // Initialize phase history if it doesn't exist
                if (!updatedTask.phaseHistory) {
                  console.log(`[Index] Initializing phase history for task`);
                  updatedTask.phaseHistory = [];
                  
                  // Add "Connecting to server..." as the first phase if we're just starting
                  if (updatedTask.phase === "working") {
                    console.log(`[Index] Adding "Connecting to server..." as first phase`);
                    updatedTask.phaseHistory.push({
                      phase: "Connecting to server...",
                      timestamp: updatedTask.createdAt,
                      completed: true,
                      completedAt: new Date()
                    });
                  }
                }
                
                // Check if this phase is already in history
                const existingPhaseIndex = updatedTask.phaseHistory.findIndex(p => p.phase === data.current_phase);
                console.log(`[Index] Existing phase index: ${existingPhaseIndex}`);
                
                if (existingPhaseIndex === -1) {
                  console.log(`[Index] Adding new phase to history: ${data.current_phase}`);
                  
                  // Mark the previous phase as completed (if any)
                  if (updatedTask.phaseHistory.length > 0) {
                    const lastPhase = updatedTask.phaseHistory[updatedTask.phaseHistory.length - 1];
                    if (!lastPhase.completed) {
                      console.log(`[Index] Marking previous phase as completed: ${lastPhase.phase}`);
                      lastPhase.completed = true;
                      lastPhase.completedAt = new Date();
                    }
                  }
                  
                  // Add new phase to history
                  updatedTask.phaseHistory.push({
                    phase: data.current_phase,
                    timestamp: new Date(),
                    completed: false
                  });
                }
                
                updatedTask.currentPhase = data.current_phase;
                console.log(`[Index] Updated currentPhase to: ${updatedTask.currentPhase}`);
                
                // Map backend phases to frontend phases
                if (data.current_phase.includes("Initializing") || data.current_phase.includes("Creating task request")) {
                  console.log(`[Index] Mapping phase to "working"`);
                  updatedTask.phase = "working";
                } else if (data.current_phase.includes("Processing results") || data.current_phase.includes("completed")) {
                  console.log(`[Index] Mapping phase to "completed"`);
                  updatedTask.phase = "completed";
                  updatedTask.isRunning = false;
                  updatedTask.status = "pending_pr";
                  updatedTask.completedAt = new Date();
                  
                  // Mark the last phase as completed
                  if (updatedTask.phaseHistory.length > 0) {
                    const lastPhase = updatedTask.phaseHistory[updatedTask.phaseHistory.length - 1];
                    console.log(`[Index] Marking final phase as completed: ${lastPhase.phase}`);
                    lastPhase.completed = true;
                    lastPhase.completedAt = new Date();
                  }
                }
              }
              
              console.log(`[Index] Updated task state:`, updatedTask);
              console.log(`[Index] Phase history:`, updatedTask.phaseHistory);
              
              return updatedTask;
            }
            return task;
          })
        );
        
        // Close WebSocket connection when progress reaches 100%
        if (data.progress === 100) {
          console.log(`[Index] Progress reached 100%, closing WebSocket connection for task ${realTaskId}`);
          websocketService.disconnect();
          
          // Mark the previous phase as completed
          setTasks(prevTasks => 
            prevTasks.map(task => {
              if (task.id === frontendTaskId) {
                const updatedTask = { ...task };
                
                if (updatedTask.phaseHistory && updatedTask.phaseHistory.length > 0) {
                  const lastPhase = updatedTask.phaseHistory[updatedTask.phaseHistory.length - 1];
                  if (!lastPhase.completed) {
                    lastPhase.completed = true;
                    lastPhase.completedAt = new Date();
                  }
                }
                
                console.log(`[Index] Marked final phase as completed for task ${frontendTaskId}`);
                
                return updatedTask;
              }
              return task;
            })
          );
          
          // Fetch task completion details
          fetchTaskCompletionDetails(realTaskId, frontendTaskId);
        }
      },
      onError: (error) => {
        console.error(`[Index] WebSocket error for task ${realTaskId}:`, error);
        // Update task status to failed
        setTasks(prevTasks => 
          prevTasks.map(task => {
            if (task.id === frontendTaskId) {
              const updatedTask = { ...task };
              
              // Mark the current phase as completed (if any)
              if (updatedTask.phaseHistory && updatedTask.phaseHistory.length > 0) {
                const lastPhase = updatedTask.phaseHistory[updatedTask.phaseHistory.length - 1];
                if (!lastPhase.completed) {
                  lastPhase.completed = true;
                  lastPhase.completedAt = new Date();
                }
              }
              
              // Add error as a new phase in history (only if it doesn't already exist)
              if (!updatedTask.phaseHistory) {
                updatedTask.phaseHistory = [];
              }
              
              // Check if "Task execution failed" phase already exists
              const failedPhaseExists = updatedTask.phaseHistory.some(p => p.phase === "Task execution failed");
              
              if (!failedPhaseExists) {
                updatedTask.phaseHistory.push({
                  phase: "Task execution failed",
                  timestamp: new Date(),
                  completed: false // Don't mark as completed so it doesn't show "Completed in"
                });
              }
              
              return { 
                ...updatedTask, 
                isRunning: false, 
                status: "failed" as const,
                phase: "failed" as const,
                errorMessage: error
              };
            }
            return task;
          })
        );
      },
      onClose: () => {
        console.log(`[Index] WebSocket closed for task: ${realTaskId}`);
      }
    };
    
    websocketService.connect(realTaskId, callbacks);
  };

  const fetchTaskCompletionDetails = async (realTaskId: string, frontendTaskId: string) => {
    console.log(`[Index] Fetching completion details for task: ${realTaskId}`);
    
    try {
      // Get task status to check if it has PR URL
      const taskStatus = await apiService.getTaskStatus(realTaskId);
      console.log(`[Index] Task status:`, taskStatus);
      
      if (taskStatus.pr_url) {
        console.log(`[Index] Task completed with PR: ${taskStatus.pr_url}`);
        
        // Extract owner, repo, and PR number from URL
        const prUrlMatch = taskStatus.pr_url.match(/github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/);
        if (prUrlMatch) {
          const [, owner, repo, prNumber] = prUrlMatch;
          console.log(`[Index] Extracted PR details: owner=${owner}, repo=${repo}, prNumber=${prNumber}`);
          
          // Fetch PR details
          const prDetails = await apiService.getPullRequest(owner, repo, parseInt(prNumber));
          console.log(`[Index] PR details:`, prDetails);
          
          // Update task with PR information and issue number
          setTasks(prevTasks => 
            prevTasks.map(task => {
              if (task.id === frontendTaskId) {
                return {
                  ...task,
                  pr: {
                    title: prDetails.title,
                    branch: prDetails.head_ref,
                    filesChanged: prDetails.changed_files,
                    additions: prDetails.additions,
                    deletions: prDetails.deletions,
                    status: prDetails.merged ? 'merged' : (prDetails.state === 'closed' ? 'closed' : 'open'),
                    url: prDetails.html_url
                  },
                  prUrl: taskStatus.pr_url
                };
              }
              return task;
            })
          );
        }
      } else {
        console.log(`[Index] Task completed but no PR URL found`);
        // Still update the issue number if provided by backend
        if (taskStatus.issue_number) {
          setTasks(prevTasks => 
            prevTasks.map(task => {
              if (task.id === frontendTaskId) {
                return {
                  ...task,
                  issueNumber: taskStatus.issue_number
                };
              }
              return task;
            })
          );
        }
      }
    } catch (error) {
      console.error(`[Index] Error fetching task completion details:`, error);
    }
  };



  const handleHomeSelect = () => {
    setCurrentScreen("home");
    setSelectedTaskId(null);
  };

  const handleDeleteTask = (taskId: string) => {
    console.log(`[Index] Deleting task: ${taskId}`);
    
    // Remove task from tasks array
    setTasks(prevTasks => prevTasks.filter(task => task.id !== taskId));
    
    // Clear selected task if it's the one being deleted
    if (selectedTaskId === taskId) {
      setSelectedTaskId(null);
    }
  };

  const handleCommandK = () => {
    setIsCommandPaletteOpen(true);
  };

  // Handle retry connection
  const handleRetryConnection = async () => {
    setCurrentScreen("startup");
    healthCheckService.resetFailureCount();
    const result = await healthCheckService.checkHealth();
    handleHealthCheck(result);
  };

  // Handle health check results - ONLY updates server health state
  const handleHealthCheck = (result: HealthCheckResult) => {
    const consecutiveFailures = result.consecutiveFailures || 0;
    console.log(
      `[Index] Health check result: ${
        result.isHealthy ? "HEALTHY" : "UNHEALTHY"
      }`
    );
    console.log(`[Index] Consecutive failures: ${consecutiveFailures}`);
    console.log(
      `[Index] Current screen: ${currentScreen}, Has started up: ${hasStartedUp}`
    );

    // Update server health state
    setIsServerHealthy(result.isHealthy);

    // Mark app as started up when server becomes healthy for the first time
    if (result.isHealthy && !hasStartedUp) {
      console.log("[Index] Server became healthy, marking app as started up");
      setHasStartedUp(true);
    }

    // Handle connection failure during initial startup
    if (
      !result.isHealthy &&
      !hasStartedUp &&
      currentScreen === "startup" &&
      consecutiveFailures >= 3
    ) {
      console.log(
        "[Index] Initial startup failed after 3 attempts, showing connection failed screen"
      );
      setCurrentScreen("connection-failed");
    }

    // Handle connection loss after startup
    if (
      !result.isHealthy &&
      hasStartedUp &&
      currentScreen !== "startup" &&
      currentScreen !== "connection-failed"
    ) {
      console.log(
        "[Index] Connection lost after startup, showing reconnecting screen"
      );
      setCurrentScreen("startup");
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

  // App routing logic - determines appropriate screen based on state
  useEffect(() => {
    const determineScreen = () => {
      console.log("[Index] Determining appropriate screen");
      console.log(
        `[Index] Server healthy: ${isServerHealthy}, Has started up: ${hasStartedUp}, User: ${
          user?.github_username || "none"
        }, Current screen: ${currentScreen}`
      );

      // Don't change screen if server is unhealthy (let health check handler manage startup/connection-failed)
      if (!isServerHealthy) {
        console.log("[Index] Server unhealthy, not changing screen");
        return;
      }

      // Don't change screen if app hasn't started up yet
      if (!hasStartedUp) {
        console.log(
          "[Index] App not started up yet, staying on startup screen"
        );
        return;
      }

      // Server is healthy and app has started up - determine appropriate screen
      if (
        currentScreen === "startup" ||
        currentScreen === "connection-failed"
      ) {
        if (user) {
          console.log(
            `[Index] App ready, user authenticated (${user.github_username}), navigating to home`
          );
          setCurrentScreen("home");
        } else {
          console.log(
            "[Index] App ready, no user authenticated, navigating to login"
          );
          setCurrentScreen("login");
        }
      }
    };

    determineScreen();
  }, [isServerHealthy, hasStartedUp, user, currentScreen]);

  // Check for existing authentication on startup
  useEffect(() => {
    const checkAuthentication = async () => {
      console.log("[Index] Checking authentication on startup");
      console.log(
        `[Index] Server healthy: ${isServerHealthy}, Has started up: ${hasStartedUp}`
      );

      if (isServerHealthy && hasStartedUp) {
        console.log(
          "[Index] Server is healthy and app has started up, checking for existing session"
        );
        const currentUser = await authService.getCurrentUser();

        if (currentUser) {
          console.log(
            `[Index] Found authenticated user: ${currentUser.github_username}`
          );
          console.log(
            "[Index] Setting user state and navigating to home screen"
          );
          setUser(currentUser);
          setCurrentScreen("home");
          console.log("[Index] Successfully authenticated user on startup");
        } else if (currentScreen === "startup") {
          console.log(
            "[Index] No authenticated user found, navigating to login screen"
          );
          setCurrentScreen("login");
        } else {
          console.log(
            `[Index] No authenticated user found, but current screen is ${currentScreen}, not changing`
          );
        }
      } else {
        console.log(
          "[Index] Skipping authentication check - server not healthy or app not started up"
        );
      }
    };

    checkAuthentication();
  }, [isServerHealthy, hasStartedUp]);

  // Handle deep link navigation and GitHub OAuth callback
  useEffect(() => {
    const handleDeepLinkAndAuth = async () => {
      console.log("[Index] Checking deep link navigation and auth callback");
      console.log(
        `[Index] Deep link URL: ${deepLinkUrl}, Server healthy: ${isServerHealthy}`
      );
      console.log(
        `[Index] User authenticated: ${!!user}, Username: ${
          user?.github_username
        }`
      );

      if (deepLinkUrl && isServerHealthy) {
        console.log(`[Index] Processing deep link: ${deepLinkUrl}`);
        const parsed = parseDeepLink(deepLinkUrl);

        if (parsed) {
          console.log(
            `[Index] Parsed deep link - Path: ${parsed.path}, Params:`,
            parsed.params
          );

          // FIRST PRIORITY: Check for GitHub OAuth callback parameters
          const authSuccess = parsed.params.auth_success;
          const sessionCode = parsed.params.session_code;
          const error = parsed.params.error;

          if (error === "oauth_failed") {
            console.log(
              "[Index] OAuth failed detected in deep link parameters"
            );
            console.log(
              "[Index] Setting auth error and navigating to login screen"
            );
            setAuthError("oauth_failed");
            setCurrentScreen("login");
          } else if (authSuccess === "true" && sessionCode) {
            console.log(
              "[Index] Successful OAuth callback detected in deep link"
            );
            console.log(
              `[Index] Processing session code: ${sessionCode.substring(
                0,
                8
              )}...`
            );

            try {
              console.log(
                "[Index] Creating session with received session code"
              );
              const sessionData = await authService.createSession(sessionCode);

              console.log(
                `[Index] Successfully created session for user: ${sessionData.user.github_username}`
              );
              setUser(sessionData.user);
              setAuthError(null);

              // Add smooth transition to home screen
              console.log("[Index] Starting smooth transition to home screen");
              setIsTransitioning(true);
              setTimeout(() => {
                console.log("[Index] Completing transition to home screen");
                setCurrentScreen("home");
                setIsTransitioning(false);
                console.log(
                  "[Index] Successfully navigated to home screen after OAuth"
                );
              }, 300);
            } catch (error) {
              console.error("[Index] Failed to create session:", error);
              console.log(
                "[Index] Setting session_failed error and navigating to login"
              );
              setAuthError("session_failed");
              setCurrentScreen("login");
            }
          } else {
            // SECOND PRIORITY: Handle regular deep link navigation
            console.log(
              "[Index] No OAuth callback detected, processing as regular navigation"
            );

            // Only allow navigation to login if not authenticated
            // Authenticated users can't be sent back to login via deep link
            switch (parsed.path) {
              case "/login":
                if (!user) {
                  console.log(
                    "[Index] Deep link to login - user not authenticated, navigating to login"
                  );
                  setCurrentScreen("login");
                } else {
                  console.log(
                    "[Index] Deep link to login - user authenticated, ignoring navigation"
                  );
                }
                break;
              case "/home":
                if (user) {
                  console.log(
                    "[Index] Deep link to home - user authenticated, navigating to home"
                  );
                  setCurrentScreen("home");
                } else {
                  console.log(
                    "[Index] Deep link to home - user not authenticated, redirecting to login"
                  );
                  setCurrentScreen("login");
                }
                break;
              case "/task":
                if (user) {
                  const taskId = parsed.params.id;
                  if (taskId) {
                    console.log(
                      `[Index] Deep link to task - user authenticated, navigating to task: ${taskId}`
                    );
                    setSelectedTaskId(taskId);
                    setCurrentScreen("task");
                  } else {
                    console.log(
                      "[Index] Deep link to task - no task ID, navigating to home"
                    );
                    setCurrentScreen("home");
                  }
                } else {
                  console.log(
                    "[Index] Deep link to task - user not authenticated, redirecting to login"
                  );
                  setCurrentScreen("login");
                }
                break;
              default:
                console.log(`[Index] Unknown deep link path: ${parsed.path}`);
                // Unknown path, redirect based on auth state
                const targetScreen = user ? "home" : "login";
                console.log(
                  `[Index] Redirecting to ${targetScreen} based on auth state`
                );
                setCurrentScreen(targetScreen);
                break;
            }
          }
        } else {
          console.log("[Index] Failed to parse deep link URL");
        }

        console.log("[Index] Clearing deep link after processing");
        clearDeepLink();
      } else if (deepLinkUrl) {
        console.log(
          "[Index] Deep link present but server not healthy, skipping navigation"
        );
      }
    };

    handleDeepLinkAndAuth();
  }, [deepLinkUrl, parseDeepLink, clearDeepLink, user, isServerHealthy]);

  // Get current task name for navigation
  const getCurrentTaskName = () => {
    if (!selectedTaskId) return undefined;
    
    // Find the task in the tasks array
    const task = tasks.find(t => t.id === selectedTaskId);
    return task ? task.name : undefined;
  };

  if (currentScreen === "startup") {
    const message = hasStartedUp
      ? "CONNECTION WITH SERVER LOST, REESTABLISHING..."
      : "STARTING UP...";
    return <StartupScreen message={message} />;
  }

  if (currentScreen === "connection-failed") {
    return <ConnectionFailedScreen onRetry={handleRetryConnection} />;
  }

  if (currentScreen === "login") {
    return (
      <div
        className={`transition-opacity duration-300 ${
          isTransitioning ? "opacity-0" : "opacity-100"
        }`}
      >
        <LoginScreen onLogin={handleLogin} authError={authError} />
      </div>
    );
  }

  return (
    <div
      className={`flex h-screen bg-background transition-opacity duration-300 ${
        isTransitioning ? "opacity-0" : "opacity-100"
      }`}
    >
      <Sidebar
        tasks={tasks}
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

        {currentScreen === "home" && (
          <HomeScreen
            onTaskStart={handleTaskStart}
            onCommandK={handleCommandK}
          />
        )}

        {currentScreen === "task" && selectedTaskId && (
          <TaskScreen 
            taskId={selectedTaskId} 
            task={tasks.find(t => t.id === selectedTaskId)}
            onDeleteTask={handleDeleteTask}
            onNavigateHome={handleHomeSelect}
          />
        )}
      </div>

      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onTaskSelect={handleTaskSelect}
        onHomeSelect={handleHomeSelect}
        tasks={tasks}
      />
    </div>
  );
};

export default Index;
