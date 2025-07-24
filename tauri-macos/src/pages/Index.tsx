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

type Screen = "startup" | "connection-failed" | "login" | "home" | "task";

const Index = () => {
  const [currentScreen, setCurrentScreen] = useState<Screen>("startup");
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
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

  const handleTaskStart = (_issueId: string) => {
    // In a real app, this would create a new task
    // For now, just select an existing task for demo
    setSelectedTaskId("1");
    setCurrentScreen("task");
  };

  const handleHomeSelect = () => {
    setCurrentScreen("home");
    setSelectedTaskId(null);
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
    const mockTaskData = {
      "1": "Implement Playwright best practices for robust web automation",
      "2": "Improve README formatting",
      "3": "Add DiffUtil to RecyclerView for better performance",
      "4": "Integrate MonsterAPI for Advanced Audio Transcription",
    };
    return mockTaskData[selectedTaskId as keyof typeof mockTaskData];
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

        {currentScreen === "home" && (
          <HomeScreen
            onTaskStart={handleTaskStart}
            onCommandK={handleCommandK}
          />
        )}

        {currentScreen === "task" && selectedTaskId && (
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
