from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio

from app.database import get_db
from app.models.task import Task, ExecutionHistory
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskStatus
from app.schemas.progress import TaskStepsPlan
from app.services.task_service import TaskService
from app.services.progress_monitor import ProgressMonitor
from app.dependencies import require_authentication, get_user_github_token

router = APIRouter()
task_service = TaskService()


async def execute_task_with_error_handling(task_id: str, github_token: str, websocket_manager=None):
    """Wrapper to handle background task execution with proper error handling"""
    print(f"[TaskExecution] Starting background task execution for: {task_id}")
    print(f"[TaskExecution] WebSocket manager provided: {websocket_manager is not None}")
    
    try:
        print(f"[TaskExecution] Creating progress callback for task: {task_id}")
        
        # Create progress callback that uses WebSocket manager
        async def progress_callback(progress_data):
            print(f"[TaskExecution] Progress callback triggered for task: {task_id}")
            print(f"[TaskExecution] Callback data: {progress_data}")
            
            if websocket_manager:
                print(f"[TaskExecution] Sending progress via WebSocket manager")
                print(f"[TaskExecution] WebSocket manager instance ID: {id(websocket_manager)}")
                print(f"[TaskExecution] WebSocket manager connections: {list(websocket_manager.connections.keys()) if hasattr(websocket_manager, 'connections') else 'No connections attr'}")
                try:
                    await websocket_manager.send_progress_update(task_id, {
                        "type": "progress",
                        **progress_data
                    })
                    print(f"[TaskExecution] Successfully sent WebSocket update")
                except Exception as e:
                    print(f"[TaskExecution] Error sending WebSocket update: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[TaskExecution] No WebSocket manager available")
        
        print(f"[TaskExecution] Calling task_service.execute_task for: {task_id}")
        result = await task_service.execute_task(task_id, github_token, progress_callback=progress_callback)
        print(f"[TaskExecution] Task {task_id} completed successfully with result: {result}")
        return result
        
    except Exception as e:
        print(f"[TaskExecution] ERROR executing task {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Send error update via WebSocket
        if websocket_manager:
            print(f"[TaskExecution] Sending error update via WebSocket")
            try:
                await websocket_manager.send_progress_update(task_id, {
                    "type": "error",
                    "message": str(e)
                })
            except Exception as ws_error:
                print(f"[TaskExecution] Failed to send WebSocket error: {ws_error}")
        
        # Make sure the task status is updated to failed
        try:
            await task_service._update_task_status(task_id, "failed", error_message=str(e))
            await task_service._log_progress(task_id, "failed", f"Background task execution failed: {str(e)}")
        except Exception as update_error:
            print(f"[TaskExecution] Failed to update task status for {task_id}: {update_error}")


@router.post("/execute")
async def execute_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Execute a SimulateDev task for a GitHub repository"""
    
    print(f"[API] Received task execution request from user: {user.github_username}")
    print(f"[API] Task data: issue_url={task_data.issue_url}")
    print(f"[API] Agents: {[{'coding_ide': agent.coding_ide, 'model': agent.model, 'role': agent.role} for agent in task_data.agents]}")
    print(f"[API] Workflow type: {task_data.workflow_type}")
    
    try:
        print(f"[API] Creating task record in database")
        # Create task record with authenticated user
        task_id = await task_service.create_task(
            user_id=user.id,
            issue_url=task_data.issue_url,
            agents_config=[agent.dict() for agent in task_data.agents],
            workflow_type=task_data.workflow_type,
            create_pr=task_data.create_pr,
            options=task_data.options,
            task_prompt=task_data.task_prompt,
            issue_number=task_data.issue_number,
            issue_title=task_data.issue_title,
            github_token=github_token
        )
        
        print(f"[API] Task created with ID: {task_id}")
        
        # Get WebSocket manager singleton
        print(f"[API] Getting WebSocket manager singleton")
        from app.services.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager.get_instance()
        print(f"[API] WebSocket manager obtained: {websocket_manager}")
        print(f"[API] WebSocket manager type: {type(websocket_manager)}")
        print(f"[API] WebSocket manager instance ID: {id(websocket_manager)}")
        print(f"[API] WebSocket manager connections: {len(websocket_manager.connections) if hasattr(websocket_manager, 'connections') else 'N/A'}")
        
        # Start background task execution with user's GitHub token
        print(f"[API] Adding background task to queue")
        background_tasks.add_task(
            execute_task_with_error_handling,
            task_id,
            github_token,
            websocket_manager
        )
        print(f"[API] Background task added to queue successfully")
        
        # Get the created task for response
        print(f"[API] Fetching task from database for response")
        task = db.query(Task).filter(Task.id == task_id).first()
        
        response_data = {
            "task_id": task_id,
            "status": "pending",
            "repo_url": task.repo_url,
            "issue_number": task.issue_number,
            "estimated_duration": task.estimated_duration,
            "created_at": task.created_at
        }
        
        print(f"[API] Returning response: {response_data}")
        return response_data
        
    except ValueError as e:
        print(f"[API] ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.get("/{task_id}")
async def get_task(
    task_id: str, 
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication)
):
    """Get task status and details"""
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Calculate estimated completion
    estimated_completion = None
    if task.started_at and task.status == "running":
        estimated_completion = task.started_at + timedelta(seconds=task.estimated_duration)
    
    # Get current phase from latest log entry
    latest_log = db.query(ExecutionHistory).filter(
        ExecutionHistory.task_id == task_id
    ).order_by(ExecutionHistory.timestamp.desc()).first()
    
    current_phase = latest_log.message if latest_log else None
    
    return TaskResponse(
        task_id=task.id,
        status=TaskStatus(task.status),
        repo_url=task.repo_url,
        issue_number=task.issue_number,
        issue_title=task.issue_title,
        workflow_type=task.workflow_type,
        agents=[agent for agent in task.agents_config],
        progress=task.progress,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        estimated_completion=estimated_completion,
        current_phase=current_phase,
        pr_url=task.pr_url,
        error_message=task.error_message
    )


@router.get("/{task_id}/steps")
async def get_task_steps(
    task_id: str, 
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication)
):
    """Get pre-generated steps plan for a task"""
    
    # Verify task exists and belongs to user
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.steps_plan:
        raise HTTPException(status_code=404, detail="Steps plan not found for this task")
    
    return task.steps_plan


@router.post("/execute-sequential")
async def execute_sequential_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Execute a sequential SimulateDev task: Coder -> Tester -> Coder"""
    
    print(f"[API] Received sequential task execution request from user: {user.github_username}")
    print(f"[API] Task data: issue_url={task_data.issue_url}")
    print(f"[API] Original agents: {[{'coding_ide': agent.coding_ide, 'model': agent.model, 'role': agent.role} for agent in task_data.agents]}")
    
    try:
        print(f"[API] Creating sequential task record in database")
        
        # Convert single agent config to sequential agent config (Coder -> Tester -> Coder)
        # Check if sequential agents are provided in options
        sequential_agents = task_data.options.get('sequential_agents') if task_data.options else None
        sequential_agents_config = await task_service.create_sequential_agents_config(
            [agent.dict() for agent in task_data.agents],
            sequential_agents
        )
        
        print(f"[API] Sequential agents config: {sequential_agents_config}")
        
        # Create task record with sequential agents and workflow type
        task_id = await task_service.create_task(
            user_id=user.id,
            issue_url=task_data.issue_url,
            agents_config=sequential_agents_config,
            workflow_type="sequential",  # Mark as sequential workflow
            create_pr=task_data.create_pr,
            options=task_data.options,
            task_prompt=task_data.task_prompt,
            issue_number=task_data.issue_number,
            issue_title=task_data.issue_title,
            github_token=github_token
        )
        
        print(f"[API] Sequential task created with ID: {task_id}")
        
        # Get WebSocket manager singleton
        print(f"[API] Getting WebSocket manager singleton")
        from app.services.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager.get_instance()
        print(f"[API] WebSocket manager obtained: {websocket_manager}")
        
        # Start background task execution with user's GitHub token
        print(f"[API] Adding sequential background task to queue")
        background_tasks.add_task(
            execute_task_with_error_handling,
            task_id,
            github_token,
            websocket_manager
        )
        print(f"[API] Sequential background task added to queue successfully")
        
        # Get the created task for response
        print(f"[API] Fetching sequential task from database for response")
        task = db.query(Task).filter(Task.id == task_id).first()
        
        response_data = {
            "task_id": task_id,
            "status": "pending",
            "repo_url": task.repo_url,
            "issue_number": task.issue_number,
            "estimated_duration": task.estimated_duration,
            "created_at": task.created_at
        }
        
        print(f"[API] Returning sequential response: {response_data}")
        return response_data
        
    except ValueError as e:
        print(f"[API] ValueError in sequential execution: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] Unexpected error in sequential execution: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create sequential task: {str(e)}")


@router.post("/debug/test-websocket/{task_id}")
async def debug_test_websocket(task_id: str):
    """Debug endpoint to test WebSocket messaging"""
    
    # Get WebSocket manager singleton
    from app.services.websocket_manager import WebSocketManager
    websocket_manager = WebSocketManager.get_instance()
    
    # Send test message
    test_message = {
        "type": "test",
        "message": "This is a test message from the debug endpoint",
        "task_id": task_id,
        "progress": 50,
        "current_phase": "Testing WebSocket connection"
    }
    
    try:
        await websocket_manager.send_progress_update(task_id, test_message)
        
        return {
            "success": True,
            "message": f"Test message sent to task {task_id}",
            "websocket_debug": websocket_manager.debug_connections()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "websocket_debug": websocket_manager.debug_connections()
        }


@router.get("/debug/websocket-status")
async def debug_websocket_status():
    """Debug endpoint to check WebSocket manager status"""
    
    # Get WebSocket manager singleton
    from app.services.websocket_manager import WebSocketManager
    
    debug_info = WebSocketManager.get_instance().debug_connections()
    
    return {
        "websocket_manager": debug_info,
        "message": "WebSocket manager status retrieved successfully"
    }


@router.get("/debug/all")
async def debug_get_all_tasks(
    db: Session = Depends(get_db)
):
    """Debug endpoint to get all tasks and their execution history"""
    
    # Get all tasks
    tasks = db.query(Task).all()
    
    result = []
    for task in tasks:
        # Get execution history for this task
        history = db.query(ExecutionHistory).filter(
            ExecutionHistory.task_id == task.id
        ).order_by(ExecutionHistory.timestamp.desc()).all()
        
        result.append({
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "repo_url": task.repo_url,
            "issue_number": task.issue_number,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_message": task.error_message,
            "execution_history": [
                {
                    "timestamp": log.timestamp,
                    "event_type": log.event_type,
                    "message": log.message
                } for log in history
            ]
        })
    
    return {
        "total_tasks": len(tasks),
        "tasks": result
    }


@router.post("/debug/cancel-all-running")
async def debug_cancel_all_running_tasks(
    db: Session = Depends(get_db)
):
    """Debug endpoint to cancel all running tasks"""
    
    # Find all running tasks
    running_tasks = db.query(Task).filter(Task.status == "running").all()
    
    cancelled_count = 0
    for task in running_tasks:
        try:
            # Try to cancel the background task
            cancelled = await task_service.cancel_task(task.id)
            
            if not cancelled:
                # If task wasn't found in running tasks, update database directly
                task.status = "cancelled"
                task.completed_at = datetime.utcnow()
                task.error_message = "Task cancelled via debug endpoint"
                
            cancelled_count += 1
        except Exception as e:
            print(f"Failed to cancel task {task.id}: {e}")
    
    db.commit()
    
    return {
        "message": f"Cancelled {cancelled_count} running tasks",
        "cancelled_tasks": [task.id for task in running_tasks]
    }



@router.get("/", response_model=dict)
async def get_user_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication),
    page: int = 1,
    per_page: int = 20
):
    """Get user's tasks with pagination"""
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Query user's tasks
    tasks_query = db.query(Task).filter(Task.user_id == user.id)
    total_tasks = tasks_query.count()
    
    tasks = tasks_query.order_by(Task.created_at.desc()).offset(offset).limit(per_page).all()
    
    # Format tasks for response
    formatted_tasks = []
    for task in tasks:
        formatted_tasks.append({
            "task_id": task.id,
            "status": task.status,
            "repo_url": task.repo_url,
            "issue_number": task.issue_number,
            "issue_title": task.issue_title,
            "workflow_type": task.workflow_type,
            "progress": task.progress,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "pr_url": task.pr_url,
            "error_message": task.error_message
        })
    
    return {
        "tasks": formatted_tasks,
        "total": total_tasks,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_tasks + per_page - 1) // per_page
    } 


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str, 
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication)
):
    """Cancel a running task"""
    
    # Check if task exists and belongs to user
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if task is in a cancellable state
    if task.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {task.status}")
    
    try:
        # Try to cancel the background task
        cancelled = await task_service.cancel_task(task_id)
        
        if cancelled:
            return {"message": "Task cancelled successfully", "task_id": task_id}
        else:
            # If task wasn't found in running tasks, update database directly
            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
            task.error_message = "Task cancelled by user"
            db.commit()
            
            return {"message": "Task marked as cancelled", "task_id": task_id}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}") 


