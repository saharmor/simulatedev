#!/usr/bin/env python3
"""
Multi-Agent CLI tmux Manager + Lean UI (v5.0)
============================================
Thread-safe version with support for multiple CLI agents (Gemini, Claude Code).

Key features:
- Support for multiple CLI agents with different behaviors
- Agent-specific configurations and completion detection
- Agent-specific pre-commands for custom setup
- Claude Code JSON streaming output parsing
- Gemini interactive mode with YOLO support
- Comprehensive locking for all shared state
- Atomic state transitions
- Safe WebSocket management
- Robust error recovery

Example usage with agent-specific pre-commands:
```python
manager = TmuxAgentManager()
# Add virtual environment activation for Gemini
manager.add_agent_pre_command("gemini", "source ~/gemini-env/bin/activate")
# Add different setup for Claude
manager.add_agent_pre_command("claude", "source ~/claude-env/bin/activate")
manager.add_agent_pre_command("claude", "export CLAUDE_API_KEY=xxx")
```

Run:
```bash
pip install fastapi uvicorn "python-multipart>=0.0.5" aiofiles
python tmux_agent_manager.py --attach --ui
```
"""

import asyncio
import subprocess
import time
import json
import hashlib
import sys
import os
import threading
import logging
import re
import shlex
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from contextlib import contextmanager
from pydantic import BaseModel
from enum import Enum

# ---------------------------- UI DEPS ----------------------------------------
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import aiofiles

# ---------------------------- Enums ------------------------------------------
class AgentType(Enum):
    """Supported CLI agent types"""
    GEMINI = "gemini"
    CLAUDE = "claude"
    
    def __str__(self):
        return self.value

class ReadyIndicatorMode(Enum):
    """Mode for checking ready indicators"""
    INCLUSIVE = "inclusive"  # Agent is ready when indicators ARE present
    EXCLUSIVE = "exclusive"  # Agent is ready when indicators are NOT present
    
    def __str__(self):
        return self.value

class SessionStatus(Enum):
    """Session status values"""
    SPAWNING = "SPAWNING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    STOPPED = "STOPPED"
    REQUIRES_USER_INPUT = "REQUIRES_USER_INPUT"
    PREMATURE_FINISH = "PREMATURE_FINISH"
    
    def __str__(self):
        return self.value

# ---------------------------- Agent Configuration ----------------------------
@dataclass
class AgentConfig:
    """Configuration for a CLI agent"""
    name: AgentType  # Agent type enum
    command: List[str]  # Base command to run
    ready_indicators: List[str]  # Text patterns that indicate agent is ready for input
    input_indicators: List[str]  # Text patterns that indicate agent is waiting for user response
    supports_interactive: bool  # Whether agent can run in interactive mode (multiple prompts)
    supports_yolo: bool  # Whether agent supports YOLO mode (auto-approve changes)
    completion_check_method: str  # "ready_prompt" or "process_exit"
    output_format: str  # "text" or "json"
    pre_commands: List[str] = field(default_factory=list)  # Commands to run before agent
    # New fields for smarter completion detection
    ready_indicator_mode: ReadyIndicatorMode = ReadyIndicatorMode.INCLUSIVE  # Mode for checking ready indicators
    busy_indicators: List[str] = field(default_factory=list)  # Text patterns that indicate agent is still working
    completion_timeout: float = 10.0  # Seconds to wait after prompt before checking completion

# Define agent configurations
AGENT_CONFIGS = {
    AgentType.GEMINI: AgentConfig(
        name=AgentType.GEMINI,
        command=["gemini", "2>&1"],
        ready_indicators=["Type your message or @path/to/file"],
        ready_indicator_mode=ReadyIndicatorMode.INCLUSIVE,  # Gemini shows text when ready
        input_indicators=[
            "Apply this change?",
            "● 1. Yes, allow once", 
            "● 2. Yes, allow always",
            "(Use Enter to select)",
            "Continue? (y/n)",
            "Confirm?"
        ],
        supports_interactive=True,  # Can accept multiple prompts in one session
        supports_yolo=True,  # Supports Ctrl+Y to auto-approve changes
        completion_check_method="ready_prompt",
        output_format="text",
        pre_commands=[
            "export GEMINI_API_KEY=\"AIzaSyDp3bjpxQDNwnVHg2xR1k6sUtcoVTIyq1E\"",
        ],
        busy_indicators=[],  # Gemini doesn't have specific busy indicators
        completion_timeout=10.0  # Default timeout for Gemini
    ),
    AgentType.CLAUDE: AgentConfig(
        name=AgentType.CLAUDE,
        command=["claude", "--permission-mode", "acceptEdits", "2>&1"],  # Interactive mode with permission handling
        ready_indicators=["esc to interrupt"],  # Text that must be ABSENT when Claude is done
        ready_indicator_mode=ReadyIndicatorMode.EXCLUSIVE,  # Claude is ready when "esc to interrupt" is NOT present
        input_indicators=["Enter to confirm"],  # Claude may have permission prompts but acceptEdits handles them
        supports_interactive=True,  # Can accept multiple prompts in one session
        supports_yolo=True,  # Can use --dangerously-skip-permissions or acceptEdits mode
        completion_check_method="ready_prompt",  # Look for ready indicators like Gemini
        output_format="text",
        pre_commands=[],  # Can be customized per deployment
        busy_indicators=["esc to interrupt"],  # Additional patterns that indicate Claude is busy
        completion_timeout=5.0  # Claude typically responds faster than Gemini
    ),
    # Example: Claude in non-interactive mode (single prompt execution)
    # AgentType.CLAUDE_PRINT: AgentConfig(
    #     name=AgentType.CLAUDE_PRINT,
    #     command=["claude", "--print"],  # --print flag for single prompt execution
    #     ready_indicators=[],  # No ready indicators in print mode
    #     input_indicators=[],
    #     supports_interactive=False,  # One prompt per execution
    #     supports_yolo=True,  # Uses --dangerously-skip-permissions flag
    #     completion_check_method="process_exit",
    #     output_format="text",
    #     pre_commands=[]
    # )
}

# ---------------------------- Data Models ------------------------------------
@dataclass
class SessionInfo:
    session_id: str
    prompt: str
    repo_url: str
    status: SessionStatus
    start_time: float
    end_time: Optional[float] = None
    yolo_mode: bool = False
    agent_type: AgentType = AgentType.GEMINI  # Agent type enum
    
    def copy(self):
        """Create a safe copy for external use"""
        return SessionInfo(
            session_id=self.session_id,
            prompt=self.prompt,
            repo_url=self.repo_url,
            status=self.status,
            start_time=self.start_time,
            end_time=self.end_time,
            yolo_mode=self.yolo_mode,
            agent_type=self.agent_type
        )
    
    def to_dict(self):
        """Convert to dictionary with enum values as strings"""
        return {
            "session_id": self.session_id,
            "prompt": self.prompt,
            "repo_url": self.repo_url,
            "status": self.status.value,  # Convert enum to string
            "start_time": self.start_time,
            "end_time": self.end_time,
            "yolo_mode": self.yolo_mode,
            "agent_type": self.agent_type.value  # Convert enum to string
        }

