#!/usr/bin/env python3
"""
Multi-Agent CLI tmux Manager + Lean UI (v5.0) - API & Frontend
=============================================================
FastAPI-based API and frontend for the tmux operations manager.

This module handles:
- REST API endpoints for session management
- WebSocket connections for real-time output streaming
- Web UI serving
- CLI argument processing and main entry point

The actual tmux session management is handled by tmux_operations_manager.py
"""

import asyncio
import subprocess
import time
import json
import sys
import os
import threading
import logging
from typing import Dict, List, Optional, Set
from pathlib import Path
from collections import defaultdict
from pydantic import BaseModel

# Import tmux operations
from tmux_operations_manager import (
    TmuxAgentManager, 
    AgentType, 
    SessionStatus, 
    ReadyIndicatorMode
)

# ---------------------------- UI DEPS ----------------------------------------
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from websockets.exceptions import ConnectionClosedError
import aiofiles

# ---------------------------- WebSocket Management ---------------------------
class WebSocketManager:
    """Manages WebSocket connections for session output streaming"""
    
    def __init__(self):
        self._ws_lock = threading.RLock()
        self._active_websockets: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._websocket_positions: Dict[str, Dict[int, int]] = defaultdict(dict)
        self.logger = logging.getLogger(__name__ + ".websocket")
    
    def register_websocket(self, sid: str, ws: WebSocket):
        """Register WebSocket connection"""
        with self._ws_lock:
            self._active_websockets[sid].add(ws)
            self._websocket_positions[sid][id(ws)] = 0
            self.logger.debug(f"Registered WebSocket for session {sid}")
    
    def unregister_websocket(self, sid: str, ws: WebSocket):
        """Unregister WebSocket connection"""
        with self._ws_lock:
            self._active_websockets[sid].discard(ws)
            ws_id = id(ws)
            if ws_id in self._websocket_positions.get(sid, {}):
                del self._websocket_positions[sid][ws_id]
            self.logger.debug(f"Unregistered WebSocket for session {sid}")
    
    async def broadcast_changes(self, sid: str, changes: str):
        """Broadcast changes to all WebSockets for a session"""
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
    
    def cleanup_session_websockets(self, sid: str):
        """Clean up all WebSocket connections for a session"""
        with self._ws_lock:
            if sid in self._active_websockets:
                del self._active_websockets[sid]
            if sid in self._websocket_positions:
                del self._websocket_positions[sid]

# ---------------------------- FastAPI App ------------------------------------
app = FastAPI()
manager: Optional[TmuxAgentManager] = None
websocket_manager: Optional[WebSocketManager] = None

# ---------------------------- Background Tasks -------------------------------
async def monitor_and_broadcast():
    """Background task to monitor sessions and broadcast changes"""
    while manager and manager.running:
        try:
            # Get session changes from the manager
            session_changes = await manager.update_sessions()
            
            # Broadcast changes to WebSocket clients
            if session_changes and websocket_manager:
                for sid, changes in session_changes.items():
                    if changes:
                        await websocket_manager.broadcast_changes(sid, changes)
            
            # Save status
            manager.save_status()
            
        except Exception as e:
            logging.error(f"Monitor and broadcast error: {e}")
        
        await asyncio.sleep(manager._adaptive_monitor_delay if manager else 2.0)

# ---------------------------- API Endpoints ----------------------------------
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
        count = manager.cleanup_finished_sessions()
        
        # Clean up WebSocket connections for cleaned sessions
        if websocket_manager:
            # We don't have the specific session IDs that were cleaned,
            # but we can clean up any orphaned WebSocket connections
            pass
        
        return {"status": "cleaned", "count": count}
        
    except Exception as e:
        manager.logger.error(f"Failed to clean sessions: {e}")
        return JSONResponse({"error": "Failed to clean sessions"}, status_code=500)

# ---------------------------- WebSocket Endpoints ------------------------
@app.websocket("/ws/{sid}")
async def websocket_endpoint(websocket: WebSocket, sid: str):
    """WebSocket for streaming output"""
    await websocket.accept()
    
    # Register
    if websocket_manager:
        websocket_manager.register_websocket(sid, websocket)
    
    try:
        # Send current content with error handling
        output = manager.get_session_output(sid)
        if output:
            try:
                # Add timeout to prevent hanging on WebSocket send
                await asyncio.wait_for(websocket.send_text(output), timeout=2.0)
            except (asyncio.TimeoutError, ConnectionClosedError, Exception) as e:
                manager.logger.debug(f"Failed to send initial output to WebSocket for session {sid}: {e}")
                return  # Exit early if we can't send initial data
        
        # Keep alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.logger.debug(f"WebSocket disconnected for session {sid}")
    except ConnectionClosedError:
        manager.logger.debug(f"WebSocket connection closed for session {sid}")
    except Exception as e:
        manager.logger.error(f"Unexpected error in WebSocket for session {sid}: {e}")
    finally:
        if websocket_manager:
            websocket_manager.unregister_websocket(sid, websocket)

# ---------------------------- UI Serving ----------------------------------
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
async def main(max_sessions: int = 50, attach: bool = False, ui: bool = False, interactive: bool = True, global_pre_commands: List[str] | None = None, default_agent: AgentType = AgentType.GEMINI):
    global manager, websocket_manager
    
    # Initialize managers
    manager = TmuxAgentManager(max_sessions=max_sessions, global_pre_commands=global_pre_commands, default_agent=default_agent)
    websocket_manager = WebSocketManager()
    
    # Start command queue
    await manager.start_queue()
    
    try:
        manager.setup_main_session()
        
        # Start background monitoring task
        monitor_task = asyncio.create_task(monitor_and_broadcast())
        
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
            
    finally:
        # Stop command queue
        await manager.stop_queue()

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