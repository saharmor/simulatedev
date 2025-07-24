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
import re
import tempfile
import fcntl
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
        
        # Cursor tracking for efficient WebSocket streaming
        self._cursors: Dict[str, int] = {}  # session_id → byte offset in log
        
        # Thread safety for JSON operations
        self._json_save_lock = threading.Lock()
        
        # Log rotation settings (guardrails for runaway size)
        self.max_log_size = 20_000_000  # 20MB per log file
        self.max_backup_count = 3
        
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
    
    def _rotate_log_if_needed(self, session_id: str):
        """Rotate log file if it exceeds max size (guardrail for runaway size)"""
        log_path = self.logs_dir / f"{session_id}.log"
        
        if not log_path.exists():
            return
            
        # Check file size
        if log_path.stat().st_size > self.max_log_size:
            self.logger.info(f"Rotating log for session {session_id} (size: {log_path.stat().st_size} bytes)")
            
            # Rotate existing backup files
            for i in range(self.max_backup_count - 1, 0, -1):
                old_backup = self.logs_dir / f"{session_id}.log.{i}"
                new_backup = self.logs_dir / f"{session_id}.log.{i + 1}"
                if old_backup.exists():
                    if new_backup.exists():
                        new_backup.unlink()
                    old_backup.rename(new_backup)
            
            # Move current log to .1
            backup_path = self.logs_dir / f"{session_id}.log.1"
            if backup_path.exists():
                backup_path.unlink()
            log_path.rename(backup_path)
            
            # Reset cursor since we rotated the file
            self._cursors[session_id] = 0
            
            self.logger.info(f"Log rotated for session {session_id}")
            return True
        return False

    def _clean_terminal_output(self, text: str) -> str:
        """Clean terminal output by removing ANSI escape codes and control sequences"""
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
        
        # Remove ANSI escape codes and terminal control sequences
        text = ansi_escape.sub('', text)
        text = terminal_sequences.sub('', text)
        
        # Remove non-printable characters except newline, tab, and box-drawing characters
        text = ''.join(char for char in text if char.isprintable() or char in '\n\t' or ord(char) >= 0x2500)
        
        # Clean up any remaining escape sequences
        text = re.sub(r'\[[\?0-9]*[KJhl]', '', text)
        
        return text

    def _save_session_output_to_json(self, session_id: str):
        """Thread-safe saving of completed session output to JSON file for efficient loading"""
        # Use thread lock to prevent concurrent access
        with self._json_save_lock:
            json_path = self.logs_dir / f"{session_id}_output.json"
            
            # Skip if already saved to avoid duplicate work
            if json_path.exists():
                self.logger.debug(f"JSON output for session {session_id} already exists, skipping")
                return
            
            try:
                # Capture final output directly from tmux pane (cleaner than reading full log)
                final_output = self._capture_final_session_output(session_id)
                
                # Get session info
                session_info = self.sessions.get(session_id)
                
                # Create JSON structure
                output_data = {
                    "session_id": session_id,
                    "status": "DONE",
                    "prompt": session_info.prompt if session_info else "",
                    "repo_url": session_info.repo_url if session_info else "",
                    "start_time": session_info.start_time if session_info else None,
                    "end_time": session_info.end_time if session_info else None,
                    "output": final_output,
                    "saved_at": time.time()
                }
                
                # Atomic write: write to temp file first, then rename
                temp_path = json_path.with_suffix('.tmp')
                try:
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        # Add file lock during write
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        json.dump(output_data, f, indent=2, ensure_ascii=False)
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    
                    # Atomic rename - this is the critical atomic operation
                    temp_path.rename(json_path)
                    self.logger.info(f"Saved session {session_id} output to JSON: {json_path}")
                    
                except Exception as e:
                    # Clean up temp file if write failed
                    if temp_path.exists():
                        temp_path.unlink()
                    raise e
                    
            except Exception as e:
                self.logger.error(f"Failed to save session {session_id} output to JSON: {e}")

    def _capture_final_session_output(self, session_id: str) -> str:
        """Capture the final, clean output from a session's tmux pane"""
        pane = self.pane_mapping.get(session_id)
        if not pane:
            # Fallback to reading log file if pane is gone
            return self._read_session_log_fallback(session_id)
        
        try:
            # Capture the current pane content (this is the final state)
            result = self._run(["tmux", "capture-pane", "-p", "-t", pane])
            raw_output = result.stdout
            
            # Clean the output to remove terminal sequences
            cleaned_output = self._clean_terminal_output(raw_output)
            
            return cleaned_output
            
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Failed to capture pane output for session {session_id}: {e}")
            # Fallback to reading log file
            return self._read_session_log_fallback(session_id)
    
    def _read_session_log_fallback(self, session_id: str) -> str:
        """Fallback method to read session output from log file"""
        log_path = self.logs_dir / f"{session_id}.log"
        
        if not log_path.exists():
            self.logger.warning(f"Log file for session {session_id} not found")
            return ""
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_output = f.read()
            
            # Clean the output
            cleaned_output = self._clean_terminal_output(raw_output)
            return cleaned_output
            
        except Exception as e:
            self.logger.error(f"Failed to read log file for session {session_id}: {e}")
            return ""

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
        # Use pipe-pane -o to attach pipe only the first time (append-once pattern)
        self._run([
            "tmux", "pipe-pane",
            "-o",                       # <= attach pipe only the first time
            "-t", pane_target,
            f"exec cat >> '{log_path}'" # append everything the pane prints
        ], check=False)

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
        
        # Set up pipe-pane logging (append-once pattern)
        self._pipe_log(pane, sid)
        self.logger.debug(f"Set up pipe-pane logging for session {sid}")
        
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
        # Check for log rotation on active sessions
        for sid in list(self.sessions.keys()):
            if self.sessions[sid].status in ("RUNNING", "SPAWNING", "REQUIRES_USER_INPUT"):
                self._rotate_log_if_needed(sid)
        
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
                    
                    # Perform cleanup for sessions that go directly from USER_INPUT to DONE
                    pane = self.pane_mapping.get(sid)
                    if pane:
                        try:
                            # Save session output to JSON BEFORE closing - captures final clean state
                            self._save_session_output_to_json(sid)
                            
                            # Stop pipe-pane logging first
                            self._run(["tmux", "pipe-pane", "-t", pane], check=False)
                            self.logger.debug(f"Session {sid}: Stopped pipe-pane logging")
                            
                            # For interactive Gemini, send two Ctrl+C to exit Gemini CLI, then exit shell
                            self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
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
                        # Save session output to JSON BEFORE closing - captures final clean state
                        self._save_session_output_to_json(sid)
                        
                        # Stop pipe-pane logging first
                        self._run(["tmux", "pipe-pane", "-t", pane], check=False)
                        self.logger.debug(f"Session {sid}: Stopped pipe-pane logging")
                        
                        # For interactive Gemini, send two Ctrl+C to exit Gemini CLI, then exit shell
                        self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
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
            
            # For interactive Gemini, send two Ctrl+C to exit Gemini CLI, then exit shell
            self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
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



    def save_status(self):
        self.status_file.write_text(json.dumps({sid: asdict(s) for sid, s in self.sessions.items()}, indent=2))

    async def ticker(self):
        while self.running:
            self.update()
            self.save_status()
            await asyncio.sleep(5)  # Sample Gemini sessions every 5 seconds

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

