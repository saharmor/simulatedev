from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import aiofiles
import asyncio
import json
from pathlib import Path
from websockets.exceptions import ConnectionClosedError

from .multi_agent_manager import MultiAgentManager
from .enums import SessionStatus, AgentType

# Global manager instance
manager: Optional[MultiAgentManager] = None

# Create FastAPI app
app = FastAPI()

# Request models
class CreateSessionRequest(BaseModel):
    prompt: str
    repo_url: Optional[str] = None
    agent_type: str = AgentType.GEMINI.value
    yolo_mode: bool = False

# API Endpoints
@app.get("/api/sessions")
async def list_sessions():
    """List all sessions"""
    return {"sessions": manager.get_sessions()}

@app.get("/api/sessions/{sid}")
async def get_session(sid: str):
    """Get session details"""
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
    json_path = manager.session_manager.logs_dir / f"{sid}_output.json"
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

@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """Create new session"""
    if not request.prompt:
        return JSONResponse({"error": "Prompt required"}, status_code=400)
    
    # Convert string agent_type to enum
    try:
        agent_type_enum = AgentType(request.agent_type)
    except ValueError:
        return JSONResponse({"error": f"Invalid agent type: {request.agent_type}"}, status_code=400)
    
    # Create session
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
        lines = output.split('\n')
        return {
            "session_id": sid,
            "status": session["status"],
            "full_output": lines,
            "context": lines[-20:] if len(lines) > 20 else lines
        }
    
    return JSONResponse({"error": "No context available"}, status_code=404)

@app.post("/api/sessions/clean")
async def clean_previous_sessions():
    """Clean up all previous sessions"""
    try:
        sessions = manager.get_sessions()
        cleaned = 0
        
        for session in sessions:
            if session["status"] in ("DONE", "STOPPED", "PREMATURE_FINISH"):
                sid = session["session_id"]
                # Clean up session
                manager.session_manager.cleanup_session(sid)
                manager.stream_manager.cleanup_session_websockets(sid)
                
                # Kill pane if exists
                pane = manager.session_manager.get_pane(sid)
                if pane:
                    manager.tmux_ops.kill_pane(pane)
                
                cleaned += 1
        
        manager.logger.info(f"Cleaned {cleaned} sessions")
        return {"status": "cleaned", "count": cleaned}
        
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
        # Send current content with error handling
        output = manager.get_session_output(sid)
        if output:
            try:
                # Add timeout to prevent hanging on WebSocket send
                await asyncio.wait_for(websocket.send_text(output), timeout=2.0)
            except (asyncio.TimeoutError, ConnectionClosedError, Exception) as e:
                print(f"Failed to send initial output to WebSocket for session {sid}: {e}")
                return  # Exit early if we can't send initial data
        
        # Keep alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {sid}")
    except ConnectionClosedError:
        print(f"WebSocket connection closed for session {sid}")
    except Exception as e:
        print(f"Unexpected error in WebSocket for session {sid}: {e}")
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

def set_manager(mgr: MultiAgentManager):
    """Set the global manager instance"""
    global manager
    manager = mgr 