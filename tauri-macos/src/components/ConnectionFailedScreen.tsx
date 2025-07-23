import { Rocket, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";

interface ConnectionFailedScreenProps {
  onRetry: () => void;
}

export function ConnectionFailedScreen({ onRetry }: ConnectionFailedScreenProps) {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center max-w-md">
        {/* Logo */}
        <div className="space-y-2 mb-8">
          <h1 className="text-4xl font-mono font-semibold text-foreground tracking-tight flex items-center justify-center gap-3">
            <Rocket className="w-10 h-10" />
            SimulateDev
          </h1>
        </div>

        {/* Connection failed message */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-foreground mb-2">
            Connection Failed
          </h2>
          <p className="text-gray-600 text-sm mb-4">
            Unable to connect to the SimulateDev server.
          </p>
          <p className="text-gray-500 text-xs">
            Make sure the server is running at localhost:8000
          </p>
        </div>

        {/* Retry button */}
        <Button
          onClick={onRetry}
          className="bg-foreground text-background hover:bg-gray-800 px-8 py-3 rounded-lg font-medium flex items-center gap-2 mx-auto transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry Connection
        </Button>
      </div>
    </div>
  );
}