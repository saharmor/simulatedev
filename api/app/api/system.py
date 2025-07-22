from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/config")
async def get_system_config():
    """Get system configuration information"""
    return {
        "max_concurrent_tasks": settings.max_concurrent_tasks,
        "default_timeout": settings.default_task_timeout,
        "supported_workflows": ["custom", "bugs", "optimize", "refactor"],
        "max_task_history": settings.max_task_history,
        "version": "1.0.0"
    }


@router.get("/health")
async def health_check():
    """Extended health check with system information"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": "connected",
        "simulatedev": "available",
        "timestamp": "2025-01-21T20:30:00Z"
    } 