@dataclass
class OutputBuffer:
    """Tracks output changes for efficient streaming"""
    content: str = ""
    version: int = 0
    
    def get_content(self) -> str:
        """Get current content safely"""
        return self.content
    
    def update_content(self, new_content: str) -> Optional[str]:
        """Update content and return changes if any"""
        if new_content != self.content:
            # Find common prefix
            common_len = 0
            for i, (a, b) in enumerate(zip(self.content, new_content)):
                if a != b:
                    break
                common_len = i + 1
            
            changes = new_content[common_len:]
            self.content = new_content
            self.version += 1
            return changes
        return None

# ---------------------------- Thread-Safe Manager ----------------------------
class TmuxAgentManager:
    """Thread-safe manager for multiple tmux sessions with support for different CLI agents."""

    def __init__(self, max_sessions: int = 50, default_repo: str | None = None, global_pre_commands: List[str] | None = None, default_agent: AgentType = AgentType.GEMINI):
        self.max_sessions = max_sessions
        self.default_repo = default_repo or "https://github.com/saharmor/gemini-multimodal-playground"
        self.global_pre_commands = global_pre_commands or []  # Applied to all agents
        self.default_agent = default_agent
        self.running = True
        self.main_session = "agent_manager"
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        self.status_file = Path("tmux_sessions_status.json")
        
        # Agent configurations (can be modified after initialization)
        self.agent_configs = AGENT_CONFIGS.copy()
        
        # Apply global pre-commands to all agents if provided
        if self.global_pre_commands:
            for agent_name in self.agent_configs:
                # Prepend global pre-commands to agent-specific ones
                self.agent_configs[agent_name].pre_commands = self.global_pre_commands + self.agent_configs[agent_name].pre_commands
        
        # Thread safety - single lock for all shared state
        self._state_lock = threading.RLock()
        
        # Protected state (access only with _state_lock)
        self._sessions: Dict[str, SessionInfo] = {}
        self._pane_mapping: Dict[str, str] = {}
        self._output_buffers: Dict[str, OutputBuffer] = {}
        self._session_prompts: Dict[str, str] = {}
        self._prompt_sent_time: Dict[str, float] = {}
        
        # WebSocket management with separate lock
        self._ws_lock = threading.RLock()
        self._active_websockets: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._websocket_positions: Dict[str, Dict[int, int]] = defaultdict(dict)
        
        # File operations lock
        self._file_lock = threading.Lock()
        
        # Setup logging
        self._setup_logging()

    def _get_agent_type(self, agent_name) -> AgentType:
        """Convert string or AgentType to AgentType enum"""
        if isinstance(agent_name, AgentType):
            return agent_name
        elif isinstance(agent_name, str):
            # Try to find matching enum value
            for agent_type in AgentType:
                if agent_type.value == agent_name:
                    return agent_type
            raise ValueError(f"Unknown agent: {agent_name}")
        else:
            raise ValueError(f"Invalid agent type: {type(agent_name)}")

    def update_agent_config(self, agent_name, **kwargs):
        """Update configuration for a specific agent"""
        agent_type = self._get_agent_type(agent_name)
        
        if agent_type not in self.agent_configs:
            raise ValueError(f"Unknown agent: {agent_type}")
        
        config = self.agent_configs[agent_type]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                raise ValueError(f"Invalid config key: {key}")
        
        self.logger.info(f"Updated {agent_type} config: {kwargs}")

    def add_agent_pre_command(self, agent_name, command: str):
        """Add a pre-command to a specific agent"""
        agent_type = self._get_agent_type(agent_name)
        
        if agent_type not in self.agent_configs:
            raise ValueError(f"Unknown agent: {agent_type}")
        
        self.agent_configs[agent_type].pre_commands.append(command)
        self.logger.info(f"Added pre-command to {agent_type}: {command}")

    def configure_agent_environment(self, agent_name, venv_path: str = None, api_key_env: str = None, custom_commands: List[str] = None):
        """Convenience method to configure common agent environment settings"""
        agent_type = self._get_agent_type(agent_name)
        
        if agent_type not in self.agent_configs:
            raise ValueError(f"Unknown agent: {agent_type}")
        
        if venv_path:
            self.add_agent_pre_command(agent_type, f"source {venv_path}/bin/activate")
        
        if api_key_env:
            self.add_agent_pre_command(agent_type, f"export {api_key_env}")
        
        if custom_commands:
            for cmd in custom_commands:
                self.add_agent_pre_command(agent_type, cmd)
        
        self.logger.info(f"Configured environment for {agent_type}")

    def _setup_logging(self):
        """Setup debug logging"""
        debug_log_file = self.logs_dir / "debug.log"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(debug_log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 TmuxAgentManager initialized (thread-safe version with multi-agent support)")
        
        # Test logging output
        print("=" * 60)
        print("🔍 LOGGING TEST - If you don't see this, logging is broken!")
        print("=" * 60)

    # ---------- Context Managers for Safe Access ----------
    @contextmanager
    def _session_context(self, sid: str):
        """Context manager for safe session access"""
        with self._state_lock:
            session = self._sessions.get(sid)
            if session:
                yield session
            else:
                yield None

    @contextmanager
    def _atomic_state_update(self):
        """Context manager for atomic state updates"""
        with self._state_lock:
            yield

    # ---------- Helper Methods ----------
    def _run(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run command safely"""
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=check)
        except Exception as e:
            self.logger.error(f"Command failed: {' '.join(cmd)} - {e}")
            raise

    def _generate_id(self, prompt: str, repo_url: str, agent_type: str) -> str:
        # Include current timestamp to ensure uniqueness even for identical prompts
        timestamp = str(time.time())
        return f"{agent_type}_{hashlib.md5(f'{prompt}:{repo_url}:{timestamp}'.encode()).hexdigest()[:8]}"

    def _rename_pane(self, full_target: str, new_name: str):
        """Set pane title safely"""
        try:
            pane_id = full_target.split(".")[-1]
            self._run(["tmux", "select-pane", "-t", pane_id, "-T", new_name])
        except Exception as e:
            self.logger.warning(f"Failed to rename pane: {e}")
    
    def _clean_terminal_output(self, text: str) -> str:
        """Clean terminal output by removing ANSI escape codes"""
        if not text:
            return ""
            
        # Comprehensive ANSI escape code removal
        ansi_escape = re.compile(r'''
            \x1B  # ESC
            (?:   # 7-bit C1 Fe
                [@-Z\\-_]
            |     # or [ for CSI
                \[
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        ''', re.VERBOSE)
        
        # Remove various terminal sequences
        text = ansi_escape.sub('', text)
        text = re.sub(r'\x1b\[[0-9;]*[mGKHJF]', '', text)
        text = re.sub(r'\x1b\[[\?0-9]*[hl]', '', text)
        text = re.sub(r'\x07|\r', '', text)
        
        # Keep only printable characters plus newline/tab
        text = ''.join(c for c in text if c.isprintable() or c in '\n\t' or ord(c) >= 0x2500)
        
        return text

    def _parse_claude_json_output(self, text: str) -> str:
        """Parse Claude's JSON streaming output and extract meaningful text"""
        if not text:
            return ""
        
        output_lines = []
        
        # Split by lines and process each JSON object
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            try:
                json_obj = json.loads(line)
                
                # Handle different message types
                if json_obj.get('type') == 'system':
                    if json_obj.get('subtype') == 'init':
                        output_lines.append(f"[Claude] Initializing session...")
                        model = json_obj.get('model', 'unknown')
                        output_lines.append(f"[Claude] Model: {model}")
                
                elif json_obj.get('type') == 'assistant':
                    message = json_obj.get('message', {})
                    content = message.get('content', [])
                    
                    for content_item in content:
                        if content_item.get('type') == 'text':
                            text_content = content_item.get('text', '')
                            if text_content.strip():
                                output_lines.append(text_content)
                        
                        elif content_item.get('type') == 'tool_use':
                            tool_name = content_item.get('name', 'unknown')
                            output_lines.append(f"\n[Tool] Using: {tool_name}")
                            
                            # Show tool details
                            input_data = content_item.get('input', {})
                            if tool_name == 'Write':
                                file_path = input_data.get('file_path', '')
                                if file_path:
                                    output_lines.append(f"   Creating file: {file_path}")
                            elif tool_name == 'Edit':
                                file_path = input_data.get('file_path', '')
                                if file_path:
                                    output_lines.append(f"   Editing file: {file_path}")
                            elif tool_name == 'Read':
                                file_path = input_data.get('file_path', '')
                                if file_path:
                                    output_lines.append(f"   Reading file: {file_path}")
                            elif tool_name == 'Bash':
                                command = input_data.get('command', '')
                                if command:
                                    output_lines.append(f"   Running: {command}")
                
                elif json_obj.get('type') == 'user':
                    message = json_obj.get('message', {})
                    content = message.get('content', [])
                    
                    for content_item in content:
                        if content_item.get('type') == 'tool_result':
                            result_content = content_item.get('content', '')
                            if result_content:
                                # Truncate long results
                                if len(result_content) > 200:
                                    result_content = result_content[:200] + "..."
                                output_lines.append(f"   Result: {result_content}")
                
                elif json_obj.get('type') == 'result':
                    if json_obj.get('subtype') == 'success':
                        output_lines.append("\n[Claude] Task completed successfully!")
                        result = json_obj.get('result', '')
                        if result:
                            output_lines.append(f"   Result: {result}")
                        cost = json_obj.get('cost_usd', 0)
                        duration = json_obj.get('duration_ms', 0)
                        output_lines.append(f"   Duration: {duration/1000:.1f}s, Cost: ${cost:.4f}")
                    else:
                        error = json_obj.get('error', 'Unknown error')
                        output_lines.append(f"\n[Claude] Task failed: {error}")
                        
            except json.JSONDecodeError:
                # Not JSON, treat as regular output
                if line:
                    output_lines.append(line)
            except Exception as e:
                self.logger.debug(f"Error parsing Claude JSON: {e}")
                output_lines.append(line)
        
        return '\n'.join(output_lines)

    # ---------- Session Management (Thread-Safe) ----------
    def setup_main_session(self):
        """Setup the main tmux session"""
        subprocess.run(["tmux", "kill-session", "-t", self.main_session], check=False)
        self._run(["tmux", "new-session", "-d", "-s", self.main_session, "-n", "controller"])
        welcome = (
            "clear && echo '🚀 CLI AGENT SESSION MANAGER' && "
            "echo '=============================' && "
            "echo 'Sessions for multiple CLI agents (Gemini, Claude Code) will appear as panes.'"
        )
        self._run(["tmux", "send-keys", "-t", f"{self.main_session}:controller", welcome, "C-m"])

    def create_session(self, prompt: str, repo_url: Optional[str] = None, agent_type: Optional[AgentType] = None, yolo_mode: bool = False) -> Optional[str]:
        """Create a new session (thread-safe)"""
        repo_url = repo_url or self.default_repo
        agent_type = agent_type or self.default_agent
        
        # Get agent configuration
        if agent_type not in self.agent_configs:
            self.logger.error(f"Unknown agent type: {agent_type}")
            return None
        
        agent_config = self.agent_configs[agent_type]
        
        # Validate YOLO mode
        if yolo_mode and not agent_config.supports_yolo:
            self.logger.info(f"YOLO mode requested for {agent_type}, but it's not supported. Ignoring.")
            yolo_mode = False
        
        with self._atomic_state_update():
            # Check limits
            active_count = sum(1 for s in self._sessions.values() 
                             if s.status in ("SPAWNING", "RUNNING", "REQUIRES_USER_INPUT"))
            if active_count >= self.max_sessions:
                self.logger.warning(f"Max sessions ({self.max_sessions}) reached")
                return None
            
            # Generate session ID
            sid = self._generate_id(prompt, repo_url, agent_type)
            if sid in self._sessions and self._sessions[sid].status != "DONE":
                self.logger.warning(f"Session {sid} already exists")
                return None
            
            # Create session atomically
            info = SessionInfo(sid, prompt, repo_url, SessionStatus.SPAWNING, time.time(), yolo_mode=yolo_mode, agent_type=agent_type)
            self._sessions[sid] = info
            self._output_buffers[sid] = OutputBuffer()
            
            # Log session creation
            self.logger.info(f"📝 Created {agent_type} session {sid} with YOLO mode: {'ENABLED 🚀' if yolo_mode else 'DISABLED'}")
            
            # Create pane
            try:
                self._run(["tmux", "split-window", "-t", f"{self.main_session}:controller", "-h"])
                self._run(["tmux", "select-layout", "-t", f"{self.main_session}:controller", "tiled"])
                pane_id = self._run([
                    "tmux", "list-panes", "-t", f"{self.main_session}:controller", "-F", "#{pane_id}"
                ]).stdout.strip().split("\n")[-1]
                
                target = f"{self.main_session}:controller.{pane_id}"
                self._pane_mapping[sid] = target
                
                # Set pane title
                self._rename_pane(target, f"SPAWNING‑{sid}")
                
                # Start agent
                actual_prompt = prompt.strip() if prompt.strip() else \
                    "Write a script that runs for 30 seconds, printing timestamps"
                
                project_path = os.getcwd()
                
                # Build command chain: pre-commands + agent command
                all_commands = []
                
                # Add cd to project path
                all_commands.append(f"cd '{project_path}'")
                
                # Add pre-commands
                all_commands.extend(agent_config.pre_commands)
                
                # Build agent command based on type
                if agent_config.supports_interactive:
                    # Interactive agents (Gemini, Claude): just start the agent
                    full_cmd = agent_config.command.copy()
                    
                    # Add YOLO mode flag if enabled and supported
                    if yolo_mode and agent_config.supports_yolo:
                        if agent_type == "claude":
                            # For Claude, replace acceptEdits with dangerously-skip-permissions for full YOLO
                            if "--permission-mode" in full_cmd and "acceptEdits" in full_cmd:
                                # Remove acceptEdits mode and add dangerously-skip-permissions
                                accept_idx = full_cmd.index("acceptEdits")
                                full_cmd[accept_idx] = "bypassPermissions"
                        # For Gemini, YOLO is handled via Ctrl+Y after startup
                    
                    cmd_str = " ".join(full_cmd)
                    all_commands.append(cmd_str)
                else:
                    # Non-interactive agents: include prompt in command
                    full_cmd = agent_config.command.copy()
                    
                    # Add YOLO mode flag if enabled and supported
                    if yolo_mode and agent_config.supports_yolo:
                        # Add agent-specific YOLO flags here for non-interactive agents
                        pass
                    
                    # Add the prompt as the last argument
                    full_cmd.append(actual_prompt)
                    cmd_str = " ".join(shlex.quote(arg) for arg in full_cmd)
                    all_commands.append(cmd_str)
                
                # Join all commands with &&
                full_command = " && ".join(all_commands)
                
                self.logger.info(f"Executing command chain for {agent_type} session {sid}: {full_command}")
                self._run(["tmux", "send-keys", "-t", target, full_command, "C-m"])
                
                # Store prompt for interactive agents
                if agent_config.supports_interactive:
                    self._session_prompts[sid] = actual_prompt
                
                success_message = f"✅ Successfully created {agent_type} session {sid} (YOLO: {'ON' if yolo_mode else 'OFF'})"
                self.logger.info(success_message)
                print(f"📝 {success_message}")
                return sid
                
            except Exception as e:
                # Rollback on error
                self.logger.error(f"Failed to create session {sid}: {e}")
                del self._sessions[sid]
                del self._output_buffers[sid]
                if sid in self._pane_mapping:
                    del self._pane_mapping[sid]
                return None

    def stop_session(self, sid: str) -> bool:
        """Stop a session (thread-safe)"""
        with self._atomic_state_update():
            if sid not in self._sessions:
                return False
            
            info = self._sessions[sid]
            if info.status not in (SessionStatus.RUNNING, SessionStatus.REQUIRES_USER_INPUT, SessionStatus.SPAWNING, SessionStatus.PREMATURE_FINISH):
                return False
            
            pane = self._pane_mapping.get(sid)
            if pane:
                try:
                    # Send termination signals
                    self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                    time.sleep(0.2)
                    self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                    time.sleep(0.2)
                    self._run(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
                    time.sleep(0.3)
                    
                    # Kill pane
                    pane_id = pane.split(".")[-1]
                    self._run(["tmux", "kill-pane", "-t", pane_id], check=False)
                    
                    del self._pane_mapping[sid]
                except Exception as e:
                    self.logger.error(f"Error stopping session {sid}: {e}")
            
            # Update status
            info.status = SessionStatus.STOPPED
            info.end_time = time.time()
            
            # Save output asynchronously
            asyncio.create_task(self._save_session_output_async(sid))
            
            self.logger.info(f"Stopped session {sid}")
            return True

    # ---------- Output Management (Thread-Safe) ----------
    def _capture_pane_output(self, pane: str) -> Optional[str]:
        """Capture output from tmux pane"""
        try:
            # Add timeout to prevent hanging
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", pane],
                capture_output=True,
                text=True,
                timeout=5.0  # 5 second timeout
            )
            if result.returncode != 0:
                # Don't log warnings for missing panes (normal after cleanup)
                if "can't find pane" not in result.stderr:
                    self.logger.warning(f"capture-pane failed for {pane}: {result.stderr}")
                return None
            return result.stdout
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            self.logger.error(f"capture-pane error for {pane}: {e}")
            return None

    async def _update_session_output(self, sid: str) -> Optional[str]:
        """Update output buffer and return changes (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            buffer = self._output_buffers.get(sid)
            session = self._sessions.get(sid)
            
            if not pane or not buffer or not session:
                return None
            
            agent_config = self.agent_configs.get(session.agent_type)
            if not agent_config:
                return None
        
        # Capture outside lock to avoid blocking
        raw_output = self._capture_pane_output(pane)
        if not raw_output:
            return None
        
        # Clean output first
        cleaned = self._clean_terminal_output(raw_output)
        
        # Parse based on agent output format
        if agent_config.output_format == "json":
            # For Claude, parse JSON output
            parsed = self._parse_claude_json_output(cleaned)
        else:
            # For Gemini and others, use cleaned text directly
            parsed = cleaned
        
        # Update buffer atomically
        with self._state_lock:
            buffer = self._output_buffers.get(sid)
            if buffer:
                return buffer.update_content(parsed)
        
        return None

    async def _broadcast_changes(self, sid: str, changes: str):
        """Broadcast changes to all WebSockets (thread-safe)"""
        if not changes:
            return
        
        # Get websockets safely
        with self._ws_lock:
            websockets = list(self._active_websockets.get(sid, set()))
        
        if not websockets:
            return
        
        # Send to all clients with timeout
        disconnected = []
        for ws in websockets:
            try:
                # Add timeout to prevent hanging on WebSocket send
                await asyncio.wait_for(ws.send_text(changes), timeout=2.0)
            except asyncio.TimeoutError:
                disconnected.append(ws)
            except Exception:
                disconnected.append(ws)
        
        # Clean up disconnected
        if disconnected:
            with self._ws_lock:
                ws_set = self._active_websockets.get(sid, set())
                for ws in disconnected:
                    ws_set.discard(ws)
                    ws_id = id(ws)
                    if ws_id in self._websocket_positions.get(sid, {}):
                        del self._websocket_positions[sid][ws_id]

    async def _save_session_output_async(self, sid: str):
        """Save session output asynchronously"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._save_session_output_sync, sid
            )
        except Exception as e:
            self.logger.error(f"Failed to save session {sid} output: {e}", exc_info=True)

    def _save_session_output_sync(self, sid: str):
        """Save session output to JSON (thread-safe)"""
        json_path = self.logs_dir / f"{sid}_output.json"
        
        with self._file_lock:
            try:
                # Get data safely
                with self._state_lock:
                    session = self._sessions.get(sid)
                    buffer = self._output_buffers.get(sid)
                    
                    if not session:
                        return
                    
                    output_data = {
                        "session_id": sid,
                        "status": session.status.value,  # Convert enum to string
                        "prompt": session.prompt,
                        "repo_url": session.repo_url,
                        "agent_type": session.agent_type.value,  # Convert enum to string
                        "yolo_mode": session.yolo_mode,
                        "start_time": session.start_time,
                        "end_time": session.end_time,
                        "output": buffer.get_content() if buffer else "",
                        "saved_at": time.time()
                    }
                
                # Write atomically
                temp_path = json_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                # Atomic rename
                temp_path.replace(json_path)
                
            except Exception as e:
                self.logger.error(f"Failed to save session {sid}: {e}")
                if 'temp_path' in locals() and temp_path.exists():
                    temp_path.unlink()

    # ---------- Status Checking (Thread-Safe) ----------
    def _check_agent_ready(self, sid: str) -> bool:
        """Check if agent is ready (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            session = self._sessions.get(sid)
        
        if not pane or not session:
            return False
        
        agent_config = self.agent_configs.get(session.agent_type)
        if not agent_config:
            return False
        
        # Non-interactive agents are never "ready" in the traditional sense
        if not agent_config.supports_interactive:
            return False
        
        output = self._capture_pane_output(pane)
        if not output:
            return False
        
        # Check for agent-specific ready indicators
        if agent_config.ready_indicator_mode == ReadyIndicatorMode.INCLUSIVE:
            return any(indicator in output for indicator in agent_config.ready_indicators)
        else: # ReadyIndicatorMode.EXCLUSIVE
            return not any(indicator in output for indicator in agent_config.ready_indicators)

    def _check_requires_input(self, sid: str) -> bool:
        """Check if session needs input (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            session = self._sessions.get(sid)
        
        if not pane or not session:
            return False
        
        agent_config = self.agent_configs.get(session.agent_type)
        if not agent_config:
            return False
        
        # Non-interactive agents don't require input
        if not agent_config.supports_interactive:
            return False
        
        output = self._capture_pane_output(pane)
        if not output:
            return False
        
        return any(indicator in output for indicator in agent_config.input_indicators)

    def _check_agent_premature_finish(self, sid: str) -> bool:
        """Check if agent process has finished prematurely (crashed or exited early)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            session = self._sessions.get(sid)
        
        if not pane or not session:
            return False
        
        # Check if pane still exists
        try:
            pane_exists_result = subprocess.run(
                ["tmux", "list-panes", "-t", self.main_session, "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            
            pane_id = pane.split(".")[-1]
            if pane_id not in pane_exists_result.stdout:
                self.logger.error(f"Session {sid}: Pane {pane_id} no longer exists")
                return True
        except Exception as e:
            self.logger.error(f"Session {sid}: Error checking pane existence: {e}")
            return True
        
        # Check if there's a shell prompt at the end (indicates process exited)
        output = self._capture_pane_output(pane)
        if not output:
            return False
        
        # Get last few non-empty lines
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        if not lines:
            return False
        
        # Check for common shell prompts that indicate the process has exited
        last_lines = lines[-5:]  # Check last 5 lines
        for line in last_lines:
            # Look for shell prompts
            if (line.endswith('$') or line.endswith('%') or line.endswith('#') or 
                line.endswith('> ') or line.startswith('bash-') or line.startswith('zsh-') or
                'command not found' in line or 'No such file or directory' in line or
                'Traceback (most recent call last)' in line or 'Error:' in line or
                'error:' in line or 'ERROR:' in line or 'Fatal:' in line or
                'fatal:' in line or 'FATAL:' in line or 'Segmentation fault' in line or
                'Aborted' in line or 'Killed' in line or 'Terminated' in line):
                
                # Make sure it's not part of the agent's normal output
                if ('gemini' not in line.lower() and 'claude' not in line.lower() and 
                    'Type your message' not in line and 'esc to interrupt' not in line):
                    self.logger.warning(f"Session {sid}: Detected premature finish indicator: {line}")
                    return True
        
        # For interactive agents, check if we're back at shell after sending prompt
        if session.status == SessionStatus.RUNNING and sid in self._prompt_sent_time:
            time_since_prompt = time.time() - self._prompt_sent_time[sid]
            if time_since_prompt > 5.0:  # After 5 seconds
                # Check if we have a bare shell prompt without agent indicators
                for line in last_lines:
                    if (line.endswith('$') or line.endswith('%')) and len(line) < 50:
                        # This is likely a shell prompt, not agent output
                        agent_config = self.agent_configs.get(session.agent_type)
                        if agent_config:
                            # Make sure none of the agent's indicators are present
                            has_agent_indicator = False
                            for indicator in (agent_config.ready_indicators + 
                                            agent_config.input_indicators + 
                                            agent_config.busy_indicators):
                                if indicator in output:
                                    has_agent_indicator = True
                                    break
                            
                            if not has_agent_indicator:
                                self.logger.warning(f"Session {sid}: Agent appears to have finished prematurely (shell prompt detected)")
                                return True
        
        return False

    def _check_done(self, sid: str) -> bool:
        """Check if session is done (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            session = self._sessions.get(sid)
            prompt_sent = self._prompt_sent_time.get(sid, 0)
        
        if not pane or not session:
            return True
        
        agent_config = self.agent_configs.get(session.agent_type)
        if not agent_config:
            return True
        
        # First check if agent process has finished prematurely
        if self._check_agent_premature_finish(sid):
            self.logger.warning(f"Session {sid}: Agent process has finished prematurely")
            # Update status to PREMATURE_FINISH if not already done/stopped
            if session.status not in (SessionStatus.DONE, SessionStatus.STOPPED, SessionStatus.PREMATURE_FINISH):
                session.status = SessionStatus.PREMATURE_FINISH
            return True
        
        # Different completion check methods
        if agent_config.completion_check_method == "process_exit":
            # For non-interactive agents, check if process is still running
            # Try to capture pane - if it fails, process has exited
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", pane],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            
            # Also check if the pane still exists
            pane_exists_result = subprocess.run(
                ["tmux", "list-panes", "-t", self.main_session, "-F", "#{pane_id}"],
                capture_output=True,
                text=True
            )
            
            pane_id = pane.split(".")[-1]
            if pane_id not in pane_exists_result.stdout:
                return True
            
            # Check if pane still exists for process_exit method
            if result.returncode != 0:
                return True
            
            return False
            
        else:  # ready_prompt method (for interactive agents like Gemini)
            # Wait minimum time after prompt
            if time.time() - prompt_sent < agent_config.completion_timeout:
                return False
            
            output = self._capture_pane_output(pane)
            if not output:
                return True
            
            # Check for completion by looking for ready indicators again
            lines = output.split('\n')[-10:]
            
            # Don't mark done if session requires input
            if self._check_requires_input(sid):
                return False
            
            # First check busy indicators - if any are present, not done
            if agent_config.busy_indicators:
                for line in lines:
                    for indicator in agent_config.busy_indicators:
                        if indicator in line:
                            return False  # Still busy
            
            # Then check ready indicators based on mode
            if agent_config.ready_indicator_mode == ReadyIndicatorMode.INCLUSIVE:
                # Look for ready indicators (agent is ready for next prompt)
                for line in lines:
                    for indicator in agent_config.ready_indicators:
                        if indicator in line:
                            return True
            else:  # ReadyIndicatorMode.EXCLUSIVE mode
                # Check that none of the ready indicators are present
                for line in lines:
                    for indicator in agent_config.ready_indicators:
                        if indicator in line:
                            return False  # Indicator present = not ready
                # If we get here, no indicators found = ready
                return True
            
            # Also check for shell prompt as fallback (only for inclusive mode)
            if agent_config.ready_indicator_mode == ReadyIndicatorMode.INCLUSIVE:
                for line in lines:
                    stripped = line.strip()
                    if stripped and (
                        (stripped.endswith('%') or stripped.endswith('$')) and
                        len(stripped) < 50 and
                        'gemini-' not in stripped and 'claude-' not in stripped
                    ):
                        return True
            
            return False

    # ---------- Main Update Loop (Thread-Safe) ----------
    async def update_sessions(self):
        """Update all sessions (thread-safe)"""
        # Get session list snapshot
        with self._state_lock:
            session_ids = list(self._sessions.keys())
        
        for sid in session_ids:
            try:
                # Skip completed sessions to avoid trying to capture from non-existent panes
                with self._state_lock:
                    session = self._sessions.get(sid)
                    if not session or session.status in ("DONE", "STOPPED", "PREMATURE_FINISH"):
                        continue
                
                # Update output
                changes = await self._update_session_output(sid)
                if changes:
                    await self._broadcast_changes(sid, changes)
                
                # Handle state transitions atomically
                await self._handle_state_transition(sid)
                
            except Exception as e:
                self.logger.error(f"Error updating session {sid}: {e}")

    async def _handle_state_transition(self, sid: str):
        """Handle state transitions atomically"""
        with self._atomic_state_update():
            session = self._sessions.get(sid)
            if not session or session.status in ("DONE", "STOPPED", "PREMATURE_FINISH"):
                return
            
            pane = self._pane_mapping.get(sid)
            if not pane:
                return
            
            # Check for premature finish first in any state
            if self._check_agent_premature_finish(sid):
                session.status = SessionStatus.PREMATURE_FINISH
                session.end_time = time.time()
                self.logger.info(f"Session {sid}: PREMATURE_FINISH - Agent process finished earlier than expected")
                self._rename_pane(pane, f"PREMATURE‑{sid}")
                # Schedule save in background
                save_task = asyncio.create_task(self._save_session_output_async(sid))
                save_task.add_done_callback(lambda t: None if not t.exception() else 
                                           self.logger.error(f"Background save failed for {sid}: {t.exception()}"))
                await self._cleanup_session(sid)
                return
            
            # State machine
            if session.status == SessionStatus.SPAWNING:
                # Debug logging for all sessions
                self.logger.debug(f"Session {sid}: Checking SPAWNING state - agent={session.agent_type}, yolo_mode={session.yolo_mode}")
                
                agent_config = self.agent_configs.get(session.agent_type)
                if not agent_config:
                    return
                
                if self._check_requires_input(sid):
                    session.status = SessionStatus.REQUIRES_USER_INPUT
                    self.logger.info(f"Session {sid}: SPAWNING -> REQUIRES_USER_INPUT")
                    self._rename_pane(pane, f"INPUT‑{sid}")
                elif agent_config.supports_interactive and self._check_agent_ready(sid):
                    session.status = SessionStatus.RUNNING
                    self.logger.info(f"Session {sid}: SPAWNING -> RUNNING (Agent: {session.agent_type}, YOLO mode: {session.yolo_mode})")
                    
                    # Handle YOLO mode for interactive agents
                    if session.yolo_mode and agent_config.supports_yolo:
                        if session.agent_type == AgentType.GEMINI:
                            # For Gemini: Send Ctrl+Y after it's ready to toggle YOLO mode
                            yolo_message = f"🚀 Session {sid}: YOLO MODE ACTIVATED - Sending Ctrl+Y to toggle YOLO in {session.agent_type}"
                            self.logger.info(yolo_message)
                            print("\n" + "="*80)
                            print(yolo_message)
                            print("="*80 + "\n")
                            
                            try:
                                # Send CTRL+Y using tmux standard notation
                                result = self._run(["tmux", "send-keys", "-t", pane, "C-y"])
                                success_message = f"✅ Session {sid}: CTRL+Y sent successfully to pane {pane}"
                                self.logger.info(success_message)
                                print(f"✅ {success_message}")
                                
                                # Wait for agent to process the YOLO toggle
                                await asyncio.sleep(1.5)
                            except subprocess.CalledProcessError as e:
                                error_message = f"❌ Session {sid}: Failed to send CTRL+Y: {e}"
                                self.logger.error(error_message)
                                print(f"❌ {error_message}")
                                await asyncio.sleep(1)
                        elif session.agent_type == AgentType.CLAUDE:
                            # For Claude: YOLO mode is handled via --permission-mode bypassPermissions
                            yolo_message = f"🚀 Session {sid}: YOLO MODE ACTIVATED - Claude started with --permission-mode bypassPermissions"
                            self.logger.info(yolo_message)
                            print("\n" + "="*80)
                            print(yolo_message)
                            print("="*80 + "\n")
                        # Add other interactive agents' YOLO handling here
                    else:
                        if session.yolo_mode and not agent_config.supports_yolo:
                            self.logger.info(f"Session {sid}: YOLO mode requested but not supported by {session.agent_type}")
                        else:
                            self.logger.debug(f"Session {sid}: YOLO mode disabled")
                    
                    # Send prompt for interactive agents
                    prompt = self._session_prompts.get(sid)
                    if prompt:
                        self._run(["tmux", "send-keys", "-t", pane, "-l", prompt])
                        await asyncio.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "C-m"])
                        self._prompt_sent_time[sid] = time.time()
                        del self._session_prompts[sid]
                        self._rename_pane(pane, f"RUNNING‑{sid}")

            
            elif session.status == SessionStatus.RUNNING:
                if self._check_requires_input(sid):
                    session.status = SessionStatus.REQUIRES_USER_INPUT
                    self.logger.info(f"Session {sid}: RUNNING -> REQUIRES_USER_INPUT")
                    self._rename_pane(pane, f"INPUT‑{sid}")
                elif self._check_done(sid):
                    try:
                        session.status = SessionStatus.DONE
                        session.end_time = time.time()
                        # Schedule save in background to avoid blocking state transition
                        save_task = asyncio.create_task(self._save_session_output_async(sid))
                        save_task.add_done_callback(lambda t: None if not t.exception() else 
                                                   self.logger.error(f"Background save failed for {sid}: {t.exception()}"))
                        self.logger.info(f"Session {sid}: RUNNING -> DONE")
                        self._rename_pane(pane, f"DONE‑{sid}")
                        await self._cleanup_session(sid)
                    except Exception as e:
                        self.logger.error(f"Exception in DONE transition for {sid}: {e}", exc_info=True)
            
            elif session.status == SessionStatus.REQUIRES_USER_INPUT:
                if self._check_done(sid):
                    session.status = SessionStatus.DONE
                    session.end_time = time.time()
                    # Schedule save in background to avoid blocking state transition
                    save_task = asyncio.create_task(self._save_session_output_async(sid))
                    save_task.add_done_callback(lambda t: None if not t.exception() else 
                                               self.logger.error(f"Background save failed for {sid}: {t.exception()}"))
                    self.logger.info(f"Session {sid}: REQUIRES_USER_INPUT -> DONE")
                    self._rename_pane(pane, f"DONE‑{sid}")
                    await self._cleanup_session(sid)
                elif not self._check_requires_input(sid):
                    session.status = SessionStatus.RUNNING
                    self.logger.info(f"Session {sid}: REQUIRES_USER_INPUT -> RUNNING")
                    
                    # Send prompt if it hasn't been sent yet (this handles SPAWNING -> REQUIRES_USER_INPUT -> RUNNING path)
                    prompt = self._session_prompts.get(sid)
                    if prompt:
                        self._run(["tmux", "send-keys", "-t", pane, "-l", prompt])
                        await asyncio.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "C-m"])
                        self._prompt_sent_time[sid] = time.time()
                        del self._session_prompts[sid]
                        self.logger.info(f"Session {sid}: Sent delayed prompt after input resolution")
                    
                    self._rename_pane(pane, f"RUNNING‑{sid}")

    async def _cleanup_session(self, sid: str):
        """Clean up completed session"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
        
        if pane:
            try:
                # Send CTRL+C twice quickly
                self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                await asyncio.sleep(0.1)  # Short delay between CTRL+C commands
                self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                await asyncio.sleep(0.3)  # Wait a bit for processes to terminate
                
                # Type exit and press enter
                self._run(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
                await asyncio.sleep(0.2)  # Give it time to process
                
                # Remove pane mapping since the pane is now closed
                with self._state_lock:
                    if sid in self._pane_mapping:
                        del self._pane_mapping[sid]
                        
            except Exception as e:
                self.logger.warning(f"Cleanup error for {sid}: {e}")

    def save_status(self):
        """Save status to file (thread-safe)"""
        with self._file_lock:
            try:
                with self._state_lock:
                    data = {sid: s.to_dict() for sid, s in self._sessions.items()}
                
                temp_path = self.status_file.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2)
                temp_path.replace(self.status_file)
                
            except Exception as e:
                self.logger.error(f"Failed to save status: {e}")

    async def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self.update_sessions()
                self.save_status()
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(2)

    # ---------- Public API Methods (Thread-Safe) ----------
    def get_sessions(self) -> List[Dict]:
        """Get all sessions safely"""
        with self._state_lock:
            return [s.to_dict() for s in self._sessions.values()]
    
    def get_session(self, sid: str) -> Optional[Dict]:
        """Get single session safely"""
        with self._state_lock:
            session = self._sessions.get(sid)
            return session.to_dict() if session else None
    
    def get_session_output(self, sid: str) -> Optional[str]:
        """Get session output safely"""
        with self._state_lock:
            buffer = self._output_buffers.get(sid)
            return buffer.get_content() if buffer else None
    
    async def send_input(self, sid: str, response: str) -> bool:
        """Send input to session"""
        with self._state_lock:
            session = self._sessions.get(sid)
            pane = self._pane_mapping.get(sid)
            
            if not session or session.status != SessionStatus.REQUIRES_USER_INPUT or not pane:
                return False
        
        try:
            self._run(["tmux", "send-keys", "-t", pane, response])
            await asyncio.sleep(1)
            self._run(["tmux", "send-keys", "-t", pane, "C-m"])
            return True
        except Exception as e:
            self.logger.error(f"Failed to send input: {e}")
            return False

    def register_websocket(self, sid: str, ws: WebSocket):
        """Register WebSocket connection"""
        with self._ws_lock:
            self._active_websockets[sid].add(ws)
            self._websocket_positions[sid][id(ws)] = 0
    
    def unregister_websocket(self, sid: str, ws: WebSocket):
        """Unregister WebSocket connection"""
        with self._ws_lock:
            self._active_websockets[sid].discard(ws)
            ws_id = id(ws)
            if ws_id in self._websocket_positions.get(sid, {}):
                del self._websocket_positions[sid][ws_id]

# ---------------------------- FastAPI App ------------------------------------
app = FastAPI()
manager: Optional[TmuxAgentManager] = None

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": manager.get_sessions()}

@app.get("/api/sessions/{sid}")
async def get_session(sid: str):
    session = manager.get_session(sid)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return session

@app.get("/api/sessions/{sid}/output")
async def get_session_output(sid: str):
    """Get session output"""
    session = manager.get_session(sid)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    
    # Try saved file first
    json_path = manager.logs_dir / f"{sid}_output.json"
    if json_path.exists():
        try:
            async with aiofiles.open(json_path, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception:
            pass
    
    # Return current buffer
    output = manager.get_session_output(sid)
    if output is not None:
        return {
            "session_id": sid,
            "status": session["status"],
            "output": output
        }
    
    return JSONResponse({"error": "No output available"}, status_code=404)

from pydantic import BaseModel

class CreateSessionRequest(BaseModel):
    prompt: str
    repo_url: Optional[str] = None
    agent_type: str = AgentType.GEMINI.value  # Agent type as string, will be converted to enum
    yolo_mode: bool = False

@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create new session"""
    if not request.prompt:
        return JSONResponse({"error": "Prompt required"}, status_code=400)
    
    # Convert string agent_type to enum
    try:
        agent_type_enum = manager._get_agent_type(request.agent_type)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    
    # Validate agent type
    if agent_type_enum not in manager.agent_configs:
        return JSONResponse({"error": f"Invalid agent type: {request.agent_type}"}, status_code=400)
    
    # Validate YOLO mode
    agent_config = manager.agent_configs[agent_type_enum]
    if request.yolo_mode and not agent_config.supports_yolo:
        manager.logger.info(f"YOLO mode requested for {request.agent_type}, but it's not supported. Ignoring.")
        request.yolo_mode = False
    
    # Log the API request with agent type and YOLO mode status
    api_message = f"🌐 API: Creating {request.agent_type} session with prompt='{request.prompt[:50]}...' yolo_mode={request.yolo_mode}"
    manager.logger.info(api_message)
    
    # Extra visibility for YOLO mode requests
    if request.yolo_mode:
        yolo_impl = "Ctrl+Y toggle" if request.agent_type == "gemini" else "--dangerously-skip-permissions flag"
        print(f"\n🚀 YOLO MODE REQUEST RECEIVED for {request.agent_type}: {request.prompt[:50]}... (Implementation: {yolo_impl})")
    
    sid = manager.create_session(request.prompt, request.repo_url, agent_type_enum, request.yolo_mode)
    if sid:
        return {"status": "created", "session_id": sid, "agent_type": request.agent_type}
    
    return JSONResponse({"error": "Failed to create session"}, status_code=500)

