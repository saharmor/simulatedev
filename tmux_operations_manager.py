#!/usr/bin/env python3
"""
Tmux Operations Manager
======================
Handles all tmux session and pane management operations for CLI agents.

This module contains:
- Agent configurations and data models
- TmuxCommandQueue for serialized command execution
- TmuxAgentManager for session lifecycle management
- Output capture and processing
- State transition handling
"""

import asyncio
import subprocess
import time
import json
import hashlib
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
from enum import Enum

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
            "export GEMINI_API_KEY=\"AIzaSyDDq3LndW44_-5DQfPurgkB0HZJPe6R2x8\"",
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
    spawning_timeout: float = 30.0  # Maximum time to stay in SPAWNING state
    
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
            agent_type=self.agent_type,
            spawning_timeout=self.spawning_timeout
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
            "agent_type": self.agent_type.value,  # Convert enum to string
            "spawning_timeout": self.spawning_timeout
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

# ---------------------------- Command Queue for Concurrency Control ----------
class TmuxCommandQueue:
    """Serializes tmux commands per-pane to prevent interleaving while allowing parallel execution across panes"""
    
    def __init__(self):
        self._pane_queues = {}  # pane_id -> asyncio.Queue
        self._pane_workers = {}  # pane_id -> worker task
        self._global_queue = asyncio.Queue()  # For non-pane-specific commands
        self._global_worker = None
        self._running = False
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """Start the command workers"""
        self._running = True
        self._global_worker = asyncio.create_task(self._global_worker_loop())
        self.logger.info("TmuxCommandQueue started with per-pane queueing")
    
    async def stop(self):
        """Stop all command workers"""
        self._running = False
        
        # Cancel global worker
        if self._global_worker:
            self._global_worker.cancel()
            try:
                await self._global_worker
            except asyncio.CancelledError:
                pass
        
        # Cancel all pane workers
        for worker in self._pane_workers.values():
            worker.cancel()
        
        # Wait for all workers to finish
        if self._pane_workers:
            await asyncio.gather(*self._pane_workers.values(), return_exceptions=True)
        
        self._pane_queues.clear()
        self._pane_workers.clear()
        self.logger.info("TmuxCommandQueue stopped")
    
    def _extract_pane_id(self, cmd: List[str]) -> Optional[str]:
        """Extract pane ID from tmux command"""
        # Look for -t flag followed by pane identifier
        for i, arg in enumerate(cmd):
            if arg == "-t" and i + 1 < len(cmd):
                target = cmd[i + 1]
                # Extract pane ID from various formats:
                # - Direct pane ID: %0, %1, etc.
                # - Session:window.pane format: main:0.%0
                # - Full path: agent_manager:controller.%5
                if "%" in target:
                    # Extract just the pane ID part
                    return target.split(".")[-1] if "." in target else target
                else:
                    # For commands targeting session/window, use full target as ID
                    return target
        return None
    
    async def _pane_worker_loop(self, pane_id: str, queue: asyncio.Queue):
        """Worker loop for a specific pane"""
        self.logger.debug(f"Started worker for pane {pane_id}")
        
        while self._running:
            try:
                cmd, future = await queue.get()
                try:
                    # Execute command with subprocess
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, 
                        lambda: subprocess.run(cmd, capture_output=True, text=True, check=False)
                    )
                    future.set_result(result)
                    
                    # Add delay between commands for the same pane
                    # Longer delay for send-keys to ensure proper delivery
                    if "send-keys" in cmd:
                        await asyncio.sleep(0.1)  # 100ms for send-keys
                    else:
                        await asyncio.sleep(0.05)  # 50ms for other commands
                        
                except Exception as e:
                    future.set_exception(e)
                finally:
                    queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Pane worker error for {pane_id}: {e}")
        
        self.logger.debug(f"Stopped worker for pane {pane_id}")
    
    async def _global_worker_loop(self):
        """Worker loop for non-pane-specific commands"""
        self.logger.debug("Started global worker")
        
        while self._running:
            try:
                cmd, future = await self._global_queue.get()
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, 
                        lambda: subprocess.run(cmd, capture_output=True, text=True, check=False)
                    )
                    future.set_result(result)
                    
                    # Small delay between global commands
                    await asyncio.sleep(0.05)
                    
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self._global_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Global worker error: {e}")
        
        self.logger.debug("Stopped global worker")
    
    async def execute(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Execute command through the appropriate queue"""
        future = asyncio.Future()
        
        # Extract pane ID from command
        pane_id = self._extract_pane_id(cmd)
        
        if pane_id:
            # Use pane-specific queue
            if pane_id not in self._pane_queues:
                # Create new queue and worker for this pane
                self._pane_queues[pane_id] = asyncio.Queue()
                self._pane_workers[pane_id] = asyncio.create_task(
                    self._pane_worker_loop(pane_id, self._pane_queues[pane_id])
                )
                self.logger.debug(f"Created queue for pane {pane_id}")
            
            await self._pane_queues[pane_id].put((cmd, future))
        else:
            # Use global queue for non-pane-specific commands
            await self._global_queue.put((cmd, future))
        
        return await future
    
    async def cleanup_pane(self, pane_id: str):
        """Clean up queue and worker for a specific pane"""
        if pane_id in self._pane_workers:
            # Cancel worker
            self._pane_workers[pane_id].cancel()
            try:
                await self._pane_workers[pane_id]
            except asyncio.CancelledError:
                pass
            
            # Remove queue and worker
            del self._pane_workers[pane_id]
            del self._pane_queues[pane_id]
            self.logger.debug(f"Cleaned up queue for pane {pane_id}")
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """Get current queue sizes for monitoring"""
        sizes = {"global": self._global_queue.qsize()}
        for pane_id, queue in self._pane_queues.items():
            sizes[f"pane_{pane_id}"] = queue.qsize()
        return sizes

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
        
        # File operations lock
        self._file_lock = threading.Lock()
        
        # Command queue for concurrency control
        self._tmux_queue = TmuxCommandQueue()
        self._session_locks = {}  # sid -> asyncio.Lock
        self._adaptive_monitor_delay = 5.0
        
        # Add session creation throttling
        self._creation_lock = asyncio.Lock()
        self._last_session_creation_time = 0
        self._min_creation_interval = 5.0  # Minimum 5 seconds between session creations
        
        # Global concurrency control
        self._global_tmux_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent tmux operations
        
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

    async def _run_async(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run command asynchronously with global concurrency control"""
        async with self._global_tmux_semaphore:  # Add this line
            try:
                result = await self._tmux_queue.execute(cmd)
                if check and result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
                return result
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

    async def _rename_pane_async(self, full_target: str, new_name: str):
        """Set pane title safely (async)"""
        try:
            pane_id = full_target.split(".")[-1]
            await self._run_async(["tmux", "select-pane", "-t", pane_id, "-T", new_name])
        except Exception as e:
            self.logger.warning(f"Failed to rename pane: {e}")
    
    def _escape_text_for_tmux(self, text: str, pane: str = None) -> str:
        """Escape text for safe transmission via tmux send-keys.
        
        The -l (literal) flag in tmux send-keys handles most characters correctly,
        including single quotes, double quotes, and special characters. However,
        we still need to handle some edge cases for maximum reliability.
        """
        # The -l flag handles quotes and most special characters correctly
        # We only need minimal escaping for truly problematic characters
        escaped_text = text
        
        # Handle null bytes which can cause issues
        if '\x00' in escaped_text:
            escaped_text = escaped_text.replace('\x00', '')
            self.logger.warning("Removed null bytes from text for tmux transmission")
        
        # Gemini CLI specific fix: Remove exclamation marks to prevent shell mode toggle
        if pane:
            # Find the session associated with this pane
            with self._state_lock:
                session_id = None
                for sid, mapped_pane in self._pane_mapping.items():
                    if mapped_pane == pane:
                        session_id = sid
                        break
                
                if session_id:
                    session = self._sessions.get(session_id)
                    if session and session.agent_type == AgentType.GEMINI:
                        if '!' in escaped_text:
                            original_count = escaped_text.count('!')
                            escaped_text = escaped_text.replace('!', '')
                            self.logger.info(f"Removed {original_count} exclamation mark(s) from text for Gemini CLI to prevent shell mode toggle")
        
        # Handle very long lines that might cause issues
        if len(escaped_text) > 2000:
            self.logger.warning(f"Text is very long ({len(escaped_text)} chars), consider using buffer method")
        
        self.logger.debug(f"Text prepared for tmux: '{text[:100]}{'...' if len(text) > 100 else ''}'")
        return escaped_text

    async def _send_text_with_enter_async(self, pane: str, text: str) -> None:
        """Send text to pane followed by Enter key with proper synchronization and retry logic"""
        self.logger.info(f"_send_text_with_enter_async called for pane {pane} with text: {text[:50]}...")
        
        # Escape text for safe transmission to tmux
        escaped_text = self._escape_text_for_tmux(text, pane)

        # For long prompts, use buffer method as primary approach
        if len(escaped_text) > 500:
            await self._send_long_text_with_enter(pane, escaped_text)
            return
        
        # Retry logic for better reliability
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{max_retries + 1} to send text to pane {pane}")
                
                # Method 1: Send text with literal flag
                await self._run_async(["tmux", "send-keys", "-t", pane, "-l", escaped_text])
                
                # Critical: Wait for tmux to process, longer for longer texts
                wait_time = 0.5 + (len(escaped_text) / 1000) * 0.5  # Increased base wait time
                await asyncio.sleep(wait_time)
                
                # Verify text was received by checking pane content
                output = await self._capture_pane_output_async(pane)
                text_found = False
                if output:
                    # Check if the original text appears in the output (look for a portion of it)
                    # Use original text for verification since that's what should appear in the terminal
                    check_text = text[-min(30, len(text)):] if len(text) > 30 else text
                    if check_text in output:
                        text_found = True
                    else:
                        # Also check if any significant portion of the text is there
                        if len(text) > 10:
                            mid_text = text[len(text)//2:len(text)//2+20]
                            if mid_text in output:
                                text_found = True
                
                if not text_found and attempt < max_retries:
                    self.logger.warning(f"Text not found in pane output on attempt {attempt + 1}, retrying...")
                    await asyncio.sleep(0.5)
                    continue
                elif not text_found:
                    self.logger.warning(f"Text not fully confirmed in pane output after {max_retries + 1} attempts, proceeding anyway")
                
                # Send Enter key - this is the critical part that was failing
                self.logger.debug(f"Sending Enter key to pane {pane}")
                await self._run_async(["tmux", "send-keys", "-t", pane, "C-m"])
                
                # Small delay to ensure Enter is processed
                await asyncio.sleep(0.2)
                
                self.logger.info(f"Successfully sent text with enter to pane {pane} on attempt {attempt + 1}")
                return
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed to send text with enter: {e}")
                if attempt == max_retries:
                    self.logger.error(f"All {max_retries + 1} attempts failed for pane {pane}")
                    raise
                else:
                    await asyncio.sleep(0.5)  # Wait before retry

    async def _send_long_text_with_enter(self, pane: str, text: str) -> None:
        """Handle long text using buffer method for reliability"""
        try:
            # Create unique buffer name to avoid conflicts
            buffer_name = f"agent_buffer_{hashlib.md5(text.encode()).hexdigest()[:8]}"
            
            # Set buffer with unique name
            await self._run_async(["tmux", "set-buffer", "-b", buffer_name, "--", text])
            
            # Small delay to ensure buffer is ready
            await asyncio.sleep(0.1)
            
            # Paste from specific buffer
            await self._run_async(["tmux", "paste-buffer", "-b", buffer_name, "-t", pane])
            
            # Wait for paste to complete (longer for long text)
            wait_time = 0.5 + (len(text) / 500) * 0.3
            await asyncio.sleep(wait_time)
            
            # Delete buffer to free memory
            await self._run_async(["tmux", "delete-buffer", "-b", buffer_name])
            
            # Send Enter
            await self._run_async(["tmux", "send-keys", "-t", pane, "C-m"])
            
            self.logger.info(f"Successfully sent long text ({len(text)} chars) with enter to pane {pane}")
        except Exception as e:
            self.logger.error(f"Buffer method failed: {e}")
            raise

    async def _verify_prompt_submitted(self, sid: str, prompt: str, timeout: float = 5.0) -> bool:
        """Verify that a prompt was actually submitted to the agent"""
        start_time = time.time()
        
        with self._state_lock:
            session = self._sessions.get(sid)
            pane = self._pane_mapping.get(sid)
            
        if not session or not pane:
            return False
        
        agent_config = self.agent_configs.get(session.agent_type)
        if not agent_config:
            return False
        
        while time.time() - start_time < timeout:
            output = await self._capture_pane_output_async(pane)
            if not output:
                await asyncio.sleep(0.5)
                continue
            
            # Check if prompt appears in output
            prompt_visible = prompt[:50] in output
            
            # Check if agent is no longer showing ready indicators (meaning it's processing)
            if agent_config.ready_indicator_mode == ReadyIndicatorMode.INCLUSIVE:
                # For inclusive mode, ready indicators should disappear when processing
                still_ready = any(indicator in output for indicator in agent_config.ready_indicators)
                if prompt_visible and not still_ready:
                    return True
            else:  # EXCLUSIVE mode
                # For exclusive mode, busy indicators should appear
                is_busy = any(indicator in output for indicator in agent_config.busy_indicators)
                if prompt_visible and is_busy:
                    return True
            
            await asyncio.sleep(0.5)
        
        return False

    # Keep original method for backward compatibility in sync contexts
    def _send_text_with_enter(self, pane: str, text: str) -> None:
        """Send text to pane followed by Enter key, handling it robustly (legacy sync version)"""
        try:
            # Escape text for safe transmission to tmux
            escaped_text = self._escape_text_for_tmux(text, pane)
            # Use literal text method directly for better concurrency
            self._run(["tmux", "send-keys", "-t", pane, "-l", escaped_text])
            self._run(["tmux", "send-keys", "-t", pane, "C-m"])
        except Exception as e:
            self.logger.error(f"Failed to send text with enter: {e}")
            raise

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

    async def create_session_async(self, prompt: str, repo_url: Optional[str] = None, 
                                  agent_type: Optional[AgentType] = None, yolo_mode: bool = False) -> Optional[str]:
        """Async version of create_session with proper throttling"""
        async with self._creation_lock:
            # Enforce minimum interval between creations
            time_since_last = time.time() - self._last_session_creation_time
            if time_since_last < self._min_creation_interval:
                await asyncio.sleep(self._min_creation_interval - time_since_last)
            
            # Call the existing synchronous create_session in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.create_session, prompt, repo_url, agent_type, yolo_mode)
            
            self._last_session_creation_time = time.time()
            return result

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
                actual_prompt = prompt.strip()
                
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
                        if agent_type == AgentType.CLAUDE:
                            # For Claude, replace acceptEdits with bypassPermissions for full YOLO
                            if "--permission-mode" in full_cmd and "acceptEdits" in full_cmd:
                                # Find and replace acceptEdits with bypassPermissions
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
                
                # Wait for agent to spawn before monitoring starts checking readiness
                # This prevents premature ready detection before the agent has fully started
                time.sleep(3.0)
                self.logger.debug(f"Session {sid}: Waited 3 seconds for agent to spawn")
                
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

    async def _terminate_pane(self, sid: str, pane: str, force_kill: bool = False):
        """Shared logic for terminating tmux panes"""
        try:
            # Send CTRL+C twice to interrupt any running processes
            await self._run_async(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
            await asyncio.sleep(0.1)
            await self._run_async(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
            await asyncio.sleep(0.3)
            
            # Send exit command
            await self._run_async(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
            await asyncio.sleep(0.2)
            
            # Force kill pane if requested (for stop_session)
            if force_kill:
                pane_id = pane.split(".")[-1]
                await self._run_async(["tmux", "kill-pane", "-t", pane_id], check=False)
            
            # Clean up the pane's command queue
            pane_id = self._tmux_queue._extract_pane_id(["tmux", "-t", pane])
            if pane_id:
                await self._tmux_queue.cleanup_pane(pane_id)
            
            # Remove pane mapping
            with self._state_lock:
                if sid in self._pane_mapping:
                    del self._pane_mapping[sid]
                    
        except Exception as e:
            self.logger.warning(f"Pane termination error for {sid}: {e}")

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
                # Use async termination in a task for consistency
                async def _async_stop():
                    await self._terminate_pane(sid, pane, force_kill=True)
                
                # Schedule the async termination
                asyncio.create_task(_async_stop())
            
            # Update status
            info.status = SessionStatus.STOPPED
            info.end_time = time.time()
            
            # Save output asynchronously
            asyncio.create_task(self._save_session_output_async(sid))
            
            # Clean up session lock
            if sid in self._session_locks:
                del self._session_locks[sid]
            
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

    async def _capture_pane_output_async(self, pane: str) -> Optional[str]:
        """Capture output from tmux pane asynchronously"""
        try:
            result = await self._run_async(
                ["tmux", "capture-pane", "-p", "-t", pane],
                check=False
            )
            if result.returncode != 0:
                if "can't find pane" not in result.stderr:
                    self.logger.warning(f"capture-pane failed for {pane}: {result.stderr}")
                return None
            return result.stdout
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
        raw_output = await self._capture_pane_output_async(pane)
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
        """Check if agent is ready (thread-safe) with improved detection"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            session = self._sessions.get(sid)
        
        if not pane or not session:
            self.logger.debug(f"_check_agent_ready({sid}): No pane or session found")
            return False
        
        agent_config = self.agent_configs.get(session.agent_type)
        if not agent_config:
            self.logger.debug(f"_check_agent_ready({sid}): No agent config found for {session.agent_type}")
            return False
        
        # Non-interactive agents are never "ready" in the traditional sense
        if not agent_config.supports_interactive:
            self.logger.debug(f"_check_agent_ready({sid}): Agent {session.agent_type} is non-interactive")
            return False
        
        # Check if we've been in SPAWNING state too long - fallback to ready
        time_in_spawning = time.time() - session.start_time
        if time_in_spawning > 15.0:  # 15 seconds is enough for any agent to start
            self.logger.warning(f"_check_agent_ready({sid}): Timeout fallback - been in SPAWNING for {time_in_spawning:.1f}s, assuming ready")
            return True
        
        output = self._capture_pane_output(pane)
        if not output:
            self.logger.debug(f"_check_agent_ready({sid}): No output captured from pane {pane}")
            # If no output after 10 seconds, assume ready (agent might have started)
            if time_in_spawning > 10.0:
                self.logger.warning(f"_check_agent_ready({sid}): No output after {time_in_spawning:.1f}s, assuming ready")
                return True
            return False
        
        # Debug: Log the captured output and what we're looking for
        self.logger.debug(f"_check_agent_ready({sid}): Agent type = {session.agent_type}")
        self.logger.debug(f"_check_agent_ready({sid}): Ready indicator mode = {agent_config.ready_indicator_mode}")
        self.logger.debug(f"_check_agent_ready({sid}): Looking for indicators = {agent_config.ready_indicators}")
        
        # Check for agent-specific ready indicators with improved logic
        if agent_config.ready_indicator_mode == ReadyIndicatorMode.INCLUSIVE:
            # Look for ready indicators in the output
            ready_found = False
            for indicator in agent_config.ready_indicators:
                if indicator in output:
                    ready_found = True
                    self.logger.debug(f"_check_agent_ready({sid}): Found indicator '{indicator}'")
                    break
            
            # Additional heuristics for Gemini
            if not ready_found and session.agent_type == AgentType.GEMINI:
                # Check if we see typical Gemini startup patterns
                if any(pattern in output.lower() for pattern in ['gemini', 'model:', 'loading', 'ready']):
                    if time_in_spawning > 8.0:  # Give it time to fully load
                        self.logger.debug(f"_check_agent_ready({sid}): Gemini heuristic - assuming ready after {time_in_spawning:.1f}s")
                        ready_found = True
            
            self.logger.debug(f"_check_agent_ready({sid}): INCLUSIVE mode result = {ready_found}")
            return ready_found
            
        else: # ReadyIndicatorMode.EXCLUSIVE
            result = not any(indicator in output for indicator in agent_config.ready_indicators)
            self.logger.debug(f"_check_agent_ready({sid}): EXCLUSIVE mode result = {result}")
            return result

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
        """Update all sessions with better concurrency control"""
        with self._state_lock:
            session_ids = list(self._sessions.keys())
            active_count = sum(1 for s in self._sessions.values() 
                             if s.status not in (SessionStatus.DONE, SessionStatus.STOPPED, SessionStatus.PREMATURE_FINISH))
        
        # Adaptive monitoring - take more time between checks as the number of active sessions increases
        if active_count > 10:
            self._adaptive_monitor_delay = self._adaptive_monitor_delay * 1.5
        elif active_count > 20:
            self._adaptive_monitor_delay = self._adaptive_monitor_delay * 2.0
        
        # Limit concurrent operations
        semaphore = asyncio.Semaphore(5)
        
        async def update_single_session(sid):
            async with semaphore:
                try:
                    with self._state_lock:
                        session = self._sessions.get(sid)
                        if not session or session.status in (SessionStatus.DONE, SessionStatus.STOPPED, SessionStatus.PREMATURE_FINISH):
                            return
                    
                    # Get or create session lock
                    if sid not in self._session_locks:
                        self._session_locks[sid] = asyncio.Lock()
                    
                    async with self._session_locks[sid]:
                        changes = await self._update_session_output(sid)
                        await self._handle_state_transition(sid)
                        return changes
                    
                except Exception as e:
                    self.logger.error(f"Error updating session {sid}: {e}")
                    return None
        
        tasks = [update_single_session(sid) for sid in session_ids]
        if tasks:
            results = await asyncio.gather(*tasks)
            return dict(zip(session_ids, results))
        return {}

    async def _handle_state_transition(self, sid: str):
        """Handle state transitions atomically"""
        self.logger.debug(f"_handle_state_transition({sid}): Starting state check")
        with self._atomic_state_update():
            session = self._sessions.get(sid)
            if not session or session.status in ("DONE", "STOPPED", "PREMATURE_FINISH"):
                self.logger.debug(f"_handle_state_transition({sid}): Session not found or already finished")
                return
            
            pane = self._pane_mapping.get(sid)
            if not pane:
                return
            
            # Check for premature finish first in any state
            if self._check_agent_premature_finish(sid):
                session.status = SessionStatus.PREMATURE_FINISH
                session.end_time = time.time()
                self.logger.info(f"Session {sid}: PREMATURE_FINISH - Agent process finished earlier than expected")
                await self._rename_pane_async(pane, f"PREMATURE‑{sid}")
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
                
                # Check for timeout in SPAWNING state (safety fallback)
                time_in_spawning = time.time() - session.start_time
                if time_in_spawning > session.spawning_timeout:
                    self.logger.error(f"Session {sid}: SPAWNING timeout after {time_in_spawning:.1f}s - forcing transition to RUNNING")
                    session.status = SessionStatus.RUNNING
                    # Force send the prompt since we're bypassing normal ready detection
                    prompt = self._session_prompts.get(sid)
                    if prompt:
                        await self._send_text_with_enter_async(pane, prompt)
                        self._prompt_sent_time[sid] = time.time()
                        del self._session_prompts[sid]
                        await self._rename_pane_async(pane, f"TIMEOUT‑RUNNING‑{sid}")
                        self.logger.warning(f"Session {sid}: Forced prompt send due to timeout")
                    return
                
                if self._check_requires_input(sid):
                    session.status = SessionStatus.REQUIRES_USER_INPUT
                    self.logger.info(f"Session {sid}: SPAWNING -> REQUIRES_USER_INPUT")
                    await self._rename_pane_async(pane, f"INPUT‑{sid}")
                elif agent_config.supports_interactive:
                    self.logger.debug(f"Session {sid}: Checking if interactive agent is ready...")
                    is_ready = self._check_agent_ready(sid)
                    self.logger.debug(f"Session {sid}: _check_agent_ready returned {is_ready}")
                    if is_ready:
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
                                    await self._run_async(["tmux", "send-keys", "-t", pane, "C-y"])
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
                        self.logger.info(f"Session {sid}: Checking for prompt - found: {bool(prompt)}, prompts dict: {list(self._session_prompts.keys())}")
                        if prompt:
                            self.logger.info(f"Session {sid}: Sending prompt: {prompt[:50]}...")
                            
                            # Send prompt with new method
                            await self._send_text_with_enter_async(pane, prompt)
                            self._prompt_sent_time[sid] = time.time()
                            
                            # Verify submission
                            if await self._verify_prompt_submitted(sid, prompt):
                                self.logger.info(f"Session {sid}: Prompt successfully submitted")
                                del self._session_prompts[sid]
                                await self._rename_pane_async(pane, f"RUNNING‑{sid}")
                            else:
                                self.logger.error(f"Session {sid}: Prompt submission verification failed")
                                # Retry once
                                await asyncio.sleep(1.0)
                                await self._send_text_with_enter_async(pane, prompt)
                                del self._session_prompts[sid]
                                await self._rename_pane_async(pane, f"RUNNING‑{sid}")
                        else:
                            self.logger.warning(f"Session {sid}: No prompt found in _session_prompts!")
                    else:
                        # Log why we're not ready yet (for debugging)
                        self.logger.debug(f"Session {sid}: Still in SPAWNING - not ready yet (time: {time_in_spawning:.1f}s)")

            
            elif session.status == SessionStatus.RUNNING:
                if self._check_requires_input(sid):
                    session.status = SessionStatus.REQUIRES_USER_INPUT
                    self.logger.info(f"Session {sid}: RUNNING -> REQUIRES_USER_INPUT")
                    await self._rename_pane_async(pane, f"INPUT‑{sid}")
                elif self._check_done(sid):
                    try:
                        session.status = SessionStatus.DONE
                        session.end_time = time.time()
                        # Schedule save in background to avoid blocking state transition
                        save_task = asyncio.create_task(self._save_session_output_async(sid))
                        save_task.add_done_callback(lambda t: None if not t.exception() else 
                                                   self.logger.error(f"Background save failed for {sid}: {t.exception()}"))
                        self.logger.info(f"Session {sid}: RUNNING -> DONE")
                        await self._rename_pane_async(pane, f"DONE‑{sid}")
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
                    await self._rename_pane_async(pane, f"DONE‑{sid}")
                    await self._cleanup_session(sid)
                elif not self._check_requires_input(sid):
                    session.status = SessionStatus.RUNNING
                    self.logger.info(f"Session {sid}: REQUIRES_USER_INPUT -> RUNNING")
                    
                    # Send prompt if it hasn't been sent yet (this handles SPAWNING -> REQUIRES_USER_INPUT -> RUNNING path)
                    prompt = self._session_prompts.get(sid)
                    if prompt:
                        # Send prompt with verification
                        await self._send_text_with_enter_async(pane, prompt)
                        self._prompt_sent_time[sid] = time.time()
                        
                        # Verify submission
                        if await self._verify_prompt_submitted(sid, prompt):
                            self.logger.info(f"Session {sid}: Delayed prompt successfully submitted after input resolution")
                            del self._session_prompts[sid]
                        else:
                            self.logger.error(f"Session {sid}: Delayed prompt submission verification failed")
                            # Retry once
                            await asyncio.sleep(1.0)
                            await self._send_text_with_enter_async(pane, prompt)
                            del self._session_prompts[sid]
                    
                    await self._rename_pane_async(pane, f"RUNNING‑{sid}")

    async def _cleanup_session(self, sid: str):
        """Clean up completed session"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
        
        if pane:
            # Use shared termination logic without force kill (gentler cleanup)
            await self._terminate_pane(sid, pane, force_kill=False)
        
        # Clean up session lock
        with self._state_lock:
            if sid in self._session_locks:
                del self._session_locks[sid]

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
        """Adaptive monitoring loop that continuously monitors sessions"""
        self.logger.info("Starting monitoring loop...")
        while self.running:
            try:
                session_changes = await self.update_sessions()
                self.save_status()  # Call synchronously since it's already thread-safe
                
                # Log active sessions count and queue sizes for debugging
                with self._state_lock:
                    active_count = sum(1 for s in self._sessions.values() 
                                     if s.status not in (SessionStatus.DONE, SessionStatus.STOPPED, SessionStatus.PREMATURE_FINISH))
                    if active_count > 0:
                        queue_sizes = self._tmux_queue.get_queue_sizes()
                        non_empty_queues = {k: v for k, v in queue_sizes.items() if v > 0}
                        if non_empty_queues:
                            self.logger.debug(f"Monitoring {active_count} active sessions. Queue sizes: {non_empty_queues}")
                        else:
                            self.logger.debug(f"Monitoring {active_count} active sessions")
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(self._adaptive_monitor_delay)
        
        self.logger.info("Monitoring loop stopped")

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
            # Use the robust helper method
            await self._send_text_with_enter_async(pane, response)
            self.logger.debug(f"Successfully sent input to session {sid}: {response}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send input to session {sid}: {e}")
            return False

    def cleanup_finished_sessions(self) -> int:
        """Clean up all finished sessions and return count"""
        with self._atomic_state_update():
            # Get all sessions that are done, stopped, or finished prematurely
            sessions_to_clean = []
            for sid, session in self._sessions.items():
                if session.status in ("DONE", "STOPPED", "PREMATURE_FINISH"):
                    sessions_to_clean.append(sid)
            
            # Remove from internal state
            for sid in sessions_to_clean:
                if sid in self._sessions:
                    del self._sessions[sid]
                if sid in self._output_buffers:
                    del self._output_buffers[sid]
                if sid in self._pane_mapping:
                    pane = self._pane_mapping[sid]
                    try:
                        # Kill the pane if it still exists
                        pane_id = pane.split(".")[-1]
                        self._run(["tmux", "kill-pane", "-t", pane_id], check=False)
                        
                        # Clean up the pane's command queue
                        queue_pane_id = self._tmux_queue._extract_pane_id(["tmux", "-t", pane])
                        if queue_pane_id:
                            # Schedule async cleanup (can't await in sync context)
                            asyncio.create_task(self._tmux_queue.cleanup_pane(queue_pane_id))
                    except Exception:
                        pass
                    del self._pane_mapping[sid]
                
                # Clean up any remaining state
                if sid in self._session_prompts:
                    del self._session_prompts[sid]
                if sid in self._prompt_sent_time:
                    del self._prompt_sent_time[sid]
        
        self.logger.info(f"Cleaned {len(sessions_to_clean)} sessions")
        return len(sessions_to_clean)

    async def debug_pane_state(self, sid: str):
        """Debug helper to log current pane state"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            session = self._sessions.get(sid)
        
        if pane and session:
            output = await self._capture_pane_output_async(pane)
            last_lines = output.split('\n')[-10:] if output else []
            
            self.logger.debug(f"""
            Session {sid} Debug Info:
            - Status: {session.status}
            - Agent: {session.agent_type}
            - Pane: {pane}
            - Last 10 lines: {last_lines}
            - Ready indicators found: {self._check_agent_ready(sid)}
            - Requires input: {self._check_requires_input(sid)}
            """)

    # ---------- Queue Management ----------
    async def start_queue(self):
        """Start the command queue"""
        await self._tmux_queue.start()

    async def stop_queue(self):
        """Stop the command queue"""
        await self._tmux_queue.stop() 