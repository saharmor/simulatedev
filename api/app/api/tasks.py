from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio

from app.database import get_db
from app.models.task import Task, ExecutionHistory
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskStatus
from app.services.task_service import TaskService
from app.services.github_service import GitHubService
from app.dependencies import require_authentication, get_user_github_token

router = APIRouter()
task_service = TaskService()
github_service = GitHubService()


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


async def simulate_task_execution(task_id: str, websocket_manager=None):
    """Simulate task execution with realistic progress updates for testing"""
    print(f"[Simulation] Starting simulated task execution for: {task_id}")
    print(f"[Simulation] WebSocket manager provided: {websocket_manager is not None}")
    
    try:
        print(f"[Simulation] Updating task status to running")
        # Update to running status
        await task_service._update_task_status(task_id, "running")
        await task_service._log_progress(task_id, "started", "Task execution started")
        
        # Send initial WebSocket update
        if websocket_manager:
            print(f"[Simulation] Sending initial WebSocket update")
            try:
                await websocket_manager.send_progress_update(task_id, {
                    "type": "progress",
                    "task_id": task_id,
                    "progress": 0,
                    "current_phase": "Task execution started"
                })
                print(f"[Simulation] Initial WebSocket update sent successfully")
            except Exception as e:
                print(f"[Simulation] Failed to send initial WebSocket update: {e}")
        
        # Simulate progress phases with realistic timing
        phases = [
            (5, "🚀 Starting task execution...", 2),
            (15, "📋 Preparing task execution environment...", 1),
            (25, "⚙️ Creating task configuration...", 1),
            (35, "🤖 Initializing SimulateDev workflow...", 2),
            (45, "📥 Cloning repository factory-onboard", 3),
            (60, "🎯 Start coding agent Cursor", 2),
            (70, "✨ Doing magic (aka coding)", 8),  # Longer phase to test 8-second polling
            (85, "🔧 Finished coding, opening a PR", 3),
            (100, "🎉 Done!", 1)
        ]
        
        for i, (progress, phase, duration) in enumerate(phases):
            print(f"[Simulation] Phase {i+1}/{len(phases)}: {progress}% - {phase}")
            
            # Update database
            await task_service._update_task_status(task_id, None, progress=progress)
            await task_service._log_progress(task_id, "progress", phase)
            
            # Send WebSocket update
            if websocket_manager:
                print(f"[Simulation] Sending WebSocket update for phase {i+1}")
                try:
                    await websocket_manager.send_progress_update(task_id, {
                        "type": "progress",
                        "task_id": task_id,
                        "progress": progress,
                        "current_phase": phase
                    })
                    print(f"[Simulation] WebSocket update sent successfully for phase {i+1}")
                except Exception as e:
                    print(f"[Simulation] Failed to send WebSocket update for phase {i+1}: {e}")
            
            print(f"[Simulation] Sleeping for {duration} seconds")
            await asyncio.sleep(duration)
        
        # Complete the task with a fake PR URL
        fake_pr_url = "https://github.com/saharmor/factory-onboard/pull/999"
        print(f"[Simulation] Completing task with PR URL: {fake_pr_url}")
        
        await task_service._update_task_status(task_id, "completed", progress=100, pr_url=fake_pr_url)
        await task_service._log_progress(task_id, "completed", f"Task completed successfully. PR: {fake_pr_url}")
        
        # Send completion WebSocket update
        if websocket_manager:
            print(f"[Simulation] Sending completion WebSocket update")
            try:
                await websocket_manager.send_progress_update(task_id, {
                    "type": "completed",
                    "task_id": task_id,
                    "progress": 100,
                    "current_phase": "🎉 Task completed successfully!",
                    "pr_url": fake_pr_url
                })
                print(f"[Simulation] Completion WebSocket update sent successfully")
            except Exception as e:
                print(f"[Simulation] Failed to send completion WebSocket update: {e}")
        
        print(f"[Simulation] Simulated task {task_id} completed successfully")
        
    except Exception as e:
        print(f"[Simulation] Error in simulated task {task_id}: {e}")
        import traceback
        traceback.print_exc()
        
        await task_service._update_task_status(task_id, "failed", error_message=f"Simulation failed: {str(e)}")
        await task_service._log_progress(task_id, "failed", f"Simulated task failed: {str(e)}")
        
        # Send error WebSocket update
        if websocket_manager:
            print(f"[Simulation] Sending error WebSocket update")
            try:
                await websocket_manager.send_progress_update(task_id, {
                    "type": "error",
                    "task_id": task_id,
                    "message": f"Simulation failed: {str(e)}"
                })
            except Exception as ws_error:
                print(f"[Simulation] Failed to send error WebSocket update: {ws_error}")


@router.post("/test/simulate")
async def test_simulate_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_authentication),
    github_token: str = Depends(get_user_github_token)
):
    """Test endpoint to simulate task execution without actually running SimulateDev"""
    
    print(f"[TestAPI] Creating simulated task for user: {user.github_username}")
    print(f"[TestAPI] Task data: issue_url={task_data.issue_url}")
    
    try:
        print(f"[TestAPI] Creating task record in database")
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
        
        print(f"[TestAPI] Simulated task created with ID: {task_id}")
        
        # Get WebSocket manager singleton
        print(f"[TestAPI] Getting WebSocket manager singleton")
        from app.services.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager.get_instance()
        print(f"[TestAPI] WebSocket manager obtained: {websocket_manager}")
        
        # Start background simulation
        print(f"[TestAPI] Adding simulation task to background queue")
        background_tasks.add_task(simulate_task_execution, task_id, websocket_manager)
        print(f"[TestAPI] Simulation task added successfully")
        
        # Get the created task for response
        print(f"[TestAPI] Fetching task from database for response")
        task = db.query(Task).filter(Task.id == task_id).first()
        
        response_data = {
            "task_id": task_id,
            "status": "pending",
            "repo_url": task.repo_url,
            "issue_number": task.issue_number,
            "estimated_duration": task.estimated_duration,
            "created_at": task.created_at,
            "simulation": True
        }
        
        print(f"[TestAPI] Returning simulation response: {response_data}")
        return response_data
        
    except Exception as e:
        print(f"[TestAPI] Error creating simulated task: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create simulated task: {str(e)}")


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
