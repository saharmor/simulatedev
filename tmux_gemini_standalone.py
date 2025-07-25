#!/usr/bin/env python3
"""
Gemini CLI tmux Manager + Lean UI (v4.1)
========================================
Thread-safe version with all race conditions fixed.

Key improvements:
- Comprehensive locking for all shared state
- Atomic state transitions
- Safe WebSocket management
- Proper async/await usage
- Robust error recovery

Run:
```bash
pip install fastapi uvicorn "python-multipart>=0.0.5" aiofiles
python gemini_tmux_manager.py --attach --ui
```
"""

import asyncio
import subprocess
import time
import json
import hashlib
import sys
import os
import signal
import threading
import logging
import re
import fcntl
import queue
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from contextlib import contextmanager
from pydantic import BaseModel

# ---------------------------- UI DEPS ----------------------------------------
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import aiofiles

# ---------------------------- Data Models ------------------------------------
@dataclass
class SessionInfo:
    session_id: str
    prompt: str
    repo_url: str
    status: str  # SPAWNING, RUNNING, DONE, STOPPED, REQUIRES_USER_INPUT
    start_time: float
    end_time: Optional[float] = None
    
    def copy(self):
        """Create a safe copy for external use"""
        return SessionInfo(
            session_id=self.session_id,
            prompt=self.prompt,
            repo_url=self.repo_url,
            status=self.status,
            start_time=self.start_time,
            end_time=self.end_time
        )

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
class TmuxGeminiManager:
    """Thread-safe manager for multiple tmux sessions with efficient streaming."""

    def __init__(self, max_sessions: int = 50, default_repo: str | None = None):
        self.max_sessions = max_sessions
        self.default_repo = default_repo or "https://github.com/saharmor/gemini-multimodal-playground"
        self.running = True
        self.main_session = "gemini_manager"
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        self.status_file = Path("tmux_sessions_status.json")
        
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
        self.logger.info("TmuxGeminiManager initialized (thread-safe version)")

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

    def _generate_id(self, prompt: str, repo_url: str) -> str:
        return "gemini_" + hashlib.md5(f"{prompt}:{repo_url}".encode()).hexdigest()[:8]

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

    # ---------- Session Management (Thread-Safe) ----------
    def setup_main_session(self):
        """Setup the main tmux session"""
        subprocess.run(["tmux", "kill-session", "-t", self.main_session], check=False)
        self._run(["tmux", "new-session", "-d", "-s", self.main_session, "-n", "controller"])
        welcome = (
            "clear && echo '🚀 GEMINI SESSION MANAGER' && "
            "echo '=========================' && "
            "echo 'Sessions will appear as panes.'"
        )
        self._run(["tmux", "send-keys", "-t", f"{self.main_session}:controller", welcome, "C-m"])

    def create_session(self, prompt: str, repo_url: Optional[str] = None) -> Optional[str]:
        """Create a new session (thread-safe)"""
        repo_url = repo_url or self.default_repo
        
        with self._atomic_state_update():
            # Check limits
            active_count = sum(1 for s in self._sessions.values() 
                             if s.status in ("SPAWNING", "RUNNING", "REQUIRES_USER_INPUT"))
            if active_count >= self.max_sessions:
                self.logger.warning(f"Max sessions ({self.max_sessions}) reached")
                return None
            
            # Generate session ID
            sid = self._generate_id(prompt, repo_url)
            if sid in self._sessions and self._sessions[sid].status != "DONE":
                self.logger.warning(f"Session {sid} already exists")
                return None
            
            # Create session atomically
            info = SessionInfo(sid, prompt, repo_url, "SPAWNING", time.time())
            self._sessions[sid] = info
            self._output_buffers[sid] = OutputBuffer()
            
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
                
                # Start Gemini
                actual_prompt = prompt.strip() if prompt.strip() else \
                    "Write a script that runs for 30 seconds, printing timestamps"
                
                project_path = os.getcwd()
                gemini_cmd = f"cd '{project_path}' && gemini 2>&1"
                self._run(["tmux", "send-keys", "-t", target, gemini_cmd, "C-m"])
                
                # Store prompt
                self._session_prompts[sid] = actual_prompt
                
                self.logger.info(f"Created session {sid}")
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
            if info.status not in ("RUNNING", "REQUIRES_USER_INPUT", "SPAWNING"):
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
            info.status = "STOPPED"
            info.end_time = time.time()
            
            # Save output asynchronously
            asyncio.create_task(self._save_session_output_async(sid))
            
            self.logger.info(f"Stopped session {sid}")
            return True

    # ---------- Output Management (Thread-Safe) ----------
    def _capture_pane_output(self, pane: str) -> Optional[str]:
        """Capture output from tmux pane"""
        try:
            result = self._run(["tmux", "capture-pane", "-p", "-t", pane])
            return result.stdout
        except Exception:
            return None

    async def _update_session_output(self, sid: str) -> Optional[str]:
        """Update output buffer and return changes (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            buffer = self._output_buffers.get(sid)
            
            if not pane or not buffer:
                return None
        
        # Capture outside lock to avoid blocking
        raw_output = self._capture_pane_output(pane)
        if not raw_output:
            return None
        
        # Clean output
        cleaned = self._clean_terminal_output(raw_output)
        
        # Update buffer atomically
        with self._state_lock:
            buffer = self._output_buffers.get(sid)
            if buffer:
                return buffer.update_content(cleaned)
        
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
        
        # Send to all clients
        disconnected = []
        for ws in websockets:
            try:
                await ws.send_text(changes)
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
        await asyncio.get_event_loop().run_in_executor(
            None, self._save_session_output_sync, sid
        )

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
                        "status": session.status,
                        "prompt": session.prompt,
                        "repo_url": session.repo_url,
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
                
                self.logger.info(f"Saved session {sid} output")
                
            except Exception as e:
                self.logger.error(f"Failed to save session {sid}: {e}")
                if temp_path.exists():
                    temp_path.unlink()

    # ---------- Status Checking (Thread-Safe) ----------
    def _check_gemini_ready(self, sid: str) -> bool:
        """Check if Gemini is ready (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
        
        if not pane:
            return False
        
        output = self._capture_pane_output(pane)
        if not output:
            return False
        
        ready_indicators = [
            "Loaded cached credentials",
            "Loading Gemini",
            "Type your message",
            "Command:"
        ]
        
        return any(indicator in output for indicator in ready_indicators)

    def _check_requires_input(self, sid: str) -> bool:
        """Check if session needs input (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
        
        if not pane:
            return False
        
        output = self._capture_pane_output(pane)
        if not output:
            return False
        
        input_indicators = [
            "Apply this change?",
            "● 1. Yes, allow once",
            "● 2. Yes, allow always",
            "(Use Enter to select)",
            "Continue? (y/n)",
            "Confirm?"
        ]
        
        return any(indicator in output for indicator in input_indicators)

    def _check_done(self, sid: str) -> bool:
        """Check if session is done (thread-safe)"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
            prompt_sent = self._prompt_sent_time.get(sid, 0)
        
        if not pane:
            return True
        
        # Wait minimum time after prompt
        if time.time() - prompt_sent < 10:
            return False
        
        output = self._capture_pane_output(pane)
        if not output:
            return True
        
        # Check for completion
        lines = output.split('\n')[-10:]
        
        # Look for "Type your message" after response
        if not self._check_requires_input(sid):
            for line in lines:
                if "Type your message" in line:
                    return True
        
        # Check for shell prompt
        for line in lines:
            stripped = line.strip()
            if stripped and (
                (stripped.endswith('%') or stripped.endswith('$')) and
                len(stripped) < 50 and
                'gemini-' not in stripped
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
            if not session or session.status in ("DONE", "STOPPED"):
                return
            
            pane = self._pane_mapping.get(sid)
            if not pane:
                return
            
            # State machine
            if session.status == "SPAWNING":
                if self._check_requires_input(sid):
                    session.status = "REQUIRES_USER_INPUT"
                    self.logger.info(f"Session {sid}: SPAWNING -> REQUIRES_USER_INPUT")
                    self._rename_pane(pane, f"INPUT‑{sid}")
                elif self._check_gemini_ready(sid):
                    session.status = "RUNNING"
                    self.logger.info(f"Session {sid}: SPAWNING -> RUNNING")
                    
                    # Send prompt
                    prompt = self._session_prompts.get(sid)
                    if prompt:
                        self._run(["tmux", "send-keys", "-t", pane, "-l", prompt])
                        await asyncio.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "C-m"])
                        self._prompt_sent_time[sid] = time.time()
                        del self._session_prompts[sid]
                        self._rename_pane(pane, f"RUNNING‑{sid}")
            
            elif session.status == "RUNNING":
                if self._check_requires_input(sid):
                    session.status = "REQUIRES_USER_INPUT"
                    self.logger.info(f"Session {sid}: RUNNING -> REQUIRES_USER_INPUT")
                    self._rename_pane(pane, f"INPUT‑{sid}")
                elif self._check_done(sid):
                    session.status = "DONE"
                    session.end_time = time.time()
                    await self._save_session_output_async(sid)
                    self.logger.info(f"Session {sid}: RUNNING -> DONE")
                    self._rename_pane(pane, f"DONE‑{sid}")
                    await self._cleanup_session(sid)
            
            elif session.status == "REQUIRES_USER_INPUT":
                if self._check_done(sid):
                    session.status = "DONE"
                    session.end_time = time.time()
                    await self._save_session_output_async(sid)
                    self.logger.info(f"Session {sid}: REQUIRES_USER_INPUT -> DONE")
                    self._rename_pane(pane, f"DONE‑{sid}")
                    await self._cleanup_session(sid)
                elif not self._check_requires_input(sid):
                    session.status = "RUNNING"
                    self.logger.info(f"Session {sid}: REQUIRES_USER_INPUT -> RUNNING")
                    self._rename_pane(pane, f"RUNNING‑{sid}")

    async def _cleanup_session(self, sid: str):
        """Clean up completed session"""
        with self._state_lock:
            pane = self._pane_mapping.get(sid)
        
        if pane:
            try:
                self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                await asyncio.sleep(0.2)
                self._run(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
            except Exception as e:
                self.logger.warning(f"Cleanup error for {sid}: {e}")

    def save_status(self):
        """Save status to file (thread-safe)"""
        with self._file_lock:
            try:
                with self._state_lock:
                    data = {sid: asdict(s.copy()) for sid, s in self._sessions.items()}
                
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
            return [asdict(s.copy()) for s in self._sessions.values()]
    
    def get_session(self, sid: str) -> Optional[Dict]:
        """Get single session safely"""
        with self._state_lock:
            session = self._sessions.get(sid)
            return asdict(session.copy()) if session else None
    
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
            
            if not session or session.status != "REQUIRES_USER_INPUT" or not pane:
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
manager: Optional[TmuxGeminiManager] = None

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

@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create new session"""
    if not request.prompt:
        return JSONResponse({"error": "Prompt required"}, status_code=400)
    
    sid = manager.create_session(request.prompt, request.repo_url)
    if sid:
        return {"status": "created", "session_id": sid}
    
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
    
    if session["status"] != "REQUIRES_USER_INPUT":
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
            # Get all sessions that are done or stopped
            sessions_to_clean = []
            for sid, session in manager._sessions.items():
                if session.status in ("DONE", "STOPPED"):
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

async def main(max_sessions: int = 50, attach: bool = False, ui: bool = False, interactive: bool = True):
    global manager
    manager = TmuxGeminiManager(max_sessions=max_sessions)
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
    
    print("🚀 Gemini tmux manager running. Press Ctrl+C to stop.")
    
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
    parser = argparse.ArgumentParser(description="Gemini tmux manager")
    parser.add_argument("--max", type=int, default=50, help="Max concurrent sessions")
    parser.add_argument("--attach", action="store_true", help="Attach to tmux")
    parser.add_argument("--ui", action="store_true", help="Start web UI")
    parser.add_argument("--no-interactive", action="store_true", help="Run without interactive prompt")
    args = parser.parse_args()
    
    try:
        asyncio.run(main(
            max_sessions=args.max, 
            attach=args.attach, 
            ui=args.ui,
            interactive=not args.no_interactive
        ))
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    finally:
        # Cleanup tmux session
        subprocess.run(["tmux", "kill-session", "-t", "gemini_manager"], check=False)