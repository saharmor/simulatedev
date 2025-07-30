from fastapi import APIRouter, HTTPException
from typing import List
import logging

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


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
    """Health check endpoint"""
    import time
    return {"status": "healthy", "timestamp": time.time()}

 