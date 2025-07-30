import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface AgentSelection {
  agent: Agent;
  isSequential: boolean;
  yoloMode?: boolean;
  sequentialAgents?: {
    coder1: Agent;
    tester: Agent;
    coder2: Agent;
  };
}

interface AgentSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAgentSelect: (selection: AgentSelection) => void;
}

// Mapping to identify which agents are CLI agents
const CLI_AGENTS = new Set(['claude_cli', 'gemini_cli']);

const availableAgents: Agent[] = [
      {
      id: "claude_cli",
    name: "Claude Code",
    description: "Advanced code generation and analysis",
    icon: "CC"
  },
  {
    id: "cursor",
    name: "Cursor",
    description: "AI-powered code editor with advanced completion",
    icon: "CR"
  },
  {
    id: "gemini_cli",
    name: "Gemini CLI",
    description: "Fast and efficient command-line focused AI",
    icon: "GC"
  }
];

export function AgentSelectionModal({ isOpen, onClose, onAgentSelect }: AgentSelectionModalProps) {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [isSequential, setIsSequential] = useState(false);
  const [yoloMode, setYoloMode] = useState(false);
  const [sequentialAgents, setSequentialAgents] = useState({
    coder1: null as Agent | null,
    tester: null as Agent | null,
    coder2: null as Agent | null
  });
  const [currentStage, setCurrentStage] = useState<'main' | 'sequential'>('main');

  const handleAgentClick = (agent: Agent) => {
    if (currentStage === 'main') {
      setSelectedAgent(agent);
      // Reset YOLO mode when switching agents
      setYoloMode(false);
    }
  };

  // Check if the selected agent is a CLI agent
  const isCliAgent = selectedAgent ? CLI_AGENTS.has(selectedAgent.id) : false;

  const handleSequentialAgentClick = (stage: 'coder1' | 'tester' | 'coder2', agent: Agent) => {
    setSequentialAgents(prev => ({
      ...prev,
      [stage]: agent
    }));
  };

  const handleSequentialToggle = (checked: boolean) => {
    setIsSequential(checked);
    if (checked) {
      setCurrentStage('sequential');
      // Initialize with the selected agent for all stages
      if (selectedAgent) {
        setSequentialAgents({
          coder1: selectedAgent,
          tester: selectedAgent,
          coder2: selectedAgent
        });
      }
    } else {
      setCurrentStage('main');
    }
  };

  const handleProceed = () => {
    if (selectedAgent) {
      if (isSequential && sequentialAgents.coder1 && sequentialAgents.tester && sequentialAgents.coder2) {
        onAgentSelect({ 
          agent: selectedAgent, 
          isSequential, 
          yoloMode,
          sequentialAgents: {
            coder1: sequentialAgents.coder1,
            tester: sequentialAgents.tester,
            coder2: sequentialAgents.coder2
          }
        });
      } else {
        onAgentSelect({ agent: selectedAgent, isSequential, yoloMode }); // Include YOLO mode
      }
      onClose();
      // Reset state for next time
      setSelectedAgent(null);
      setIsSequential(false);
      setYoloMode(false); // Reset YOLO mode
      setSequentialAgents({ coder1: null, tester: null, coder2: null });
      setCurrentStage('main');
    }
  };

  const isSequentialComplete = sequentialAgents.coder1 && sequentialAgents.tester && sequentialAgents.coder2;

  const renderAgentGrid = (agents: Agent[], selectedAgent: Agent | null, onSelect: (agent: Agent) => void, compact: boolean = false) => (
    <div className={`w-full ${compact ? 'space-y-2' : 'space-y-4'} ${compact ? 'mb-4' : 'mb-6'}`}>
      {agents.map((agent) => (
        <button
          key={agent.id}
          onClick={() => onSelect(agent)}
          className={`w-full flex items-center gap-4 ${compact ? 'p-3' : 'p-4'} rounded-lg text-left border transition-colors ${
            selectedAgent?.id === agent.id 
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-950 dark:border-blue-400' 
              : 'border-border hover:bg-muted'
          }`}
        >
          <div className={`${compact ? 'w-10 h-10' : 'w-12 h-12'} bg-muted rounded-lg flex items-center justify-center ${compact ? 'text-sm' : 'text-lg'} font-bold text-muted-foreground`}>
            {agent.icon}
          </div>
          <div className="flex-1">
            <h3 className={`font-semibold text-foreground ${compact ? 'text-sm mb-0.5' : 'mb-1'}`}>{agent.name}</h3>
            <p className={`${compact ? 'text-xs' : 'text-sm'} text-muted-foreground`}>{agent.description}</p>
          </div>
        </button>
      ))}
    </div>
  );

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="sr-only">Choose Your Model</DialogTitle>
        </DialogHeader>
        
        <div className="flex flex-col items-center py-6 px-6">
          {currentStage === 'main' ? (
            <>
              {/* Main Agent Selection */}
              <h1 className="text-2xl font-mono font-normal text-foreground tracking-tight mb-8">
                CHOOSE THE CODING AGENT
              </h1>

              {renderAgentGrid(availableAgents, selectedAgent, handleAgentClick)}

              {/* Sequential Execution Option */}
              {selectedAgent && (
                <div className="w-full mb-6 space-y-3">
                  <label className="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted">
                    <input
                      type="checkbox"
                      checked={isSequential}
                      onChange={(e) => handleSequentialToggle(e.target.checked)}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <div className="text-sm font-medium text-foreground">
                        Sequential Agent Execution
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Run Coder → Tester → Coder sequence with custom agents per stage
                      </div>
                    </div>
                  </label>

                  {/* YOLO Mode Option - only show for CLI agents */}
                  {isCliAgent && (
                    <label className="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted">
                      <input
                        type="checkbox"
                        checked={yoloMode}
                        onChange={(e) => setYoloMode(e.target.checked)}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-foreground">
                          YOLO Mode
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Enable automated execution without confirmation prompts
                        </div>
                      </div>
                    </label>
                  )}
                </div>
              )}

              {/* Proceed Button */}
              {selectedAgent && !isSequential && (
                <Button 
                  onClick={handleProceed}
                  className="w-full"
                >
                  Start Task with {selectedAgent.name}
                </Button>
              )}
            </>
          ) : (
            <>
              {/* Sequential Agent Selection */}
              <h1 className="text-xl font-mono font-normal text-foreground tracking-tight mb-6">
                CHOOSE AGENTS FOR EACH STAGE
              </h1>

              {/* Grid Layout for Stages */}
              <div className="w-full grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                {/* Stage 1: First Coder */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-foreground mb-3 text-center">
                    Stage 1: Initial Coder
                  </h3>
                  {renderAgentGrid(availableAgents, sequentialAgents.coder1, (agent) => handleSequentialAgentClick('coder1', agent), true)}
                </div>

                {/* Stage 2: Tester */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-foreground mb-3 text-center">
                    Stage 2: Tester
                  </h3>
                  {renderAgentGrid(availableAgents, sequentialAgents.tester, (agent) => handleSequentialAgentClick('tester', agent), true)}
                </div>

                {/* Stage 3: Second Coder */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-foreground mb-3 text-center">
                    Stage 3: Final Coder
                  </h3>
                  {renderAgentGrid(availableAgents, sequentialAgents.coder2, (agent) => handleSequentialAgentClick('coder2', agent), true)}
                </div>
              </div>

              {/* Execution Flow Indicator */}
              <div className="w-full mb-6 flex items-center justify-center space-x-4 text-sm text-muted-foreground">
                <span className={`${sequentialAgents.coder1 ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                  {sequentialAgents.coder1 ? sequentialAgents.coder1.name : 'Select Coder'}
                </span>
                <span>→</span>
                <span className={`${sequentialAgents.tester ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                  {sequentialAgents.tester ? sequentialAgents.tester.name : 'Select Tester'}
                </span>
                <span>→</span>
                <span className={`${sequentialAgents.coder2 ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                  {sequentialAgents.coder2 ? sequentialAgents.coder2.name : 'Select Coder'}
                </span>
              </div>

              {/* Back and Proceed Buttons */}
              <div className="w-full flex gap-3">
                <Button 
                  variant="outline"
                  onClick={() => setCurrentStage('main')}
                  className="flex-1"
                >
                  Back
                </Button>
                {isSequentialComplete && (
                  <Button 
                    onClick={handleProceed}
                    className="flex-1"
                  >
                    Start Sequential Task
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}