from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.config import settings
from app.database import create_tables
# from app.api import auth, github, agents, tasks, websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    yield
    # Shutdown - cleanup if needed

app = FastAPI(
    title="SimulateDev API",
    description="FastAPI backend for SimulateDev GitHub automation",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import agents, tasks, github, system

# Include routers
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
# TODO: Include other routers once they're created
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(github.router, prefix="/api/github", tags=["GitHub"])
# app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
# app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket"])

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", 
        "version": "1.0.0",
        "simulatedev": "available"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 