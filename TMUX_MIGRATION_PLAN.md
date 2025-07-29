# Tmux Integration Migration Plan

## Overview

This document outlines the plan for integrating the standalone tmux-based CLI agents (Claude Code and Gemini) into the existing SimulateDev backend. The goal is to enable the Tauri macOS app to execute these agents via the backend API with real-time output streaming.

## Table of Contents

1. [Architecture Diagrams](#architecture-diagrams)
2. [Current State Analysis](#current-state-analysis)
3. [Migration Strategy](#migration-strategy)
   - [Phase 1: Core Integration](#phase-1-core-integration-week-1)
   - [Phase 2: Output Streaming](#phase-2-output-streaming-integration-week-1-2)
   - [Phase 3: API and Database](#phase-3-api-and-database-updates-week-2)
   - [Phase 4: Testing](#phase-4-testing-and-validation-week-2-3)
4. [Implementation Details](#implementation-details)
5. [Configuration Management](#configuration-management)
6. [Security & Authentication](#security--authentication)
7. [Key Design Decisions](#key-design-decisions)
8. [Error Handling & Recovery](#error-handling--recovery)
9. [Monitoring & Observability](#monitoring--observability)
10. [Risk Mitigation](#risk-mitigation)
11. [Deployment Requirements](#deployment-requirements)
12. [Test Data & Examples](#test-data--examples)
13. [Rollback Strategy](#rollback-strategy)
14. [Migration Checklist](#migration-checklist)
15. [Success Criteria](#success-criteria)
16. [Timeline](#timeline)
17. [Implementation Tips](#implementation-tips--common-pitfalls)
18. [Next Steps](#next-steps)

## Architecture Diagrams

### Component Architecture
```
┌─────────────────────┐     ┌─────────────────────┐
│   Tauri Frontend    │     │    REST API         │
│  - Task Creation    │────▶│  - /api/tasks/*     │
│  - Progress Display │     │  - Authentication   │
│  - WebSocket Client │     └─────────┬───────────┘
└─────────────────────┘               │
           ▲                          ▼
           │              ┌─────────────────────┐
           │              │   Task Service      │
           │              │  - Task Management  │
           │              │  - Agent Routing    │
           │              └─────────┬───────────┘
           │                        │
     WebSocket Updates              ▼
           │              ┌─────────────────────┐
           │              │   Tmux Service      │
           │              │  - Session Mgmt     │
           │              │  - Command Queue    │
           │              │  - Output Capture   │
           │              └─────────┬───────────┘
           │                        │
           │                        ▼
           │              ┌─────────────────────────┐
           │              │    CLI Agents           │
           │              │  ┌─────────┬─────────┐ │
           │              │  │ Claude  │ Gemini  │ │
           │              │  │  CLI    │  CLI    │ │
           │              │  └─────────┴─────────┘ │
           │              └─────────────────────────┘
           │                        │
           │                        ▼
           │              ┌─────────────────────┐
┌──────────┴──────────┐   │   Output Stream     │
│  WebSocket Manager  │◀──│     Adapter         │
│  - Real-time Updates│   │  - Format Output    │
│  - Connection Mgmt  │   │  - Buffer Updates   │
└─────────────────────┘   └─────────┬───────────┘
                                    │
                                    ▼
                          ┌─────────────────────┐
                          │   SQLite Database   │
                          │  - Task History     │
                          │  - Output Logs      │
                          └─────────────────────┘
```

### Execution Flow Sequence
```
1. Tauri App ──────▶ API: Create Task
                      │
2.                    ├──▶ Task Service: Initialize
                      │
3.                    ├──▶ Tmux Service: Create Session
                      │
4.                    ├──▶ CLI Agent: Start in Tmux Pane
                      │
5.                    └──▶ WebSocket: Connect for Updates
                           │
6. CLI Agent ─────────────┼──▶ Generate Output
                           │
7. Tmux Service ──────────┼──▶ Capture Output
                           │
8. Output Adapter ────────┼──▶ Format & Stream
                           │
9. WebSocket Manager ─────┼──▶ Send to Frontend
                           │
10. Tauri App ◀───────────┘ Display Progress
```

## Current State Analysis

### Working Tmux Implementation
- **Core Files:**
  - `tmux_operations_manager.py` - Main tmux session management with per-pane command queueing
  - `tmux_gemini_standalone.py` - FastAPI wrapper with WebSocket streaming
  - Test files validating the implementation

- **Key Features:**
  - Per-pane command isolation preventing cross-session interference
  - YOLO mode support for automated execution
  - Real-time output streaming via WebSocket
  - Session state management (SPAWNING → RUNNING → DONE)
  - Adaptive monitoring for performance optimization

### Existing Backend Structure
- **Agent System:**
  - Base agent classes for different IDE types (desktop, web, CLI)
  - Agent factory pattern for instantiation
  - Task service orchestrating execution
  
- **Communication Layer:**
  - WebSocket manager for real-time updates
  - SQLite database for execution history
  - REST API endpoints for task management

### Tauri Frontend
- Communicates via REST API for task execution
- WebSocket client for real-time progress updates
- Expects structured task status and output

## Migration Strategy

> **⚠️ IMPORTANT: Incremental Migration Approach**
> 
> Before implementing any WebSocket streaming, API integration, or complex features, **first focus on getting the core tmux functionality working within the backend environment**. This means:
> 
> 1. **Start Simple**: Extract and adapt `tmux_operations_manager.py` to work as a backend service
> 2. **Test Isolation**: Ensure tmux sessions can be created, managed, and cleaned up properly
> 3. **Verify Core Logic**: Confirm the per-pane command queueing system works in the new environment
> 4. **Basic CLI Agent Integration**: Get one CLI agent (e.g., Gemini) working through the tmux service
> 
> Only after confirming the tmux core works reliably in its new "home" should we proceed with WebSocket streaming, API endpoints, and full integration. This incremental approach reduces risk and makes debugging much easier.

### Phase 1: Core Integration (Week 1)

#### 1.1 Create Tmux Service Module
```
api/app/services/tmux_service.py
```
- Extract core functionality from `tmux_operations_manager.py`
- Remove duplicate enums/models (use existing backend structures)
- Adapt to use existing logging and configuration
- Integrate with backend's threading model

#### 1.2 Update Agent Base Classes
```
agents/base.py
```
- Add new agent type: `CLI_AGENT` alongside existing types
- Create `CLIAgent` base class extending `CodingAgent`
- Define interface for CLI-specific operations

#### 1.3 Implement CLI Agent Classes
```
agents/claude_cli_agent.py  (rename existing to claude_code_agent.py)
agents/gemini_cli_agent.py
```
- Extend new `CLIAgent` base class
- Implement agent-specific configurations
- Handle YOLO mode settings
- Map to existing agent response structures

### Phase 2: Output Streaming Integration (Week 1-2)

#### 2.1 Create Output Stream Adapter
```
api/app/services/output_stream_adapter.py
```
- Bridge between tmux output buffers and WebSocket manager
- Convert tmux output format to frontend-expected format
- Handle incremental updates efficiently
- Integrate with SQLite for output persistence

#### 2.2 Update Task Service
- Add support for CLI agent execution path
- Route CLI agents through tmux service
- Maintain compatibility with existing desktop/web agents
- Handle agent-specific execution parameters

#### 2.3 Enhance WebSocket Communication
- Adapt existing WebSocket manager for CLI agent output
- Ensure message format compatibility with Tauri frontend
- Add CLI-specific progress indicators

### Phase 3: API and Database Updates (Week 2)

#### 3.1 Database Schema Updates
```sql
-- Add to execution_history table
ALTER TABLE execution_history ADD COLUMN output_buffer TEXT;
ALTER TABLE execution_history ADD COLUMN agent_session_id VARCHAR(100);

-- Add CLI agent configuration table
CREATE TABLE cli_agent_configs (
    id VARCHAR(36) PRIMARY KEY,
    agent_type VARCHAR(50),
    yolo_mode BOOLEAN DEFAULT FALSE,
    pre_commands JSON,
    ready_indicators JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3.2 API Endpoint Modifications
- Extend task execution endpoint to accept CLI agent parameters
- Add YOLO mode configuration option
- Ensure backward compatibility for existing agent types

### Phase 4: Testing and Validation (Week 2-3)

#### 4.1 Unit Tests
- Test tmux service isolation
- Test CLI agent initialization
- Test output streaming adapter
- Test database operations

#### 4.2 Integration Tests
- End-to-end task execution via API
- WebSocket streaming validation
- Concurrent session handling
- Error recovery scenarios

#### 4.3 Frontend Integration Testing
- Verify Tauri app can execute CLI agents
- Validate real-time output display
- Test progress indicators
- Ensure UI responsiveness

## Implementation Details

### Key Changes Required

#### 1. Agent Factory Updates
```python
# agents/factory.py
from .claude_cli_agent import ClaudeCliAgent
from .gemini_cli_agent import GeminiCliAgent

class AgentFactory:
    @staticmethod
    def create_agent(agent_type: CodingAgentIdeType, computer_use_client) -> CodingAgent:
        # ... existing code ...
        elif agent_type == CodingAgentIdeType.CLAUDE_CLI:
            return ClaudeCliAgent(computer_use_client)
        elif agent_type == CodingAgentIdeType.GEMINI_CLI:
            return GeminiCliAgent(computer_use_client)
```

#### 2. Task Service Integration
```python
# api/app/services/task_service.py
async def _execute_task_internal(self, task_id: str, github_token: str):
    # ... existing code ...
    
    # Check if CLI agent
    if agent_config['coding_ide'] in ['claude_cli', 'gemini_cli']:
        # Route through tmux service
        result = await self._execute_cli_agent(task_id, task_request, github_token)
    else:
        # Existing orchestrator path
        result = await self._execute_with_orchestrator(task_id, task_request, github_token)
```

#### 3. WebSocket Message Format
```typescript
// Ensure compatibility with existing frontend
interface TaskProgressUpdate {
  type: "progress" | "output" | "error" | "completion";
  task_id: string;
  progress?: number;
  current_phase?: string;
  output?: string;  // For CLI agent output chunks
  timestamp: string;
}
```

### Configuration Management

#### Environment Variables
```bash
# .env additions
TMUX_MAX_SESSIONS=50
TMUX_MONITOR_INTERVAL=5.0
TMUX_SESSION_TIMEOUT=1800
GEMINI_API_KEY=xxx
CLAUDE_API_KEY=xxx
```

#### Agent Configurations
Each CLI agent implements its own `get_config()` method to provide agent-specific configuration using a structured `CLIAgentConfig` class:

```python
# agents/base.py
from dataclasses import dataclass
from typing import List

@dataclass
class CLIAgentConfig:
    command: List[str]
    supports_yolo: bool
    pre_commands: List[str]
    ready_indicators: List[str]

# agents/gemini_cli_agent.py
class GeminiCliAgent(CLIAgent):
    @classmethod
    def get_config(cls) -> CLIAgentConfig:
        return CLIAgentConfig(
            command=["gemini", "2>&1"],
            supports_yolo=True,
            pre_commands=["export GEMINI_API_KEY=${GEMINI_API_KEY}"],
            ready_indicators=["Type your message"]
        )

# agents/claude_cli_agent.py
class ClaudeCliAgent(CLIAgent):
    @classmethod
    def get_config(cls) -> CLIAgentConfig:
        return CLIAgentConfig(
            command=["claude", "--permission-mode", "acceptEdits"],
            supports_yolo=True,
            pre_commands=[],
            ready_indicators=["esc to interrupt"]
        )
```

This approach provides type safety, better IDE support, and ensures all required configuration fields are present while allowing each agent to define its own specific configuration.

## Key Design Decisions

### 1. Minimal Backend Disruption
- Keep existing agent architecture intact
- Add CLI agents as a new agent type alongside desktop/web agents
- Route CLI agents through tmux service while others use existing orchestrator

### 2. Reuse Existing Infrastructure
- Use existing WebSocket manager for streaming
- Leverage existing SQLite schema with minimal additions
- Maintain current API contract with Tauri frontend

### 3. Preserve Tmux Core Logic
- Extract core functionality from `tmux_operations_manager.py`
- Keep per-pane command queueing system intact
- Maintain session state machine (SPAWNING → RUNNING → DONE)

### 4. Clean Separation of Concerns
- Tmux Service: Session and pane management
- CLI Agents: Agent-specific configurations and behaviors
- Output Adapter: Format conversion and streaming
- Task Service: High-level orchestration

### 5. Backward Compatibility
- No breaking changes to existing API
- Frontend continues to work without modifications unless modifications lead to a cleaner and simpler code
- Existing agents unaffected by CLI agent addition

## Error Handling & Recovery

### Common Error Scenarios

#### 1. Tmux Session Failures
```python
class TmuxErrorHandler:
    @staticmethod
    async def handle_session_error(session_id: str, error: Exception):
        """Handle tmux session errors with appropriate recovery"""
        if isinstance(error, TmuxSessionNotFound):
            # Session died unexpectedly
            await cleanup_dead_session(session_id)
            await notify_user_session_failed(session_id)
        elif isinstance(error, TmuxCommandTimeout):
            # Command queue blocked
            await force_kill_pane(session_id)
            await restart_session_if_needed(session_id)
```

#### 2. Agent Startup Failures
- **Scenario**: CLI agent fails to start
- **Detection**: No ready indicators within timeout
- **Recovery**: Notify user

#### 3. Output Buffer Overflow
- **Scenario**: Agent produces excessive output
- **Detection**: Buffer size exceeds threshold
- **Recovery**: Implement circular buffer with size limits

#### 4. WebSocket Connection Loss
- **Scenario**: Frontend loses connection during execution
- **Detection**: WebSocket disconnect event
- **Recovery**: Buffer output for reconnection within time window

### Recovery Strategies
1. **Automatic Retry**: For transient failures (network, resource contention)
2. **Graceful Degradation**: Fallback to non-YOLO mode if YOLO fails
3. **Session Recovery**: Ability to reconnect to existing sessions
4. **Clean Shutdown**: Ensure all resources cleaned up on failure

## Monitoring & Observability

### Logging Strategy
```python
# Structured logging for tmux operations
logger.info("tmux_session_created", extra={
    "session_id": session_id,
    "agent_type": agent_type,
    "user_id": user_id,
    "yolo_mode": yolo_mode,
    "duration_ms": elapsed_time
})
```

## Deployment Requirements

### CLI Agent Installation
```bash
# Install script for CLI agents
#!/bin/bash
# install_cli_agents.sh

# Install Claude CLI
curl -fsSL https://claude.ai/cli/install.sh | sh

# Install Gemini CLI
pip install google-generativeai-cli

# Verify installations
claude --version || exit 1
gemini --version || exit 1
```


## Test Data & Examples

### Sample Test Repositories
```json
{
  "small_repo": "https://github.com/saharmor/cursor-chat-view",
  "medium_repo": "https://github.com/facebook/react",
  "large_repo": "https://github.com/microsoft/vscode"
}
```

### Test Prompts by Complexity
```python
# Simple test prompts
SIMPLE_PROMPTS = [
    "Print the current time in Berlin",
    "Fix the typo in the main function",
    "Echo 'hello world'"
]

# Medium complexity prompts
MEDIUM_PROMPTS = [
    "Add a README.md file with project description",
    "Write a basic HTTP server that returns 'Hello World'",
    "Create a JSON configuration file with database settings"
]

# Complex prompts requiring YOLO mode
COMPLEX_PROMPTS = [
    "Refactor the authentication system to use JWT tokens",
    "Add unit tests for the user service",
    "Implement pagination for the API endpoints"
]
```

### Integration Test Cases
```python
# tests/integration/test_cli_agents.py
class TestCLIAgentIntegration:
    async def test_simple_task_execution(self):
        """Test basic CLI agent execution"""
        task_id = await create_task(
            agent_type="gemini_cli",
            prompt="Create a hello world Python script",
            yolo_mode=False
        )
        result = await wait_for_completion(task_id, timeout=300)
        assert result.success
        assert "hello_world.py" in result.files_created
    
    async def test_concurrent_sessions(self):
        """Test multiple concurrent CLI sessions"""
        tasks = []
        for i in range(5):
            task_id = await create_task(
                agent_type="claude_cli" if i % 2 else "gemini_cli",
                prompt=f"Create test_file_{i}.txt",
                yolo_mode=True
            )
            tasks.append(task_id)
        
        results = await asyncio.gather(*[
            wait_for_completion(tid) for tid in tasks
        ])
        assert all(r.success for r in results)
    
    async def test_session_isolation(self):
        """Verify sessions don't interfere with each other"""
        # Implementation similar to test_tmux_cross_pane_input.py
        pass
```

### Expected File Structure After Migration
```
simulatedev/
├── agents/
│   ├── base.py (updated with CLIAgent base class)
│   ├── claude_code_agent.py (existing, renamed)
│   ├── claude_cli_agent.py (new)
│   ├── gemini_cli_agent.py (new)
│   └── factory.py (updated)
├── api/
│   └── app/
│       ├── services/
│       │   ├── tmux_service.py (new)
│       │   ├── output_stream_adapter.py (new)
│       │   └── task_service.py (updated)
│       └── api/
│           └── health.py (updated)
├── tests/
│   ├── unit/
│   │   ├── test_tmux_service.py (new)
│   │   └── test_cli_agents.py (new)
│   └── integration/
│       ├── test_cli_agent_integration.py (new)
│       └── test_websocket_streaming.py (new)
└── config/
    └── cli_agents.py (new)
```

## Migration Checklist

### Pre-Migration
- [ ] Back up existing database
- [ ] Document current API endpoints

### During Migration
- [ ] Implement Phase 1 components
- [ ] Write unit tests for new modules
- [ ] Implement Phase 2 streaming
- [ ] Update API documentation (OpenAPI/Swagger)
- [ ] Implement Phase 3 database changes
- [ ] Create integration tests
- [ ] Test with Tauri frontend

### Post-Migration
- [ ] Load testing with 20+ concurrent sessions

## Success Criteria

1. **Functional Requirements**
   - CLI agents executable via Tauri app
   - Real-time output streaming working
   - Session isolation maintained
   - YOLO mode functional

2. **Quality Requirements**
   - 95%+ test coverage for new code
   - No regression in existing functionality
   - Clean error handling and recovery
   - Zero data loss during migration

## Implementation Tips & Common Pitfalls

### Do's ✅
1. **Start Small**: Test with a single CLI agent first (Gemini)
2. **Use Existing Patterns**: Follow existing agent implementation patterns
3. **Test Early**: Set up tmux in development environment immediately
4. **Monitor Resources**: Watch for file descriptor and memory leaks
5. **Document Everything**: Especially non-obvious tmux behaviors

### Don'ts ❌
1. **Don't Modify Core tmux Logic**: Keep the per-pane queueing system intact
2. **Don't Store Secrets in Logs**: Ensure API keys are never logged
3. **Don't Skip Cleanup**: Always clean up tmux sessions on errors
5. **Don't Break Existing Agents**: Test desktop/web agents still work

### Common Pitfalls to Avoid

#### 1. Tmux Environment Issues
```python
# WRONG: Tmux may not find the socket
subprocess.run(["tmux", "new-session"])

# CORRECT: Set proper environment
env = os.environ.copy()
env["TMUX_TMPDIR"] = "/tmp/tmux-sessions"
subprocess.run(["tmux", "new-session"], env=env)
```

#### 2. Race Conditions
```python
# WRONG: Checking state immediately after command
send_command_to_pane(pane_id, prompt)
if is_agent_ready(pane_id):  # Too fast!

# CORRECT: Allow time for state changes
send_command_to_pane(pane_id, prompt)
await asyncio.sleep(0.5)  # Give tmux time to process
if is_agent_ready(pane_id):
```

#### 3. Output Buffer Management
```python
# WRONG: Unbounded buffer growth
output_buffer += new_output

# CORRECT: Implement circular buffer
if len(output_buffer) > MAX_BUFFER_SIZE:
    output_buffer = output_buffer[-MAX_BUFFER_SIZE:]
output_buffer += new_output
```

#### 4. WebSocket Message Flooding
```python
# WRONG: Send every output change
for line in new_output.split('\n'):
    await websocket.send(line)

# CORRECT: Batch updates
if time.time() - last_update > 0.1:  # 100ms throttle
    await websocket.send(batched_output)
    last_update = time.time()
```

### Debugging Tips
1. **Enable Tmux Logging**: `tmux -L debug -f /dev/null`
2. **Capture Pane History**: `tmux capture-pane -p -S -1000`
5. **Use Tmux Status Line**: Display session info for debugging

## Next Steps

1. Review and approve this migration plan
2. Begin Phase 1 implementation and track progress in a new markdown file
3. Continue with other steps after getting confirmation from your manager, which is me!

---

**Document Version**: 1.0  
**Last Updated**: Current Date  
**Author**: Development Team 