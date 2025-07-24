import { Github, Rocket } from "lucide-react";
import { Button } from "./ui/button";
import { authService } from "../services/authService";

interface LoginScreenProps {
  onLogin: () => void;
  authError?: string | null;
}

export function LoginScreen({ authError }: LoginScreenProps) {
  console.log('[LoginScreen] Rendering login screen');
  console.log(`[LoginScreen] Auth error present: ${!!authError}, Error type: ${authError}`);
  
  const handleGitHubLogin = async () => {
    console.log('[LoginScreen] GitHub login button clicked');
    try {
      console.log('[LoginScreen] Initiating GitHub OAuth flow');
      await authService.initiateGitHubOAuth();
      console.log('[LoginScreen] GitHub OAuth initiation completed successfully');
    } catch (error) {
      console.error("[LoginScreen] GitHub login failed:", error);
      console.log('[LoginScreen] User will remain on login screen due to OAuth error');
    }
  };
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center max-w-md">
        {/* Logo */}
        <div className="space-y-2 mb-8">
          <h1 className="text-4xl font-mono font-semibold text-foreground tracking-tight flex items-center justify-center gap-3">
            <Rocket className="w-10 h-10" />
            SimulateDev
          </h1>
          <p className="text-gray-600 text-lg">
            Build with agents, not editors
          </p>
        </div>

        {/* Subtitle */}
        <div className="mb-8">
          <p className="text-gray-500 text-sm">
            Sign into GitHub to give your agents a terminal, a mission, and
            autonomy for your codebase.
          </p>
        </div>

        {/* Sign in button */}
        <Button
          onClick={handleGitHubLogin}
          className="bg-foreground text-background hover:bg-gray-800 px-16 py-5 rounded-lg font-medium flex items-center gap-2 mx-auto transition-colors"
        >
          <Github className="w-4 h-4" />
          Sign in with GitHub
        </Button>

        {/* Error message */}
        {authError === 'oauth_failed' && (() => {
          console.log('[LoginScreen] Displaying AUTHENTICATION FAILED error message');
          return (
            <div className="mt-4">
              <p className="text-red-500 text-4xl font-mono font-semibold tracking-tight">
                AUTHENTICATION FAILED
              </p>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