@app.get("/api/sessions/{sid}/output")
async def get_session_output(sid: str):
    """Get saved output for a completed session"""
    if sid not in manager.sessions:
        return {"error": "Session not found"}, 404
    
    session_info = manager.sessions[sid]
    if session_info.status != "DONE":
        return {"error": "Session is not completed yet"}, 400
    
    json_path = manager.logs_dir / f"{sid}_output.json"
    if not json_path.exists():
        return {"error": "Output file not found"}, 404
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
        return output_data
    except Exception as e:
        manager.logger.error(f"Failed to read output for session {sid}: {e}")
        return {"error": "Failed to read output file"}, 500

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

@app.post("/api/sessions/clean")
async def clean_previous_sessions():
    """Clean all DONE and STOPPED sessions"""
    try:
        cleaned_sessions = []
        sessions_to_remove = []
        
        for sid, info in manager.sessions.items():
            if info.status in ("DONE", "STOPPED"):
                sessions_to_remove.append(sid)
                cleaned_sessions.append(sid)
                
                # Clean up the pane mapping if it exists
                if sid in manager.pane_mapping:
                    del manager.pane_mapping[sid]
                
                # Remove log files
                log_path = manager.logs_dir / f"{sid}.log"
                if log_path.exists():
                    try:
                        log_path.unlink()
                        manager.logger.info(f"Removed log file for session {sid}")
                    except OSError as e:
                        manager.logger.warning(f"Failed to remove log file for session {sid}: {e}")
                
                # Remove any rotated log files
                for i in range(1, manager.max_backup_count + 1):
                    backup_path = manager.logs_dir / f"{sid}.log.{i}"
                    if backup_path.exists():
                        try:
                            backup_path.unlink()
                            manager.logger.info(f"Removed backup log file {backup_path}")
                        except OSError as e:
                            manager.logger.warning(f"Failed to remove backup log file {backup_path}: {e}")
        
        # Remove sessions from manager
        for sid in sessions_to_remove:
            del manager.sessions[sid]
            # Clean up cursor tracking
            if sid in manager._cursors:
                del manager._cursors[sid]
        
        manager.logger.info(f"Cleaned {len(cleaned_sessions)} previous sessions: {cleaned_sessions}")
        
        return {
            "status": "success", 
            "cleaned_sessions": cleaned_sessions,
            "count": len(cleaned_sessions)
        }
        
    except Exception as e:
        manager.logger.error(f"Error cleaning sessions: {e}")
        return {"error": f"Failed to clean sessions: {str(e)}"}, 500

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
        
        # Remove non-printable characters except newline, tab, and box-drawing characters
        line = ''.join(char for char in line if char.isprintable() or char in '\n\t' or ord(char) >= 0x2500)
        
        # Clean up any remaining escape sequences
        line = re.sub(r'\[[\?0-9]*[KJhl]', '', line)
        
        stripped = line.strip()
        
        # Only filter out very specific shell artifacts, be much less aggressive
        if stripped in ['%', '%%', '$', '#']:
            return ''
        
        # Skip obvious shell prompts but allow other content
        if stripped.endswith('% ') or stripped.endswith('$ '):
            return ''
        
        # Skip the startup command echo but preserve Gemini content
        if stripped.startswith('cd ') and stripped.endswith('&& gemini') and 'Type your message' not in stripped:
            return ''
        
        # Preserve Gemini UI elements (box drawing, prompts, etc.)
        if any(indicator in stripped for indicator in ['Type your message', '│', '╭', '╰', '✦', 'gemini-', 'context left']):
            return line.rstrip()
        
        # Don't filter empty lines as they provide structure
        if not stripped:
            return line
        
        return line.rstrip()  # Remove trailing whitespace but keep the content
    
    await ws.accept()
    log_path = manager.logs_dir / f"{sid}.log"
    
    # Wait for log file to exist
    while not log_path.exists():
        await asyncio.sleep(0.2)
    
    # For DONE sessions, reset cursor to show full log from beginning
    session_info = manager.sessions.get(sid)
    if session_info and session_info.status == "DONE":
        manager._cursors[sid] = 0
        manager.logger.debug(f"Reset cursor to 0 for DONE session {sid}")
    
    # Efficient cursor-based streaming: only send bytes we haven't sent yet
    try:
        with log_path.open("rb") as f:
            # Skip what this client already received, but handle log rotation
            cursor_pos = manager._cursors.get(sid, 0)
            
            # If cursor is beyond file size, log was likely rotated - start from beginning
            try:
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                if cursor_pos > file_size:
                    manager.logger.debug(f"Log rotation detected for {sid}, resetting cursor")
                    cursor_pos = 0
                    manager._cursors[sid] = 0
                
                f.seek(cursor_pos)
            except OSError:
                # File might not exist yet or other IO error
                cursor_pos = 0
                f.seek(0)
            
            while True:
                chunk = f.read(4096)
                if chunk:
                    # Update cursor position
                    manager._cursors[sid] = f.tell()
                    
                    # Decode and clean the chunk
                    try:
                        text = chunk.decode('utf-8', errors='ignore')
                    except UnicodeDecodeError as decode_error:
                        # Log actual decode error but continue
                        manager.logger.debug(f"Unicode decode error in WebSocket for {sid}: {decode_error}")
                        continue
                    
                    # Process line by line for cleaning and send via WebSocket
                    try:
                        for line in text.split('\n'):
                            if line:  # Skip empty lines
                                cleaned = clean_line(line)
                                if cleaned:  # Only send non-empty cleaned lines
                                    await ws.send_text(cleaned)
                    except WebSocketDisconnect as ws_error:
                        # WebSocket disconnected, exit gracefully
                        manager.logger.debug(f"WebSocket disconnected for {sid}: {ws_error}")
                        return
                    except Exception as send_error:
                        # Other WebSocket send errors, also exit
                        manager.logger.debug(f"WebSocket send error for {sid}: {send_error}")
                        return
                else:
                    await asyncio.sleep(0.1)  # No new data, wait briefly
                    
    except WebSocketDisconnect as e:
        # Handle WebSocket disconnection
        manager.logger.debug(f"WebSocket disconnected for {sid}: {e}")
        return
    except Exception as e:
        # Handle other unexpected errors
        manager.logger.error(f"Unexpected error in WebSocket handler for {sid}: {e}")
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
