import { Rocket } from "lucide-react";

interface StartupScreenProps {
  message?: string;
}

export function StartupScreen({ message = "STARTING UP..." }: StartupScreenProps) {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center">
        {/* Logo */}
        <div className="space-y-2 mb-8">
          <h1 className="text-4xl font-mono font-semibold text-foreground tracking-tight flex items-center justify-center gap-3">
            <Rocket className="w-10 h-10" />
            SimulateDev
          </h1>
        </div>

        {/* Loading indicator */}
        <div className="mb-4">
          <div className="w-8 h-8 border-2 border-foreground border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>

        {/* Status message */}
        <p className="text-foreground text-lg font-mono">
          {message}
        </p>
      </div>
    </div>
  );
}