@router.post("/test-cli-agent")
async def test_cli_agent_execution(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Test endpoint for CLI agent execution without authentication - FOR TESTING ONLY"""
    
    print("[API] Test CLI agent execution endpoint called")
    
    # Create test task data
    test_task_data = {
        "issue_url": "https://github.com/saharmor/factory-onboard",
        "agents": [
            {
                "coding_ide": "gemini_cli",
                "model": "gemini-pro",
                "role": "Coder"
            }
        ],
        "create_pr": True,
        "workflow_type": "custom",
        "task_prompt": "Create a simple hello world Python script with proper comments",
        "options": {}
    }
    
    try:
        print(f"[API] Creating test task record")
        # Create task without user authentication for testing
        task_id = await task_service.create_task(
            user_id="test-user-id",
            issue_url=test_task_data["issue_url"],
            agents_config=test_task_data["agents"],
            workflow_type=test_task_data["workflow_type"],
            create_pr=test_task_data["create_pr"],
            options=test_task_data.get("options"),
            task_prompt=test_task_data["task_prompt"],
            github_token=None  # No GitHub token for test
        )
        
        print(f"[API] Test task created with ID: {task_id}")
        
        # Get WebSocket manager
        from app.services.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager.get_instance()
        print(f"[API] WebSocket manager obtained for test: {id(websocket_manager)}")
        
        # Start background task execution
        background_tasks.add_task(
            execute_task_with_error_handling,
            task_id,
            None,  # No GitHub token for test
            websocket_manager
        )
        
        print(f"[API] Test task {task_id} queued for execution")
        
        return {
            "message": "Test task execution started",
            "task_id": task_id,
            "agent_type": "gemini_cli"
        }
        
    except Exception as e:
        print(f"[API] Error in test CLI agent execution: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start test task: {str(e)}") 
