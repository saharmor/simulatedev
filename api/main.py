from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from app.config import settings

from app.database import create_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up SimulateDev API...")
    # Create database tables
    create_tables()
    print("Database tables created/verified")
    yield
    # Shutdown
    print("Shutting down SimulateDev API...")

app = FastAPI(
    title="SimulateDev API",
    description="FastAPI backend for SimulateDev GitHub automation",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS properly using settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420"], # allow frontend only as an origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import tasks, github, auth, system, agents
from app.services.websocket_manager import WebSocketManager

# Include routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])

@app.websocket("/ws/tasks/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task progress updates"""
    websocket_manager = WebSocketManager.get_instance()
    print(f"[WebSocket] Using WebSocket manager instance: {id(websocket_manager)}")
    
    try:
        await websocket_manager.connect(websocket, task_id)
        print(f"[WebSocket] Connection established and registered for task: {task_id}")
        
        # Keep connection alive and handle any messages
        while True:
            try:
                # Wait for messages with a reasonable timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                print(f"[WebSocket] Received message from client: {data}")
                
                # Echo back for heartbeat
                await websocket.send_text(f"heartbeat: {data}")
                print(f"[WebSocket] Sent heartbeat response: heartbeat: {data}")
                
            except asyncio.TimeoutError:
                # No message received in 60 seconds, that's fine - just continue
                print(f"[WebSocket] No message received in 60s for task {task_id}, connection still alive")
                continue
                
            except WebSocketDisconnect:
                print(f"[WebSocket] Client disconnected from task {task_id}")
                break
                
            except Exception as e:
                print(f"[WebSocket] Unexpected error for task {task_id}: {e}")
                # Don't break on unexpected errors, try to keep connection alive
                import traceback
                traceback.print_exc()
                continue
                
    except WebSocketDisconnect:
        print(f"[WebSocket] Connection closed during setup for task {task_id}")
    except Exception as e:
        print(f"[WebSocket] Setup error for task {task_id}: {e}")
        import traceback  
        traceback.print_exc()
    finally:
        print(f"[WebSocket] Cleaning up connection for task {task_id}")
        websocket_manager.disconnect(websocket, task_id)

@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML file"""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev_frontend", "index.html")
    return FileResponse(frontend_path)

@app.get("/windows_complete.mp3")
async def serve_completion_sound():
    """Serve the completion sound file"""
    sound_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev_frontend", "windows_complete.mp3")
    if os.path.exists(sound_path):
        return FileResponse(sound_path, media_type="audio/mpeg")
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sound file not found")

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", 
        "version": "1.0.0",
        "simulatedev": "available"
    } 