@app.post("/api/sessions/{sid}/stop")
async def stop_session(sid: str):
    """Stop session"""
    if manager.stop_session(sid):
        return {"status": "stopped", "session_id": sid}
    return JSONResponse({"error": "Session not found"}, status_code=404)

@app.post("/api/sessions/{sid}/input")
async def send_input(sid: str, response: str):
    """Send input to session"""
    if await manager.send_input(sid, response):
        return {"status": "input_sent", "session_id": sid}
    return JSONResponse({"error": "Cannot send input"}, status_code=400)

@app.get("/api/sessions/{sid}/options")
async def get_session_options(sid: str):
    """Get session options/context for user input"""
    session = manager.get_session(sid)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    
    if session["status"] != SessionStatus.REQUIRES_USER_INPUT.value:
        return JSONResponse({"error": "Session does not require input"}, status_code=400)
    
    # Get current output to show context
    output = manager.get_session_output(sid)
    if output is not None:
        # Split into lines and get recent context
        lines = output.split('\n')
        return {
            "session_id": sid,
            "status": session["status"],
            "full_output": lines,
            "context": lines[-20:] if len(lines) > 20 else lines  # Last 20 lines
        }
    
    return JSONResponse({"error": "No context available"}, status_code=404)

@app.post("/api/sessions/clean")
async def clean_previous_sessions():
    """Clean up all previous sessions"""
    try:
        with manager._atomic_state_update():
            # Get all sessions that are done, stopped, or finished prematurely
            sessions_to_clean = []
            for sid, session in manager._sessions.items():
                if session.status in ("DONE", "STOPPED", "PREMATURE_FINISH"):
                    sessions_to_clean.append(sid)
            
            # Remove from internal state
            for sid in sessions_to_clean:
                if sid in manager._sessions:
                    del manager._sessions[sid]
                if sid in manager._output_buffers:
                    del manager._output_buffers[sid]
                if sid in manager._pane_mapping:
                    pane = manager._pane_mapping[sid]
                    try:
                        # Kill the pane if it still exists
                        pane_id = pane.split(".")[-1]
                        manager._run(["tmux", "kill-pane", "-t", pane_id], check=False)
                    except Exception:
                        pass
                    del manager._pane_mapping[sid]
                
                # Clean up any remaining state
                if sid in manager._session_prompts:
                    del manager._session_prompts[sid]
                if sid in manager._prompt_sent_time:
                    del manager._prompt_sent_time[sid]
        
        # Clean up WebSocket connections
        with manager._ws_lock:
            for sid in sessions_to_clean:
                if sid in manager._active_websockets:
                    del manager._active_websockets[sid]
                if sid in manager._websocket_positions:
                    del manager._websocket_positions[sid]
        
        manager.logger.info(f"Cleaned {len(sessions_to_clean)} sessions")
        return {"status": "cleaned", "count": len(sessions_to_clean)}
        
    except Exception as e:
        manager.logger.error(f"Failed to clean sessions: {e}")
        return JSONResponse({"error": "Failed to clean sessions"}, status_code=500)

