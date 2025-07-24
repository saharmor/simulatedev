#!/usr/bin/env python3
"""
Gemini CLI tmux Manager + Lean UI (v3.1)
========================================
Fixes `rename-pane` target errors on macOS/Linux by renaming panes via their
**pane‑id only** (e.g. `%14`) instead of the composite
`session:window.%id` string that tmux rejects.

Other behaviour unchanged:
• Detached‑first manager (inspired by claude_code_agent_farm)
• FastAPI + WebSocket UI on `http://localhost:8000` when `--ui` flag passed
• Logs for each session in `logs/<session>.log`

Run:
```bash
pip install fastapi uvicorn "python-multipart>=0.0.5"
python gemini_tmux_manager.py --attach --ui
```
"""

import asyncio
import subprocess
import time
import json
import hashlib
import random
import sys
import os
import signal
import threading
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# ---------------------------- UI DEPS ----------------------------------------
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ---------------------------- Data Models ------------------------------------
@dataclass
class SessionInfo:
    session_id: str
    prompt: str
    repo_url: str
    status: str  # SPAWNING, RUNNING, DONE, STOPPED, REQUIRES_USER_INPUT
    start_time: float
    end_time: Optional[float] = None

# ---------------------------- Manager ----------------------------------------
class TmuxGeminiManager:
    """Manages multiple tmux sessions for Gemini CLI (mock‑mode)."""

    def __init__(self, max_sessions: int = 50, default_repo: str | None = None):
        self.sessions: Dict[str, SessionInfo] = {}
        self.max_sessions = max_sessions
        self.default_repo = default_repo or "https://github.com/saharmor/gemini-multimodal-playground"
        self.running = True
        self.main_session = "gemini_manager"
        self.pane_mapping: Dict[str, str] = {}
        self.next_pane_index = 0
        self.logs_dir = Path("logs"); self.logs_dir.mkdir(exist_ok=True)
        self.status_file = Path("tmux_sessions_status.json")
        
        # Setup debug logging
        debug_log_file = self.logs_dir / "debug.log"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(debug_log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("TmuxGeminiManager initialized")

    # ---------- low‑level helpers ----------
    def _run(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def _generate_id(self, prompt: str, repo_url: str) -> str:
        return "gemini_" + hashlib.md5(f"{prompt}:{repo_url}".encode()).hexdigest()[:8]

    def _rename_pane(self, full_target: str, new_name: str):
        """Set pane title using select-pane -T (modern tmux syntax)."""
        pane_id = full_target.split(".")[-1]  # e.g. '%14'
        self._run(["tmux", "select-pane", "-t", pane_id, "-T", new_name])

    # ---------- session / pane creation ----------
    def setup_main_session(self):
        subprocess.run(["tmux", "kill-session", "-t", self.main_session], check=False)
        self._run(["tmux", "new-session", "-d", "-s", self.main_session, "-n", "controller"])
        welcome = (
            "clear && echo '🚀 GEMINI SESSION MANAGER' && "
            "echo '=========================' && "
            "echo 'Use tmux prefix + arrow keys to navigate panes; prefix+d to detach.'"
        )
        self._run(["tmux", "send-keys", "-t", f"{self.main_session}:controller", welcome, "C-m"])

    def _new_pane(self, session_id: str) -> str:
        self._run(["tmux", "split-window", "-t", f"{self.main_session}:controller", "-h"])
        self._run(["tmux", "select-layout", "-t", f"{self.main_session}:controller", "tiled"])
        pane_id = self._run([
            "tmux", "list-panes", "-t", f"{self.main_session}:controller", "-F", "#{pane_id}"
        ]).stdout.strip().split("\n")[-1]
        target = f"{self.main_session}:controller.{pane_id}"
        self.pane_mapping[session_id] = target
        return target

    def _pipe_log(self, pane_target: str, session_id: str):
        log_path = self.logs_dir / f"{session_id}.log"
        # Try using pipe-pane with both input and output capture
        self._run(["tmux", "pipe-pane", "-IO", "-t", pane_target, f"cat >> {log_path}"], check=False)

    def create_session(self, prompt: str, repo_url: Optional[str] = None):
        repo_url = repo_url or self.default_repo
        if sum(1 for s in self.sessions.values() if s.status in ("SPAWNING", "RUNNING", "REQUIRES_USER_INPUT")) >= self.max_sessions:
            self.logger.warning(f"Max sessions ({self.max_sessions}) reached")
            print("⚠️  Max sessions reached"); return
        sid = self._generate_id(prompt, repo_url)
        if sid in self.sessions and self.sessions[sid].status != "DONE":
            self.logger.warning(f"Session {sid} already exists with status {self.sessions[sid].status}")
            print("⚠️  Session already running for that prompt + repo"); return
        
        info = SessionInfo(sid, prompt, repo_url, "SPAWNING", time.time())
        self.sessions[sid] = info
        self.logger.info(f"Created session {sid} with status SPAWNING")
        
        pane = self._new_pane(sid)
        self.logger.debug(f"Created pane {pane} for session {sid}")
        
        # Use Gemini in non-interactive mode with direct input/output
        project_path = os.getcwd()
        log_path = self.logs_dir / f"{sid}.log"
        
        # Determine the actual prompt to use
        if not prompt or prompt.strip() == "":
            actual_prompt = "Write a script that runs for a random time between 1-3 minutes, printing hello world every 6 seconds"
        else:
            actual_prompt = prompt
        
        self.logger.info(f"Session {sid} using prompt: {actual_prompt[:100]}...")
        
        # Run Gemini with direct execution and better output capture
        escaped_prompt = actual_prompt.replace("'", "'\"'\"'")
        
        # First, start Gemini interactively
        gemini_start_cmd = f"cd '{project_path}' && gemini 2>&1 | tee -a {log_path}"
        self._run(["tmux", "send-keys", "-t", pane, gemini_start_cmd, "C-m"])
        self.logger.debug(f"Started Gemini interactively in pane {pane}")
        
        # Store the prompt so we can send it after Gemini is ready
        self.session_prompts = getattr(self, 'session_prompts', {})
        self.session_prompts[sid] = actual_prompt
        self.logger.debug(f"Stored prompt for session {sid}, will send when Gemini is ready")
        
        # Keep in SPAWNING status until we detect Gemini is ready
        self.logger.debug(f"Session {sid} created in SPAWNING status, will check for Gemini readiness")
        self._rename_pane(pane, f"SPAWNING‑{sid}")
        print(f"🔥 Started Gemini session {sid} in pane {pane} with prompt: {actual_prompt[:50]}...")

    # ---------- status upkeep ----------
    def _check_gemini_ready(self, sid: str) -> bool:
        """Check if Gemini has loaded and is ready to receive input"""
        pane = self.pane_mapping.get(sid)
        if not pane:
            self.logger.debug(f"Session {sid}: No pane mapping found for readiness check")
            return False
        
        try:
            out = self._run(["tmux", "capture-pane", "-p", "-t", pane]).stdout
            lines = out.split('\n')
            recent_lines = lines[-10:]  # Check more lines for readiness indicators
            
            self.logger.debug(f"Session {sid}: Checking readiness in recent lines: {recent_lines}")
            
            # Look for indicators that Gemini has loaded and is processing
            for line in recent_lines:
                line_clean = line.strip()
                if ("Loaded cached credentials" in line_clean or 
                    "Loading Gemini" in line_clean or
                    line_clean.startswith("Command:") or
                    "Type your message" in line_clean):
                    self.logger.debug(f"Session {sid}: Found Gemini readiness indicator: '{line_clean}'")
                    return True
            
            return False
            
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Session {sid}: Pane capture failed during readiness check: {e}")
            return False

    def _check_requires_user_input(self, sid: str) -> bool:
        """Check if Gemini is waiting for user confirmation/input"""
        pane = self.pane_mapping.get(sid)
        if not pane:
            return False
        
        try:
            out = self._run(["tmux", "capture-pane", "-p", "-t", pane]).stdout
            
            # Check the entire output, not just after "context left)"
            # as the waiting indicator might appear anywhere
            self.logger.debug(f"Session {sid}: Checking full output for user input requirement")
            
            # Look for patterns indicating user input is required
            user_input_indicators = [
                "Apply this change?",
                "Waiting for user confirmation",
                "● 1. Yes, allow once",
                "● 2. Yes, allow always", 
                "4. No (esc)",
                "WriteFile Writing to",
                "⠏ Waiting for",
                "Press any key to continue",
                "Would you like to",
                "Continue? (y/n)",
                "Confirm? (yes/no)"
            ]
            
            for indicator in user_input_indicators:
                if indicator in out:
                    self.logger.debug(f"Session {sid}: Found user input indicator: '{indicator}'")
                    return True
            
            return False
            
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Session {sid}: Pane capture failed during user input check: {e}")
            return False

    def _check_done(self, sid: str):
        pane = self.pane_mapping.get(sid)
        if not pane: 
            self.logger.debug(f"Session {sid}: No pane mapping found, considering done")
            return True
        
        # Check if pane still exists (it might have been killed when stopped)
        try:
            out = self._run(["tmux", "capture-pane", "-p", "-t", pane]).stdout
            
            # Log a snippet of the captured output for debugging
            lines = out.split('\n')
            recent_lines = lines[-10:]  # Check more lines for completion indicators
            self.logger.debug(f"Session {sid}: Recent lines captured: {recent_lines}")
            
            # For interactive Gemini, look for "Type your message" appearing again after response
            # But only after we've had time for Gemini to process and respond
            prompt_sent_time = getattr(self, 'prompt_sent_time', {}).get(sid, 0)
            time_since_prompt = time.time() - prompt_sent_time
            
            # Only check for completion if enough time has passed since we sent the prompt
            # AND we're not waiting for user input
            if time_since_prompt > 10:  # At least 10 seconds for Gemini to process
                # Check if we're NOT in a waiting state
                if not self._check_requires_user_input(sid):
                    for line in recent_lines:
                        stripped_line = line.strip()
                        if "Type your message" in stripped_line:
                            self.logger.debug(f"Session {sid}: Found 'Type your message' after {time_since_prompt:.1f}s, marking as done: '{stripped_line}'")
                            return True
            else:
                self.logger.debug(f"Session {sid}: Only {time_since_prompt:.1f}s since prompt sent, waiting longer before checking completion")
            
            # Also check for shell prompt as fallback (in case Gemini exited)
            # But be more specific to avoid false positives from Gemini UI
            for line in recent_lines:
                stripped_line = line.strip()
                # Check if it's a macOS/Linux shell prompt pattern
                # Look for username@hostname patterns or just % at the end
                if stripped_line and (
                    # Standard shell prompt endings
                    (stripped_line.endswith('%') or stripped_line.endswith('$')) and
                    # Must not be part of Gemini UI
                    'gemini-' not in stripped_line and
                    'sandbox' not in stripped_line and
                    # Either short prompt or contains @ (user@host pattern)
                    (len(stripped_line) < 50 or '@' in stripped_line)
                ):
                    self.logger.debug(f"Session {sid}: Found actual shell prompt, marking as done: '{stripped_line}'")
                    return True
            
            self.logger.debug(f"Session {sid}: No completion indicators found, still running")
            return False
            
        except subprocess.CalledProcessError as e:
            # Pane no longer exists (was killed), consider it done
            self.logger.debug(f"Session {sid}: Pane capture failed (pane killed?): {e}")
            return True

    def update(self):
        for sid, info in list(self.sessions.items()):
            # Handle SPAWNING -> RUNNING transition
            if info.status == "SPAWNING" and self._check_gemini_ready(sid):
                info.status = "RUNNING"
                self.logger.info(f"Session {sid} status changed: SPAWNING -> RUNNING")
                
                # Now send the stored prompt to Gemini
                if hasattr(self, 'session_prompts') and sid in self.session_prompts:
                    pane = self.pane_mapping.get(sid)
                    if pane:
                        prompt = self.session_prompts[sid]
                        # Send the prompt using literal mode to handle special characters
                        self._run(["tmux", "send-keys", "-t", pane, "-l", prompt])
                        # Add a small delay to let Gemini process the pasted text before sending Enter
                        time.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "C-m"])
                        self.logger.debug(f"Sent prompt to Gemini: {prompt[:100]}...")
                        
                        # Mark when we sent the prompt so we can distinguish from initial ready state
                        self.prompt_sent_time = getattr(self, 'prompt_sent_time', {})
                        self.prompt_sent_time[sid] = time.time()
                        
                        self._rename_pane(pane, f"RUNNING‑{sid}")
                        
                        # Clean up the stored prompt
                        del self.session_prompts[sid]
                    
            # Handle RUNNING -> REQUIRES_USER_INPUT transition
            elif info.status == "RUNNING" and self._check_requires_user_input(sid):
                info.status = "REQUIRES_USER_INPUT"
                self.logger.info(f"Session {sid} status changed: RUNNING -> REQUIRES_USER_INPUT")
                pane = self.pane_mapping.get(sid)
                if pane:
                    self._rename_pane(pane, f"INPUT‑{sid}")
                    
            # Handle REQUIRES_USER_INPUT -> RUNNING or DONE transitions
            elif info.status == "REQUIRES_USER_INPUT":
                if self._check_done(sid):
                    info.status = "DONE"; info.end_time = time.time()
                    self.logger.info(f"Session {sid} status changed: REQUIRES_USER_INPUT -> DONE")
                elif not self._check_requires_user_input(sid):
                    # User provided input, back to running
                    info.status = "RUNNING"
                    self.logger.info(f"Session {sid} status changed: REQUIRES_USER_INPUT -> RUNNING")
                    pane = self.pane_mapping.get(sid)
                    if pane:
                        self._rename_pane(pane, f"RUNNING‑{sid}")
                        
            # Handle RUNNING -> DONE transition  
            elif info.status == "RUNNING" and self._check_done(sid):
                info.status = "DONE"; info.end_time = time.time()
                self.logger.info(f"Session {sid} status changed: RUNNING -> DONE")
                
                pane = self.pane_mapping.get(sid)
                if pane:
                    try:
                        # Stop pipe-pane logging first
                        self._run(["tmux", "pipe-pane", "-t", pane], check=False)
                        self.logger.debug(f"Session {sid}: Stopped pipe-pane logging")
                        
                        # For interactive Gemini, send Ctrl+D to exit gracefully, then Ctrl+C as backup
                        self._run(["tmux", "send-keys", "-t", pane, "C-d"], check=False)
                        time.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                        time.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
                        time.sleep(0.5)
                        self.logger.debug(f"Session {sid}: Sent exit commands to pane")
                        
                        # Write completion message to log file
                        log_path = self.logs_dir / f"{sid}.log"
                        with open(log_path, 'a') as f:
                            f.write("✅ Gemini session completed and closed\n")
                        
                        # Rename pane to show completion
                        self._rename_pane(pane, f"DONE‑{sid}")
                        
                        print(f"✅ Session {sid} completed and Gemini CLI closed")
                        self.logger.info(f"Session {sid} cleanup completed")
                        
                    except subprocess.CalledProcessError as e:
                        # Pane no longer exists, clean up mapping
                        self.logger.debug(f"Session {sid}: Cleanup failed, pane may be gone: {e}")
                        if sid in self.pane_mapping:
                            del self.pane_mapping[sid]

    def stop_session(self, sid: str) -> bool:
        """Stop a running session"""
        if sid not in self.sessions:
            self.logger.warning(f"Attempted to stop non-existent session {sid}")
            return False
        
        info = self.sessions[sid]
        if info.status not in ("RUNNING", "REQUIRES_USER_INPUT"):
            self.logger.warning(f"Attempted to stop session {sid} with status {info.status}")
            return False
        
        self.logger.info(f"Stopping session {sid}")
        
        pane = self.pane_mapping.get(sid)
        if pane:
            # Stop pipe-pane logging first to prevent capturing shell artifacts
            self._run(["tmux", "pipe-pane", "-t", pane], check=False)
            self.logger.debug(f"Session {sid}: Stopped pipe-pane logging for manual stop")
            
            # For interactive Gemini, send Ctrl+D to exit gracefully, then Ctrl+C as backup
            self._run(["tmux", "send-keys", "-t", pane, "C-d"], check=False)
            time.sleep(0.5)
            self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
            time.sleep(0.5)
            # Exit shell if needed
            self._run(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
            time.sleep(0.5)
            self.logger.debug(f"Session {sid}: Sent stop and exit commands")
            
            # Write final message directly to log file instead of through tmux
            log_path = self.logs_dir / f"{sid}.log"
            with open(log_path, 'a') as f:
                f.write("🛑 Session stopped by user\n")
            
            # Kill the pane immediately after stopping logging
            time.sleep(0.5)
            pane_id = pane.split(".")[-1]  # Extract pane ID (e.g., '%14')
            self._run(["tmux", "kill-pane", "-t", pane_id], check=False)
            self.logger.debug(f"Session {sid}: Killed pane {pane_id}")
            
            # Clean up pane mapping
            del self.pane_mapping[sid]
            
            # Update status
            info.status = "STOPPED"
            info.end_time = time.time()
            self.logger.info(f"Session {sid} status changed: RUNNING -> STOPPED")
            
            print(f"🛑 Stopped session {sid}")
            return True
        
        self.logger.warning(f"Session {sid}: No pane mapping found for stop")
        return False

    def capture_logs(self):
        """Supplement pipe-pane with periodic capture to ensure we get all output"""
        for sid, info in self.sessions.items():
            if info.status in ("RUNNING", "SPAWNING"):
                pane = self.pane_mapping.get(sid)
                if pane:
                    try:
                        # Capture the entire pane content
                        result = self._run(["tmux", "capture-pane", "-p", "-t", pane, "-S", "-"])
                        if result.returncode == 0:
                            log_path = self.logs_dir / f"{sid}.log"
                            # Append any new content that pipe-pane might have missed
                            # Read existing content first
                            existing_content = ""
                            if log_path.exists():
                                with open(log_path, 'r') as f:
                                    existing_content = f.read()
                            
                            # If captured content is longer and contains existing content, append the new part
                            captured = result.stdout
                            if len(captured) > len(existing_content) and existing_content in captured:
                                # Find the new content
                                idx = captured.find(existing_content) + len(existing_content)
                                new_content = captured[idx:]
                                if new_content.strip():
                                    with open(log_path, 'a') as f:
                                        f.write(new_content)
                            elif not existing_content and captured:
                                # First capture
                                with open(log_path, 'w') as f:
                                    f.write(captured)
                    except subprocess.CalledProcessError:
                        pass  # Pane might have been killed

    def save_status(self):
        self.status_file.write_text(json.dumps({sid: asdict(s) for sid, s in self.sessions.items()}, indent=2))

    async def ticker(self):
        while self.running:
            self.update()
            self.capture_logs()  # Add periodic log capture
            self.save_status()
            await asyncio.sleep(1)  # Reduced to 1 second for more frequent captures

# ---------------------------- UI Layer ---------------------------------------
app = FastAPI()
manager: Optional[TmuxGeminiManager] = None  # will be set in main()

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": [asdict(s) for s in manager.sessions.values()]}

@app.get("/api/sessions/{sid}")
async def session_meta(sid: str):
    s = manager.sessions.get(sid)
    return asdict(s) if s else {"error": "not found"}

@app.post("/api/sessions/{sid}/stop")
async def stop_session(sid: str):
    success = manager.stop_session(sid)
    if success:
        return {"status": "stopped", "session_id": sid}
    else:
        return {"error": "Session not found or not running"}, 404

@app.get("/api/sessions/{sid}/options")
async def get_input_options(sid: str):
    """Get the current input options for a session that requires user input"""
    if sid not in manager.sessions:
        return {"error": "Session not found"}, 404
    
    info = manager.sessions[sid]
    if info.status != "REQUIRES_USER_INPUT":
        return {"error": "Session is not waiting for input"}, 400
    
    pane = manager.pane_mapping.get(sid)
    if not pane:
        return {"error": "Session pane not found"}, 500
    
    # Capture the current pane content to show options
    try:
        result = manager._run(["tmux", "capture-pane", "-p", "-t", pane])
        output = result.stdout
        
        # Extract the last meaningful section (usually the options)
        lines = output.split('\n')
        # Find the last section with options (look for numbered items)
        options_section = []
        in_options = False
        
        for line in reversed(lines):
            if line.strip():
                options_section.insert(0, line)
                # Look for numbered options or confirmation prompts
                if any(pattern in line for pattern in ['● 1.', '● 2.', '1)', '2)', 'Apply this change?', 'Continue?']):
                    in_options = True
                # Stop if we hit a clear boundary
                elif in_options and ('╭' in line or '╰' in line or 'context left)' in line):
                    break
            elif in_options:
                # Empty line in options section
                options_section.insert(0, line)
        
        return {
            "session_id": sid,
            "status": "waiting_for_input", 
            "options": options_section[-20:],  # Last 20 lines to show context
            "full_output": output.split('\n')[-30:]  # Last 30 lines for full context
        }
        
    except subprocess.CalledProcessError as e:
        return {"error": f"Failed to capture options: {e}"}, 500

@app.post("/api/sessions/{sid}/input")
async def send_input(sid: str, response: str):
    """Send input to a session that's waiting for user confirmation"""
    if sid not in manager.sessions:
        return {"error": "Session not found"}, 404
    
    info = manager.sessions[sid]
    if info.status != "REQUIRES_USER_INPUT":
        return {"error": "Session is not waiting for input"}, 400
    
    pane = manager.pane_mapping.get(sid)
    if not pane:
        return {"error": "Session pane not found"}, 500
    
    # Send the user's response
    manager._run(["tmux", "send-keys", "-t", pane, response])
    # Add a small delay to let Gemini process the input before sending Enter
    time.sleep(0.3)
    manager._run(["tmux", "send-keys", "-t", pane, "C-m"])
    manager.logger.info(f"Sent user input '{response}' to session {sid}")
    
    return {"status": "input_sent", "session_id": sid, "response": response}

@app.post("/api/sessions/create")
async def create_session_api(prompt: str, repo_url: Optional[str] = None):
    if not prompt:
        return {"error": "Prompt is required"}, 400
    
    # Generate session ID to return it
    sid = manager._generate_id(prompt, repo_url or manager.default_repo)
    
    # Check if session already exists
    if sid in manager.sessions and manager.sessions[sid].status != "DONE":
        return {"error": "Session already exists for this prompt and repo"}, 409
    
    # Create the session
    manager.create_session(prompt, repo_url)
    
    return {"status": "created", "session_id": sid}

@app.websocket("/ws/{sid}")
async def tail_ws(ws: WebSocket, sid: str):
    import re
    # Regex to remove ANSI escape codes and terminal control sequences
    ansi_escape = re.compile(r'''
        \x1B  # ESC
        (?:   # 7-bit C1 Fe (except CSI)
            [@-Z\\-_]
        |     # or [ for CSI, followed by parameter bytes
            \[
            [0-?]*  # Parameter bytes
            [ -/]*  # Intermediate bytes
            [@-~]   # Final byte
        )
    ''', re.VERBOSE)
    
    # Additional patterns for other terminal sequences
    terminal_sequences = re.compile(r'\x1b\[[0-9;]*[mGKHJF]|\x1b\[[\?0-9]*[hl]|\x07|\r')
    
    def clean_line(line):
        # Remove ANSI escape codes and terminal control sequences first
        line = ansi_escape.sub('', line)
        line = terminal_sequences.sub('', line)
        
        # Remove non-printable characters except newline and tab
        line = ''.join(char for char in line if char.isprintable() or char in '\n\t')
        
        # Clean up any remaining escape sequences
        line = re.sub(r'\[[\?0-9]*[KJhl]', '', line)
        
        stripped = line.strip()
        
        # Only filter out very specific shell artifacts, be much less aggressive
        if stripped in ['%', '%%', '$', '#', '']:
            return ''
        
        # Skip obvious shell prompts but allow other content
        if stripped.endswith('% ') or stripped.endswith('$ '):
            return ''
        
        # Skip the startup command echo
        if stripped.startswith('cd ') and stripped.endswith('&& gemini'):
            return ''
        
        return line.rstrip()  # Remove trailing whitespace but keep the content
    
    await ws.accept()
    log_path = manager.logs_dir / f"{sid}.log"
    
    # Wait for log file to exist
    while not log_path.exists():
        await asyncio.sleep(0.2)
    
    # Open file and follow it like tail -f
    with log_path.open("r") as f:
        # First, send existing content
        content = f.read()
        for line in content.split('\n'):
            cleaned = clean_line(line)
            if cleaned:  # Only send non-empty lines
                try:
                    await ws.send_text(cleaned)
                except Exception:
                    return
        
        # Then continue tailing new content
        try:
            while True:
                line = f.readline()
                if line:
                    cleaned = clean_line(line.rstrip('\n'))
                    if cleaned:  # Only send non-empty lines
                        try:
                            await ws.send_text(cleaned)
                        except Exception:
                            return
                else:
                    await asyncio.sleep(0.1)  # Reduced sleep for faster updates
                    
        except (WebSocketDisconnect, Exception):
            # Handle any WebSocket disconnection or error
            return

@app.get("/")
async def index():
    # Serve the external HTML file
    html_path = Path(__file__).parent / "tmux_gemini_ui.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    else:
        return HTMLResponse("<h1>UI file not found</h1><p>Please ensure tmux_gemini_ui.html exists in the same directory.</p>")

# ---------------------------- Runner ----------------------------------------

def run_uvicorn():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

async def interactive_loop():
    print("Enter prompt (or 'q' to quit):")
    loop = asyncio.get_event_loop()
    while True:
        try:
            p = await loop.run_in_executor(None, sys.stdin.readline)
            if not p: continue
            p = p.strip()
            if p.lower() in {"q", "quit", "exit"}:
                manager.running = False; break
            if p:
                manager.create_session(p)
        except (KeyboardInterrupt, EOFError):
            manager.running = False; break

async def demo_loop():
    """Create demo sessions automatically"""
    # Use the predefined prompt for real Gemini testing
    test_prompt = "Write a script that runs for a random time between 1-3 minutes, printing hello world every 6 seconds"
    
    print("🚀 Creating Gemini session with predefined prompt...")
    print(f"Prompt: {test_prompt}")
    manager.create_session(test_prompt)
    
    print("✅ Gemini session created!")
    print("🌐 Visit http://localhost:8000 to see the UI")
    print("📱 Session will update automatically as Gemini executes the task")
    print("\n⏳ Manager running... Press Ctrl+C to stop")
    
    try:
        while manager.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping manager...")
        manager.running = False

async def main(max_sessions: int = 50, attach: bool = False, ui: bool = False, demo: bool = False):
    global manager
    manager = TmuxGeminiManager(max_sessions=max_sessions)
    manager.setup_main_session()
    asyncio.create_task(manager.ticker())
    if ui:
        threading.Thread(target=run_uvicorn, daemon=True).start()
        print("🌐 UI running on http://localhost:8000")
    if attach:
        os.execvp("tmux", ["tmux", "attach", "-t", manager.main_session])
    
    if demo:
        await demo_loop()
    elif ui and not demo:
        # Just keep the UI server running without interactive prompt
        print("🎯 UI server is running. Use the web interface at http://localhost:8000")
        print("⏹️  Press Ctrl+C to stop")
        try:
            while manager.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping UI server...")
            manager.running = False
    else:
        await interactive_loop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gemini tmux manager + UI")
    parser.add_argument("--max", type=int, default=50, help="max concurrent sessions")
    parser.add_argument("--attach", action="store_true", help="attach to tmux after startup")
    parser.add_argument("--ui", action="store_true", help="start UI server on :8000")
    parser.add_argument("--demo", action="store_true", help="create demo sessions automatically")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.max, args.attach, args.ui, args.demo))
    finally:
        subprocess.run(["tmux", "kill-session", "-t", "gemini_manager"], check=False)
