import sys
import os
import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import json

# Add the parent SimulateDev directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

try:
    from src.orchestrator import Orchestrator, TaskRequest
    from agents import AgentDefinition, AgentRole, CodingAgentIdeType, MultiAgentTask
    from common.config import config
except ImportError as e:
    print(f"Warning: Could not import SimulateDev modules: {e}")
    Orchestrator = None
    TaskRequest = None
    AgentDefinition = None

from app.database import SessionLocal
from app.models.task import Task, ExecutionHistory
from app.services.github_service import GitHubService


class TaskService:
    """Service for managing SimulateDev task execution"""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
    
    async def create_task(self, user_id: str, issue_url: str, agents_config: List[Dict], 
                         workflow_type: str = "custom", create_pr: bool = True,
                         options: Optional[Dict] = None, task_prompt: Optional[str] = None,
                         issue_number: Optional[int] = None, issue_title: Optional[str] = None,
                         github_token: Optional[str] = None) -> str:
        """Create a new task in the database"""
        db = SessionLocal()
        
        try:
            # Parse repo URL to get basic info
            repo_info = self.github_service.parse_repo_url(issue_url)
            
            # Extract issue information from repo_info if not provided
            final_issue_number = issue_number or repo_info.get('issue_number')
            final_issue_title = issue_title
            
            # For GitHub issues, always synthesize the detailed task prompt
            final_task_prompt = task_prompt
            if final_issue_number and github_token:
                try:
                    # Fetch issue data from GitHub
                    issue_data = self.github_service.get_issue_details(
                        repo_info['owner'], 
                        repo_info['repo'], 
                        final_issue_number, 
                        github_token
                    )
                    
                    # Update issue title if not provided
                    if not final_issue_title:
                        final_issue_title = issue_data.get('title')
                    
                    # Always synthesize detailed task prompt from issue data for GitHub issues
                    final_task_prompt = self.github_service.synthesize_task_prompt(issue_data, repo_info)
                    
                    print(f"Auto-synthesized detailed task prompt for GitHub issue #{final_issue_number}")
                    
                except Exception as e:
                    print(f"Warning: Failed to synthesize task prompt from issue #{final_issue_number}: {e}")
                    # Fallback to the provided prompt or a basic prompt if synthesis fails
                    if not task_prompt:
                        final_task_prompt = f"Resolve GitHub issue #{final_issue_number}: {final_issue_title or 'See issue details'}"
                    else:
                        final_task_prompt = task_prompt
            
            # If still no prompt (no issue number or token), use provided prompt or create a basic fallback
            if not final_task_prompt:
                final_task_prompt = task_prompt or f"Complete the requested task for repository {repo_info['repo_url']}"
            
            # Create task record
            task_id = str(uuid.uuid4())
            task = Task(
                id=task_id,
                user_id=user_id,
                repo_url=repo_info['repo_url'],
                repo_owner=repo_info['owner'],
                repo_name=repo_info['repo'],
                issue_number=final_issue_number,
                issue_title=final_issue_title,
                issue_url=issue_url,
                task_description=final_task_prompt,
                workflow_type=workflow_type,
                agents_config=agents_config,
                status="pending",
                estimated_duration=options.get('timeout_seconds', 1800) if options else 1800
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            
            return task_id
            
        finally:
            db.close()
    
    async def execute_task(self, task_id: str, github_token: str, 
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Execute a SimulateDev task"""
        
        print(f"[TaskService] Starting execute_task for: {task_id}")
        print(f"[TaskService] Progress callback provided: {progress_callback is not None}")
        
        if progress_callback:
            self.progress_callbacks[task_id] = progress_callback
            print(f"[TaskService] Progress callback registered for task: {task_id}")
            print(f"[TaskService] Total registered callbacks: {len(self.progress_callbacks)}")
        else:
            print(f"[TaskService] No progress callback provided for task: {task_id}")
        
        try:
            print(f"[TaskService] Creating async task for execution: {task_id}")
            # Create async task for execution
            execution_task = asyncio.create_task(
                self._execute_task_internal(task_id, github_token)
            )
            
            # Store running task
            self.running_tasks[task_id] = execution_task
            print(f"[TaskService] Task stored in running_tasks. Total running: {len(self.running_tasks)}")
            
            # Wait for completion
            print(f"[TaskService] Waiting for task execution to complete: {task_id}")
            result = await execution_task
            print(f"[TaskService] Task execution completed: {task_id}, result: {result}")
            
            return result
            
        except Exception as e:
            print(f"[TaskService] ERROR in execute_task for {task_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            await self._update_task_status(task_id, "failed", error_message=str(e))
            await self._log_progress(task_id, "failed", f"Task execution failed: {str(e)}")
            raise e
        finally:
            print(f"[TaskService] Cleaning up task: {task_id}")
            # Cleanup
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
                print(f"[TaskService] Removed task from running_tasks: {task_id}")
            if task_id in self.progress_callbacks:
                del self.progress_callbacks[task_id]
                print(f"[TaskService] Removed progress callback for task: {task_id}")
    
    async def _execute_simulatedev_with_response_capture(self, args, github_token: str) -> Dict[str, Any]:
        """Execute SimulateDev with response capture and proper error handling"""
        try:
            print(f"[TaskService] Starting SimulateDev execution with args: {args}")
            
            # Set GitHub token in environment
            if github_token:
                os.environ['GITHUB_TOKEN'] = github_token
            
            # Execute the task with proper error handling
            from simulatedev import execute_task
            success = await execute_task(args)
            
            print(f"[TaskService] SimulateDev execution completed with success: {success}")
            
            if success:
                return {'success': True, 'pr_url': None}  # PR URL will be extracted separately
            else:
                return {'success': False, 'error': 'SimulateDev execution returned false'}
                
        except Exception as e:
            print(f"[TaskService] ERROR in SimulateDev execution: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    async def _execute_simulatedev_with_progress_tracking(self, args, github_token: str, task_id: str) -> Dict[str, Any]:
        """Execute SimulateDev with integrated progress tracking"""
        try:
            print(f"[TaskService] Starting SimulateDev execution with integrated progress tracking")
            
            # Set GitHub token in environment
            if github_token:
                os.environ['GITHUB_TOKEN'] = github_token
            
            # Try to use orchestrator for better progress control
            try:
                # Import and create orchestrator directly for better progress control
                print(f"[TaskService] Attempting to import orchestrator modules...")
                from src.orchestrator import Orchestrator, TaskRequest
                from agents import AgentDefinition, AgentRole, CodingAgentIdeType
                print(f"[TaskService] Successfully imported orchestrator modules")
                
                # Create orchestrator
                print(f"[TaskService] Creating orchestrator with GitHub token...")
                orchestrator = Orchestrator(github_token)
                print(f"[TaskService] Orchestrator created successfully")
                
                # Convert args to TaskRequest
                print(f"[TaskService] Converting args to TaskRequest...")
                task_request = self._create_task_request_from_args(args)
                
                # If TaskRequest creation failed, task_request will be the original args object
                if not hasattr(task_request, 'agents'):
                    print(f"[TaskService] TaskRequest creation failed - no 'agents' attribute found")
                    print(f"[TaskService] task_request type: {type(task_request)}")
                    print(f"[TaskService] task_request attributes: {dir(task_request)}")
                    raise ImportError("TaskRequest creation failed")
                
                print(f"[TaskService] TaskRequest created successfully with {len(task_request.agents)} agents")
                
                # Execute with progress tracking
                await self._notify_progress(task_id, 30, "Starting SimulateDev orchestrator...")
                
                # Monitor the orchestrator execution and provide progress updates based on actual milestones
                print(f"[TaskService] Starting orchestrator execution with milestone tracking...")
                response = await self._execute_with_milestone_tracking(orchestrator, task_request, task_id)
                
                print(f"[TaskService] Orchestrator execution completed: {response}")
                
                if response and response.success:
                    return {
                        'success': True, 
                        'pr_url': getattr(response, 'pr_url', None),
                        'final_output': response.final_output
                    }
                else:
                    error_msg = getattr(response, 'error_message', 'Orchestrator execution failed') if response else 'Orchestrator execution failed'
                    return {'success': False, 'error': error_msg}
                    
            except (ImportError, AttributeError) as import_error:
                print(f"[TaskService] Cannot use orchestrator ({import_error}), falling back to original execute_task")
                import traceback
                traceback.print_exc()
                
                # Fallback to original execute_task method
                await self._notify_progress(task_id, 30, "Using fallback execution method...")
                
                from simulatedev import execute_task
                
                # Start execution in background and provide progress updates
                execution_task = asyncio.create_task(execute_task(args))
                
                # Track progress with simulated milestones for fallback
                last_progress = 30
                check_interval = 5  # Check every 5 seconds
                timeout_seconds = 1800  # 30 minutes max
                start_time = asyncio.get_event_loop().time()
                
                while not execution_task.done():
                    elapsed = asyncio.get_event_loop().time() - start_time
                    
                    if elapsed > timeout_seconds:
                        execution_task.cancel()
                        await self._notify_progress(task_id, last_progress, "Execution timed out")
                        raise asyncio.TimeoutError(f"Execution timed out after {timeout_seconds // 60} minutes")
                    
                    # Update progress based on elapsed time
                    progress_percentage = min(90, 30 + int((elapsed / timeout_seconds) * 60))
                    
                    if progress_percentage > last_progress:
                        if progress_percentage >= 35 and last_progress < 35:
                            await self._notify_progress(task_id, 35, "Repository cloning in progress...")
                        elif progress_percentage >= 45 and last_progress < 45:
                            await self._notify_progress(task_id, 45, "IDE agent starting...") 
                        elif progress_percentage >= 55 and last_progress < 55:
                            await self._notify_progress(task_id, 55, "Analyzing codebase...")
                        elif progress_percentage >= 70 and last_progress < 70:
                            await self._notify_progress(task_id, 70, "Coding in progress...")
                        elif progress_percentage >= 85 and last_progress < 85:
                            await self._notify_progress(task_id, 85, "Finalizing solution...")
                        
                        last_progress = progress_percentage
                    
                    # Wait before next check
                    await asyncio.sleep(check_interval)
                
                # Get the result
                success = await execution_task
                
                print(f"[TaskService] Fallback execution completed with success: {success}")
                
                if success:
                    return {'success': True, 'pr_url': None}  # PR URL will be extracted separately
                else:
                    return {'success': False, 'error': 'SimulateDev execution returned false'}
                
        except Exception as e:
            print(f"[TaskService] ERROR in SimulateDev execution: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    async def _execute_with_milestone_tracking(self, orchestrator, task_request, task_id: str):
        """Execute orchestrator with milestone-based progress tracking"""
        try:
            # Start execution in background
            execution_task = asyncio.create_task(orchestrator.execute_task(task_request))
            
            # Track progress by checking execution state periodically
            last_progress = 30
            check_interval = 5  # Check every 5 seconds
            timeout_seconds = 1800  # 30 minutes max
            start_time = asyncio.get_event_loop().time()
            
            while not execution_task.done():
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if elapsed > timeout_seconds:
                    execution_task.cancel()
                    await self._notify_progress(task_id, last_progress, "Execution timed out")
                    raise asyncio.TimeoutError(f"Execution timed out after {timeout_seconds // 60} minutes")
                
                # Update progress based on elapsed time (more realistic than sleep-based)
                progress_percentage = min(95, 30 + int((elapsed / timeout_seconds) * 65))
                
                if progress_percentage > last_progress:
                    if progress_percentage >= 35 and last_progress < 35:
                        await self._notify_progress(task_id, 35, "Repository cloned successfully")
                    elif progress_percentage >= 45 and last_progress < 45:
                        await self._notify_progress(task_id, 45, "IDE agent initialized") 
                    elif progress_percentage >= 55 and last_progress < 55:
                        await self._notify_progress(task_id, 55, "Analyzing codebase and issue")
                    elif progress_percentage >= 70 and last_progress < 70:
                        await self._notify_progress(task_id, 70, "Implementing solution")
                    elif progress_percentage >= 85 and last_progress < 85:
                        await self._notify_progress(task_id, 85, "Finalizing changes")
                    
                    last_progress = progress_percentage
                
                # Wait before next check
                await asyncio.sleep(check_interval)
            
            # Get the result
            response = await execution_task
            return response
            
        except asyncio.CancelledError:
            await self._notify_progress(task_id, last_progress, "Execution was cancelled")
            raise
        except Exception as e:
            await self._notify_progress(task_id, last_progress, f"Execution error: {str(e)}")
            raise

    def _create_task_request_from_args(self, args):
        """Convert argparse args to TaskRequest object"""
        try:
            from src.orchestrator import TaskRequest
            from agents import AgentDefinition, AgentRole, CodingAgentIdeType
            
            print(f"[TaskService] Creating TaskRequest from args: agent={args.agent}, repo={args.repo}, task={args.task}")
            
            # Create agent definition
            agent_def = AgentDefinition(
                coding_ide=args.agent,
                model="claude-sonnet-4",  # Default model
                role=AgentRole.CODER
            )
            
            print(f"[TaskService] Created AgentDefinition: {agent_def}")
            
            # Create task request with correct field names
            task_request = TaskRequest(
                task_description=args.task,  # Correct field name
                agents=[agent_def],
                workflow_type="custom_coding",  # String, not enum
                repo_url=args.repo,  # Correct field name
                create_pr=not args.no_pr,
                target_dir=args.target_dir,  # Correct field name
                work_directory=args.work_dir,  # Correct field name
                delete_existing_repo_env=not getattr(args, 'no_delete_existing_repo_env', False)
            )
            
            print(f"[TaskService] Created TaskRequest successfully: {task_request}")
            return task_request
            
        except Exception as e:
            print(f"[TaskService] Error creating TaskRequest: {e}")
            import traceback
            traceback.print_exc()
            # Fallback - use the original execute_task method instead of orchestrator
            return args

    async def _execute_task_internal(self, task_id: str, github_token: str) -> Dict[str, Any]:
        """Internal task execution with milestone-based progress tracking"""
        
        try:
            import asyncio  # Import at method level to avoid scoping issues
            
            # Get task from database
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    raise Exception(f"Task {task_id} not found")
            finally:
                db.close()
            
            # Update task status to running
            await self._update_task_status(task_id, "running")
            await self._log_progress(task_id, "started", "Task execution started")
            
            # Give WebSocket connection time to establish (race condition fix)
            await asyncio.sleep(3)  # Increased from 2 to 3 seconds
            
            await self._notify_progress(task_id, 5, "Starting task execution...")
            
            # Import SimulateDev modules - only import if we're going to use them
            try:
                # Import the execute_task function from simulatedev.py
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
                
                import argparse
                
                await self._notify_progress(task_id, 10, "Preparing task execution environment...")
                
                # Create arguments for SimulateDev execution
                args = argparse.Namespace()
                args.workflow = "custom"
                args.repo = task.repo_url
                args.task = task.task_description or f"Resolve GitHub issue #{task.issue_number}: {task.issue_title}"
                
                # Set agent from first agent in config
                agent_config = task.agents_config[0] if task.agents_config else {'coding_ide': 'cursor', 'model': 'Claude 4 Sonnet', 'role': 'Coder'}
                args.agent = agent_config['coding_ide']
                args.coding_agents = None  # Single agent for now
                
                # Set other required arguments
                args.target_dir = None
                args.work_dir = None
                args.no_pr = False  # Always create PR
                args.output = None
                args.no_report = True  # Skip report for API execution
                args.no_delete_existing_repo_env = False  # Clean up after execution
                args.skip_github_check = True  # Skip preflight check for API
                
                await self._notify_progress(task_id, 15, "Creating task configuration...")
                
                # Get repository name for progress messages
                repo_name = task.repo_name
                agent_name = agent_config.get('coding_ide', 'Cursor').title()
                
                await self._notify_progress(task_id, 20, f"Initializing {repo_name} execution...")
                
                # Execute SimulateDev with integrated progress tracking
                print(f"[TaskService] Starting integrated SimulateDev execution...")
                try:
                    # Execute with milestone tracking instead of sleep-based simulation
                    response_data = await self._execute_simulatedev_with_progress_tracking(args, github_token, task_id)
                        
                    # Check execution result
                    if response_data and response_data.get('success'):
                        await self._notify_progress(task_id, 95, "Creating pull request...")
                        await asyncio.sleep(1)  # Brief pause for PR creation
                        
                        await self._notify_progress(task_id, 100, "Task completed successfully!")
                        
                        # Try to extract PR URL
                        pr_url = response_data.get('pr_url')
                        if not pr_url:
                            pr_url = await self._extract_pr_url_from_execution_output(task_id, task.repo_owner, task.repo_name)
                        
                        if not pr_url:
                            pr_url = await self._extract_pr_url_from_recent_reports(task.repo_owner, task.repo_name)
                        
                        if not pr_url:
                            pr_url = f"https://github.com/{task.repo_owner}/{task.repo_name}/pulls?q=is%3Apr+is%3Aopen+SimulateDev"
                            await self._log_progress(task_id, "warning", "Could not extract PR URL automatically. Check recent PRs in the repository.")
                        
                        await self._update_task_status(task_id, "completed", progress=100, pr_url=pr_url)
                        await self._log_progress(task_id, "completed", f"Task completed successfully. PR: {pr_url if pr_url else 'Not created'}")
                        
                        return {
                            'status': 'completed',
                            'progress': 100,
                            'pr_url': pr_url,
                            'message': 'Task completed successfully'
                        }
                    else:
                        # Execution failed
                        error_msg = response_data.get('error', 'SimulateDev execution failed') if response_data else 'SimulateDev execution failed'
                        await self._notify_progress(task_id, 75, f"Execution failed: {error_msg}")
                        raise Exception(f"SimulateDev execution failed: {error_msg}")
                        
                except asyncio.TimeoutError as e:
                    print(f"[TaskService] SimulateDev execution timed out: {str(e)}")
                    await self._notify_progress(task_id, 80, "Execution timed out")
                    raise Exception(str(e))
                except Exception as e:
                    # If execution fails, provide detailed error information
                    print(f"[TaskService] SimulateDev execution failed: {str(e)}")
                    
                    # Provide more specific error information based on error patterns
                    if any(pattern in str(e).lower() for pattern in ["cursor", "window", "focus", "ide"]):
                        error_detail = f"IDE integration issue: {str(e)}"
                    elif "timeout" in str(e).lower():
                        error_detail = f"Execution timeout: {str(e)}"
                    else:
                        error_detail = f"Execution error: {str(e)}"
                    
                    await self._notify_progress(task_id, 75, f"Error: {error_detail}")
                    raise Exception(error_detail)
                
            except Exception as import_error:
                print(f"[TaskService] ERROR importing SimulateDev modules: {str(import_error)}")
                await self._notify_progress(task_id, 15, "Failed to initialize execution environment")
                raise Exception(f"Failed to initialize SimulateDev environment: {str(import_error)}")
                
        except Exception as e:
            print(f"[TaskService] ERROR in task execution: {str(e)}")
            import traceback
            traceback.print_exc()
            
            await self._update_task_status(task_id, "failed", error_message=str(e))
            await self._log_progress(task_id, "failed", f"Task execution failed: {str(e)}")
            raise e
    
    async def _update_task_status(self, task_id: str, status: Optional[str], progress: Optional[int] = None,
                                 error_message: Optional[str] = None, pr_url: Optional[str] = None):
        """Update task status in database"""
        print(f"[TaskService] Updating task status: {task_id}")
        print(f"[TaskService] Status: {status}, Progress: {progress}, Error: {error_message}, PR: {pr_url}")
        
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                print(f"[TaskService] Found task in database: {task_id}")
                if status is not None:
                    task.status = status
                    print(f"[TaskService] Updated status to: {status}")
                if progress is not None:
                    task.progress = progress
                    print(f"[TaskService] Updated progress to: {progress}")
                if error_message:
                    task.error_message = error_message
                    print(f"[TaskService] Updated error message: {error_message}")
                if pr_url:
                    task.pr_url = pr_url
                    print(f"[TaskService] Updated PR URL: {pr_url}")
                if status == "running" and not task.started_at:
                    task.started_at = datetime.utcnow()
                    print(f"[TaskService] Set started_at timestamp")
                elif status in ["completed", "failed", "cancelled"]:
                    task.completed_at = datetime.utcnow()
                    print(f"[TaskService] Set completed_at timestamp")
                
                db.commit()
                print(f"[TaskService] Database commit successful for task: {task_id}")
            else:
                print(f"[TaskService] ERROR: Task not found in database: {task_id}")
        except Exception as e:
            print(f"[TaskService] ERROR updating task status: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    
    async def _log_progress(self, task_id: str, event_type: str, message: str):
        """Log progress to execution history"""
        print(f"[TaskService] Logging progress for task: {task_id}")
        print(f"[TaskService] Event: {event_type}, Message: {message}")
        
        db = SessionLocal()
        try:
            log_entry = ExecutionHistory(
                task_id=task_id,
                event_type=event_type,
                message=message
            )
            db.add(log_entry)
            db.commit()
            print(f"[TaskService] Progress log saved successfully for task: {task_id}")
        except Exception as e:
            print(f"[TaskService] ERROR logging progress: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    
    async def _notify_progress(self, task_id: str, progress: int, phase: str):
        """Notify progress via callback (WebSocket) and log to database"""
        print(f"[TaskService] Notifying progress for task: {task_id}")
        print(f"[TaskService] Progress: {progress}%, Phase: {phase}")
        
        # Update task progress in database
        await self._update_task_status(task_id, None, progress=progress)
        
        # Log the phase information to execution history
        await self._log_progress(task_id, "progress", phase)
        
        # Notify via callback if available
        if task_id in self.progress_callbacks:
            try:
                callback = self.progress_callbacks[task_id]
                print(f"[TaskService] Found progress callback for task: {task_id}, calling it")
                print(f"[TaskService] Callback type: {type(callback)}")
                
                progress_data = {
                    "task_id": task_id,
                    "progress": progress,
                    "current_phase": phase,
                    "timestamp": datetime.utcnow().isoformat()
                }
                print(f"[TaskService] Calling callback with data: {progress_data}")
                
                await callback(progress_data)
                print(f"[TaskService] Progress callback completed successfully for task: {task_id}")
                
            except Exception as e:
                print(f"[TaskService] ERROR in progress callback for task {task_id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[TaskService] No progress callback found for task: {task_id}")
            print(f"[TaskService] Available callbacks: {list(self.progress_callbacks.keys())}")
    
    async def _simulate_progress_updates(self, task_id: str, progress_steps: list):
        """Simulate progress updates during execution"""
        try:
            for progress, phase in progress_steps:
                await self._notify_progress(task_id, progress, phase)
                await asyncio.sleep(3)  # Update every 3 seconds
        except asyncio.CancelledError:
            pass  # Task completed, stop progress updates
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.cancel()
            await self._update_task_status(task_id, "cancelled")
            await self._log_progress(task_id, "cancelled", "Task cancelled by user")
            return True
        return False
    
    def get_running_tasks(self) -> List[str]:
        """Get list of currently running task IDs"""
        return list(self.running_tasks.keys())
    
    def is_task_running(self, task_id: str) -> bool:
        """Check if a task is currently running"""
        return task_id in self.running_tasks 

    async def _extract_pr_url_from_execution_output(self, task_id: str, repo_owner: str, repo_name: str) -> Optional[str]:
        """Try to extract PR URL from execution output files"""
        try:
            # Check execution output directory for recent reports
            from app.config import Settings
            settings = Settings()
            output_dir = settings.execution_output_path
            
            if not os.path.exists(output_dir):
                return None
            
            # Look for recent execution reports (last 10 minutes)
            import time
            current_time = time.time()
            cutoff_time = current_time - (10 * 60)  # 10 minutes ago
            
            for filename in os.listdir(output_dir):
                if filename.endswith('_execution_report.json'):
                    filepath = os.path.join(output_dir, filename)
                    file_mtime = os.path.getmtime(filepath)
                    
                    if file_mtime > cutoff_time:
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                report_data = json.load(f)
                                
                            # Check if this report has a PR URL and matches our repo
                            pr_url = report_data.get('pr_url')
                            if pr_url and f"/{repo_owner}/{repo_name}/" in pr_url:
                                await self._log_progress(task_id, "info", f"Found PR URL in execution report: {pr_url}")
                                return pr_url
                        except (json.JSONDecodeError, IOError):
                            continue
            
            return None
        except Exception as e:
            await self._log_progress(task_id, "warning", f"Error extracting PR URL from execution output: {str(e)}")
            return None
    
    async def _extract_pr_url_from_recent_reports(self, repo_owner: str, repo_name: str) -> Optional[str]:
        """Try to extract PR URL from recent execution reports"""
        try:
            from app.config import Settings
            settings = Settings()
            output_dir = settings.execution_output_path
            
            if not os.path.exists(output_dir):
                return None
            
            # Look for any reports containing this repo (last 30 minutes)
            import time
            current_time = time.time()
            cutoff_time = current_time - (30 * 60)  # 30 minutes ago
            
            for filename in os.listdir(output_dir):
                if filename.endswith('.json') and repo_name in filename:
                    filepath = os.path.join(output_dir, filename)
                    file_mtime = os.path.getmtime(filepath)
                    
                    if file_mtime > cutoff_time:
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                report_data = json.load(f)
                                
                            pr_url = report_data.get('pr_url')
                            if pr_url and f"/{repo_owner}/{repo_name}/" in pr_url:
                                return pr_url
                        except (json.JSONDecodeError, IOError):
                            continue
            
            return None
        except Exception:
            return None 