@app.websocket("/ws/{sid}")
async def websocket_endpoint(websocket: WebSocket, sid: str):
    """WebSocket for streaming output"""
    await websocket.accept()
    
    # Register
    manager.register_websocket(sid, websocket)
    
    try:
        # Send current content
        output = manager.get_session_output(sid)
        if output:
            await websocket.send_text(output)
        
        # Keep alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister_websocket(sid, websocket)

@app.get("/")
async def index():
    """Serve UI"""
    html_path = Path(__file__).parent / "tmux_gemini_ui.html"
    if html_path.exists():
        with open(html_path, 'r') as f:
            content = f.read()
            return HTMLResponse(content)
    return HTMLResponse("<h1>UI file not found</h1>")

# ---------------------------- Main Entry --------------------------------------
async def run_server():
    """Run uvicorn server in a separate thread with its own event loop"""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        workers=1,  # Single worker to minimize threads
        loop="none",  # Don't create new event loop
        access_log=False  # Reduce logging overhead
    )
    server = uvicorn.Server(config)
    await server.serve()

async def main(max_sessions: int = 50, attach: bool = False, ui: bool = False, interactive: bool = True, global_pre_commands: List[str] | None = None, default_agent: AgentType = AgentType.GEMINI):
    global manager
    manager = TmuxAgentManager(max_sessions=max_sessions, global_pre_commands=global_pre_commands, default_agent=default_agent)
    manager.setup_main_session()
    
    # Start monitoring
    monitor_task = asyncio.create_task(manager.monitor_loop())
    
    server_thread = None
    if ui:
        # Run uvicorn in a separate thread to avoid asyncio thread explosion
        import threading
        server_thread = threading.Thread(
            target=lambda: uvicorn.run(
                app, 
                host="0.0.0.0", 
                port=8000, 
                log_level="warning",
                workers=1,
                access_log=False
            ),
            daemon=True
        )
        server_thread.start()
        print("🌐 UI running on http://localhost:8000")
    
    if attach:
        # Attach to tmux (non-blocking)
        subprocess.Popen(["tmux", "attach", "-t", manager.main_session])
    
    print("🚀 Multi-agent tmux manager running. Press Ctrl+C to stop.")
    print(f"📋 Supported agents: {', '.join(str(agent) for agent in manager.agent_configs.keys())}")
    print(f"🎯 YOLO Mode Support: Available for agents with interactive mode")
    print(f"📊 Max sessions: {max_sessions}")
    if global_pre_commands:
        print(f"⚙️  Pre-commands: {global_pre_commands}")
    
    if interactive:
        print("📝 Enter prompts or 'q' to quit:")
        
        # Use a single thread for input instead of creating new ones
        import queue
        input_queue = queue.Queue()
        
        def input_thread():
            while manager.running:
                try:
                    line = input("> ")
                    input_queue.put(line)
                except (EOFError, KeyboardInterrupt):
                    input_queue.put(None)
                    break
        
        input_thread_instance = threading.Thread(target=input_thread, daemon=True)
        input_thread_instance.start()
        
        # Main event loop
        try:
            while manager.running:
                try:
                    # Check for input without blocking
                    prompt = input_queue.get_nowait()
                    
                    if prompt is None:  # EOF or interrupt
                        break
                    
                    if prompt.lower() in ('q', 'quit', 'exit'):
                        break
                    
                    if prompt.strip():
                        manager.create_session(prompt.strip())
                        
                except queue.Empty:
                    # No input available, just continue
                    await asyncio.sleep(0.1)
                    
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
    else:
        # Non-interactive mode - just run until interrupted
        try:
            while manager.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
    
    # Cleanup
    manager.running = False
    monitor_task.cancel()
    
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-agent CLI tmux manager")
    parser.add_argument("--max", type=int, default=50, help="Max concurrent sessions")
    parser.add_argument("--attach", action="store_true", help="Attach to tmux")
    parser.add_argument("--ui", action="store_true", help="Start web UI")
    parser.add_argument("--no-interactive", action="store_true", help="Run without interactive prompt")
    parser.add_argument("--pre-commands", type=str, help="Comma-separated list of commands to run before agent (e.g., 'source venv/bin/activate,pip install -r requirements.txt')")
    parser.add_argument("--default-agent", type=str, default=AgentType.GEMINI.value, choices=[agent.value for agent in AgentType], help="Default agent to use")
    args = parser.parse_args()
    
    # Parse pre-commands from comma-separated string
    pre_commands = []
    if args.pre_commands:
        pre_commands = [cmd.strip() for cmd in args.pre_commands.split(',') if cmd.strip()]
    
    # Convert string agent to enum
    try:
        default_agent_enum = AgentType(args.default_agent)
    except ValueError:
        print(f"Error: Invalid agent type '{args.default_agent}'. Valid choices: {[agent.value for agent in AgentType]}")
        sys.exit(1)
    
    try:
        asyncio.run(main(
            max_sessions=args.max, 
            attach=args.attach, 
            ui=args.ui,
            interactive=not args.no_interactive,
            global_pre_commands=pre_commands,
            default_agent=default_agent_enum
        ))
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    finally:
        # Cleanup tmux session
        subprocess.run(["tmux", "kill-session", "-t", "agent_manager"], check=False)