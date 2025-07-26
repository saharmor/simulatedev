import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface AgentSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAgentSelect: (agent: Agent) => void;
}

const availableAgents: Agent[] = [
  {
    id: "claude_code",
    name: "Claude Code",
    description: "Advanced code generation and analysis",
    icon: "CC"
  },
  {
    id: "gemini_cli",
    name: "Gemini CLI",
    description: "Fast and efficient command-line focused AI",
    icon: "GC"
  }
];

export function AgentSelectionModal({ isOpen, onClose, onAgentSelect }: AgentSelectionModalProps) {
  const handleAgentClick = (agent: Agent) => {
    onAgentSelect(agent);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="sr-only">Choose Your Model</DialogTitle>
        </DialogHeader>
        
        <div className="flex flex-col items-center py-6">
          {/* Title */}
          <h1 className="text-2xl font-mono font-normal text-foreground tracking-tight mb-8">
            CHOOSE THE CODING AGENT
          </h1>

          {/* Agent Options */}
          <div className="w-full space-y-4">
            {availableAgents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => handleAgentClick(agent)}
                className="w-full flex items-center gap-4 p-4 rounded-lg hover:bg-gray-50 text-left border border-gray-200 transition-colors"
              >
                <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center text-lg font-bold text-gray-700">
                  {agent.icon}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 mb-1">{agent.name}</h3>
                  <p className="text-sm text-gray-500">{agent.description}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}