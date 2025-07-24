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
    status: str  # SPAWNING, RUNNING, DONE, STOPPED
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
        if sum(1 for s in self.sessions.values() if s.status in ("SPAWNING", "RUNNING")) >= self.max_sessions:
            print("⚠️  Max sessions reached"); return
        sid = self._generate_id(prompt, repo_url)
        if sid in self.sessions and self.sessions[sid].status != "DONE":
            print("⚠️  Session already running for that prompt + repo"); return
        info = SessionInfo(sid, prompt, repo_url, "SPAWNING", time.time())
        self.sessions[sid] = info
        pane = self._new_pane(sid)
        self._pipe_log(pane, sid)
        
        # Start the real Gemini CLI
        project_path = os.getcwd()
        startup_cmd = f"cd '{project_path}' && gemini"
        
        # Send the startup command
        self._run(["tmux", "send-keys", "-t", pane, startup_cmd, "C-m"])
        
        # Give Gemini time to start up and become ready
        time.sleep(3)
        
        # Wait for Gemini to be ready (look for "Type your message" indicator)
        max_wait = 10  # seconds
        wait_count = 0
        ready = False
        
        while wait_count < max_wait:
            try:
                output = self._run(["tmux", "capture-pane", "-p", "-t", pane]).stdout
                if "Type your message" in output:
                    ready = True
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(1)
            wait_count += 1
        
        if not ready:
            print(f"⚠️  Gemini failed to start properly for session {sid}")
            info.status = "DONE"
            info.end_time = time.time()
            return
        
        # Enable YOLO mode with Ctrl+Y (for autonomous execution)
        self._run(["tmux", "send-keys", "-t", pane, "C-y"])
        time.sleep(2)  # Increased delay to ensure YOLO mode is activated
        
        # Use the predefined prompt if none provided, otherwise use the custom prompt
        if not prompt or prompt.strip() == "":
            actual_prompt = "Write a script that runs for a random time between 1-3 minutes, printing hello world every 6 seconds"
        else:
            actual_prompt = prompt
        
        # Send the prompt to Gemini
        self._run(["tmux", "send-keys", "-t", pane, actual_prompt, "C-m"])
        time.sleep(1)  # Add delay after sending prompt
        
        info.status = "RUNNING"
        self._rename_pane(pane, f"RUNNING‑{sid}")
        print(f"🔥 Started real Gemini session {sid} in pane {pane} with prompt: {actual_prompt[:50]}...")

    # ---------- status upkeep ----------
    def _check_done(self, sid: str):
        pane = self.pane_mapping.get(sid)
        if not pane: return True
        
        # Check if pane still exists (it might have been killed when stopped)
        try:
            out = self._run(["tmux", "capture-pane", "-p", "-t", pane]).stdout
            
            # The most reliable indicator: Gemini returns to "Type your message" prompt
            # after completing a task, indicating it's ready for the next input
            lines = out.split('\n')
            recent_lines = lines[-10:]  # Check last 10 lines for the prompt
            
            # Look for the "Type your message" prompt in recent output
            has_type_message = any("Type your message" in line for line in recent_lines)
            
            if has_type_message:
                # Make sure this isn't the initial prompt by checking if we have
                # substantial content before it (indicating work was done)
                if len(out) > 1000:  # Arbitrary threshold for "substantial content"
                    return True
            
            # Fallback: Check if Gemini process has exited (back to shell prompt)
            for line in recent_lines:
                if line.strip().endswith('% ') or line.strip().endswith('$ '):
                    # Back to shell prompt, Gemini has exited
                    return True
            
            return False
            
        except subprocess.CalledProcessError:
            # Pane no longer exists (was killed), consider it done
            return True

    def update(self):
        for sid, info in list(self.sessions.items()):
            if info.status == "RUNNING" and self._check_done(sid):
                info.status = "DONE"; info.end_time = time.time()
                pane = self.pane_mapping.get(sid)
                if pane:
                    try:
                        # Stop pipe-pane logging first
                        self._run(["tmux", "pipe-pane", "-t", pane], check=False)
                        
                        # Send Ctrl+C to stop any running processes, then exit Gemini
                        self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
                        time.sleep(0.5)
                        self._run(["tmux", "send-keys", "-t", pane, "exit", "C-m"], check=False)
                        time.sleep(0.5)
                        
                        # Write completion message to log file
                        log_path = self.logs_dir / f"{sid}.log"
                        with open(log_path, 'a') as f:
                            f.write("✅ Gemini session completed and closed\n")
                        
                        # Rename pane to show completion
                        self._rename_pane(pane, f"DONE‑{sid}")
                        
                        print(f"✅ Session {sid} completed and Gemini CLI closed")
                        
                    except subprocess.CalledProcessError:
                        # Pane no longer exists, clean up mapping
                        if sid in self.pane_mapping:
                            del self.pane_mapping[sid]

    def stop_session(self, sid: str) -> bool:
        """Stop a running session"""
        if sid not in self.sessions:
            return False
        
        info = self.sessions[sid]
        if info.status != "RUNNING":
            return False
        
        pane = self.pane_mapping.get(sid)
        if pane:
            # Stop pipe-pane logging first to prevent capturing shell artifacts
            self._run(["tmux", "pipe-pane", "-t", pane], check=False)
            
            # Send Ctrl+C to stop the running script
            self._run(["tmux", "send-keys", "-t", pane, "C-c"], check=False)
            time.sleep(0.5)
            
            # Write final message directly to log file instead of through tmux
            log_path = self.logs_dir / f"{sid}.log"
            with open(log_path, 'a') as f:
                f.write("🛑 Session stopped by user\n")
            
            # Kill the pane immediately after stopping logging
            time.sleep(0.5)
            pane_id = pane.split(".")[-1]  # Extract pane ID (e.g., '%14')
            self._run(["tmux", "kill-pane", "-t", pane_id], check=False)
            
            # Clean up pane mapping
            del self.pane_mapping[sid]
            
            # Update status
            info.status = "STOPPED"
            info.end_time = time.time()
            
            print(f"🛑 Stopped session {sid}")
            return True
        
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
