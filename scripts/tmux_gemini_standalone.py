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
    sleep_duration: Optional[int] = None

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
        self._run(["tmux", "pipe-pane", "-o", "-t", pane_target, f"cat >> {log_path}"], check=False)

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
        
        # Random duration between 1-10 minutes (60-600 seconds)
        total_duration = random.randint(60, 600)
        # Random message interval between 10-30 seconds
        msg_interval = random.randint(10, 30)
        
        # Create a script that prints messages periodically
        mock_script = f"""
echo 'Prompt: {prompt[:50]}...'
echo 'Repo: {repo_url}'
echo 'Session will run for {total_duration} seconds ({total_duration//60} minutes {total_duration%60} seconds)'
echo 'Messages every {msg_interval} seconds'
echo '---'

elapsed=0
while [ $elapsed -lt {total_duration} ]; do
    echo "[$(date '+%H:%M:%S')] I'm here! Progress: $elapsed/{total_duration} seconds"
    sleep {msg_interval}
    elapsed=$((elapsed + {msg_interval}))
done

echo '✅ GEMINI_TASK_COMPLETED'
echo "Session completed after {total_duration} seconds"
        """
        
        # Write script to temp file and execute it
        script_path = f"/tmp/gemini_session_{sid}.sh"
        with open(script_path, 'w') as f:
            f.write(mock_script)
        
        self._run(["tmux", "send-keys", "-t", pane, f"bash {script_path}", "C-m"])
        info.sleep_duration = total_duration; info.status = "RUNNING"
        self._rename_pane(pane, f"RUNNING‑{sid}")
        print(f"🔥 Started {sid} in pane {pane} (duration: {total_duration}s, messages every {msg_interval}s)")

    # ---------- status upkeep ----------
    def _check_done(self, sid: str):
        pane = self.pane_mapping.get(sid)
        if not pane: return True
        
        # Check if pane still exists (it might have been killed when stopped)
        try:
            out = self._run(["tmux", "capture-pane", "-p", "-t", pane]).stdout
            return "GEMINI_TASK_COMPLETED" in out
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
                        self._rename_pane(pane, f"DONE‑{sid}")
                        self._run(["tmux", "send-keys", "-t", pane, "echo '🔔 Done!'", "C-m"], check=False)
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

    def save_status(self):
        self.status_file.write_text(json.dumps({sid: asdict(s) for sid, s in self.sessions.items()}, indent=2))

    async def ticker(self):
        while self.running:
            self.update(); self.save_status(); await asyncio.sleep(3)

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
        # Skip lines that are just shell prompts or tmux commands
        if line.strip().endswith('% ') or line.strip().startswith('bash /tmp/'):
            return ''
        if 'saharmor@' in line and ('scripts %' in line or '% ' in line):
            return ''
        
        # Skip lines that are just prompt artifacts
        stripped = line.strip()
        if stripped in ['%', '%%', '$', '#', '> ', '$ ', '% ', '# ']:
            return ''
        
        # Skip lines that contain only shell prompt patterns
        if re.match(r'^[%$#>\s]*$', stripped):
            return ''
        
        # Skip lines that look like command echoing (bash script execution artifacts)
        if stripped.startswith('bash /tmp/gemini_session_') and stripped.endswith('.sh'):
            return ''
        
        # Skip tmux command output
        if 'tmux' in stripped and ('send-keys' in stripped or 'select-pane' in stripped):
            return ''
        
        # Remove ANSI escape codes
        line = ansi_escape.sub('', line)
        # Remove other terminal sequences
        line = terminal_sequences.sub('', line)
        # Remove non-printable characters except newline
        line = ''.join(char for char in line if char.isprintable() or char == '\n')
        # Clean up any remaining escape sequences
        line = re.sub(r'\[[\?0-9]*[KJhl]', '', line)
        line = line.strip()
        
        # Final check for artifacts after cleaning
        if line in ['%', '%%', '$', '#', '', ' ']:
            return ''
        
        # Skip very short lines that are likely artifacts
        if len(line) <= 2 and line in ['.', '..', '.sh', 'sh']:
            return ''
        
        # Skip lines that are just the script name being typed
        if line.endswith('.sh') and len(line) < 10:
            return ''
            
        return line
    
    await ws.accept(); log_path = manager.logs_dir / f"{sid}.log"
    while not log_path.exists(): await asyncio.sleep(0.2)
    with log_path.open("r") as f:
        # First, send the last 50 lines of existing content
        lines = f.readlines()
        recent_lines = lines[-50:] if len(lines) > 50 else lines
        for line in recent_lines:
            cleaned = clean_line(line)
            if cleaned:  # Only send non-empty lines
                try:
                    await ws.send_text(cleaned)
                except Exception:
                    return
        
        # Then continue tailing new content
        f.seek(0, os.SEEK_END)
        try:
            while True:
                line = f.readline()
                if line:
                    cleaned = clean_line(line)
                    if cleaned:  # Only send non-empty lines
                        try:
                            await ws.send_text(cleaned)
                        except Exception:
                            # WebSocket connection closed, exit gracefully
                            return
                else: 
                    await asyncio.sleep(0.3)
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
    test_prompts = [
        "Create a simple hello world function",
        "Write a Python script to read a CSV file", 
        "Implement a basic REST API with FastAPI",
        "Create a React component for a todo list"
    ]
    
    print("🚀 Creating demo sessions...")
    for i, prompt in enumerate(test_prompts):
        print(f"Creating session {i+1}: {prompt[:30]}...")
        manager.create_session(prompt)
        await asyncio.sleep(2)  # Space out the creation
    
    print("✅ All demo sessions created!")
    print("🌐 Visit http://localhost:8000 to see the UI")
    print("📱 Sessions will update automatically as they complete")
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
