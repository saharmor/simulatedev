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
    from agents import AgentDefinition, AgentRole, CodingAgentIdeType
    from common.config import config
    from src.github_integration import GitHubIntegration
except ImportError as e:
    print(f"Warning: Could not import SimulateDev modules: {e}")
    Orchestrator = None
    TaskRequest = None
    AgentDefinition = None
    GitHubIntegration = None

from app.database import SessionLocal
from app.models.task import Task, ExecutionHistory


class TaskService:
    """Service for managing SimulateDev task execution"""
    
    def __init__(self):
        self.github_integration = GitHubIntegration() if GitHubIntegration else None
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
            # Parse repo URL to get basic info using GitHubIntegration
            if self.github_integration:
                repo_info = self.github_integration.parse_repo_info(issue_url)
            else:
                # Fallback parsing if GitHubIntegration is not available
                repo_info = self._parse_repo_url_fallback(issue_url)
            
            # Extract issue information from repo_info if not provided
            final_issue_number = issue_number or repo_info.get('issue_number')
            final_issue_title = issue_title
            
            # For GitHub issues, synthesize the detailed task prompt
            final_task_prompt = task_prompt
            if final_issue_number and github_token and self.github_integration:
                try:
                    # Use GitHubIntegration to fetch issue data
                    issue_data = self._get_issue_details(
                        repo_info['owner'], 
                        repo_info['repo'], 
                        final_issue_number, 
                        github_token
                    )
                    
                    # Update issue title if not provided
                    if not final_issue_title:
                        final_issue_title = issue_data.get('title')
                    
                    # Synthesize detailed task prompt from issue data
                    final_task_prompt = self._synthesize_task_prompt(issue_data, repo_info)
                    print(f"Auto-synthesized detailed task prompt for GitHub issue #{final_issue_number}")
                    
                except Exception as e:
                    print(f"Warning: Failed to synthesize task prompt from issue #{final_issue_number}: {e}")
                    # Fallback to the provided prompt or a basic prompt
                    if not task_prompt:
                        final_task_prompt = f"Resolve GitHub issue #{final_issue_number}: {final_issue_title or 'See issue details'}"
                    else:
                        final_task_prompt = task_prompt
            
            # If still no prompt, use provided prompt or create a basic fallback
            if not final_task_prompt:
                final_task_prompt = task_prompt or f"Complete the requested task for repository {repo_info['repo_url']}"
            
            # Create task record
            task_id = str(uuid.uuid4())
            task = Task(
                id=task_id,
                user_id=user_id,
                repo_url="https://github.com/repos/{repo_info['owner']}/{repo_info['repo']}/",
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
            
            print(f"Task created: {task_id} for repo https://github.com/repos/{repo_info['owner']}/{repo_info['repo']}/")
            return task_id
            
        finally:
            db.close()
    
    async def execute_task(self, task_id: str, github_token: str, 
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Execute a SimulateDev task using the Orchestrator"""
        
        if progress_callback:
            self.progress_callbacks[task_id] = progress_callback
        
        try:
            # Create async task for execution
            execution_task = asyncio.create_task(
                self._execute_task_internal(task_id, github_token)
            )
            
            # Store running task
            self.running_tasks[task_id] = execution_task
            
            # Wait for completion
            result = await execution_task
            return result
            
        except Exception as e:
            print(f"[TaskService] ERROR in execute_task for {task_id}: {str(e)}")
            await self._update_task_status(task_id, "failed", error_message=str(e))
            await self._log_progress(task_id, "failed", f"Task execution failed: {str(e)}")
            raise e
        finally:
            # Cleanup
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.progress_callbacks:
                del self.progress_callbacks[task_id]

    async def _execute_task_internal(self, task_id: str, github_token: str) -> Dict[str, Any]:
        """Internal task execution using Orchestrator directly"""
        
        try:
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
            
            # Brief pause for WebSocket connection establishment
            await asyncio.sleep(2)
            
            await self._notify_progress(task_id, 5, "Initializing task execution...")
            
            # Validate required modules are available
            if not Orchestrator or not TaskRequest or not AgentDefinition:
                raise Exception("SimulateDev core modules not available")
            
            await self._notify_progress(task_id, 10, "Creating task request...")
            
            # Create TaskRequest from task data
            task_request = self._create_task_request(task)
            
            await self._notify_progress(task_id, 15, "Starting orchestrator...")
            
            # Create and execute orchestrator
            orchestrator = Orchestrator(github_token)
            
            # Execute with progress monitoring
            response = await self._execute_with_progress_monitoring(
                orchestrator, task_request, task_id, task.repo_name
            )
            
            # Process results
            if response and response.success:
                await self._notify_progress(task_id, 95, "Processing results...")
                
                pr_url = getattr(response, 'pr_url', None)
                if not pr_url:
                    # Try to extract PR URL from output or recent reports
                    pr_url = await self._extract_pr_url(task_id, task.repo_owner, task.repo_name)
                
                await self._notify_progress(task_id, 100, "Task completed successfully!")
                await self._update_task_status(task_id, "completed", progress=100, pr_url=pr_url)
                
                return {
                    'success': True,
                    'pr_url': pr_url,
                    'final_output': response.final_output
                }
            else:
                error_msg = getattr(response, 'error_message', 'Task execution failed') if response else 'Task execution failed'
                await self._update_task_status(task_id, "failed", error_message=error_msg)
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"[TaskService] ERROR in task execution: {str(e)}")
            await self._update_task_status(task_id, "failed", error_message=str(e))
            await self._log_progress(task_id, "failed", f"Task execution failed: {str(e)}")
            raise e
    
    def _create_task_request(self, task: Task) -> TaskRequest:
        """Create TaskRequest from Task model"""
        # Create agent definitions from task config
        agents = []
        for agent_config in task.agents_config:
            agent_def = AgentDefinition(
                coding_ide=agent_config['coding_ide'],
                model=agent_config.get('model', 'claude-sonnet-4'),
                role=AgentRole(agent_config.get('role', 'Coder'))
            )
            agents.append(agent_def)
        
        # Create TaskRequest
        return TaskRequest(
            task_description=task.task_description,
            agents=agents,
            workflow_type=task.workflow_type,
            repo_url=task.repo_url,
            create_pr=True,  # Always create PR for API execution
            delete_existing_repo_env=True  # Clean execution environment
        )
    
    async def _execute_with_progress_monitoring(self, orchestrator: Orchestrator, 
                                              task_request: TaskRequest, task_id: str, 
                                              repo_name: str):
        """Execute orchestrator with progress monitoring"""
        try:
            # Start execution in background
            execution_task = asyncio.create_task(orchestrator.execute_task(task_request))
            
            # Monitor progress
            last_progress = 15
            check_interval = 10  # Check every 10 seconds
            timeout_seconds = 1800  # 30 minutes max
            start_time = asyncio.get_event_loop().time()
            
            while not execution_task.done():
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if elapsed > timeout_seconds:
                    execution_task.cancel()
                    await self._notify_progress(task_id, last_progress, "Execution timed out")
                    raise asyncio.TimeoutError(f"Execution timed out after {timeout_seconds // 60} minutes")
                
                # Update progress based on elapsed time
                progress_percentage = min(90, 15 + int((elapsed / timeout_seconds) * 75))
                
                if progress_percentage > last_progress:
                    if progress_percentage >= 25 and last_progress < 25:
                        await self._notify_progress(task_id, 25, f"Repository {repo_name} cloned successfully")
                    elif progress_percentage >= 40 and last_progress < 40:
                        await self._notify_progress(task_id, 40, "IDE agent initialized") 
                    elif progress_percentage >= 55 and last_progress < 55:
                        await self._notify_progress(task_id, 55, "Analyzing codebase and issue")
                    elif progress_percentage >= 70 and last_progress < 70:
                        await self._notify_progress(task_id, 70, "Implementing solution")
                    elif progress_percentage >= 85 and last_progress < 85:
                        await self._notify_progress(task_id, 85, "Finalizing changes")
                    
                    last_progress = progress_percentage
                
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

    async def _update_task_status(self, task_id: str, status: Optional[str], progress: Optional[int] = None,
                                 error_message: Optional[str] = None, pr_url: Optional[str] = None):
        """Update task status in database"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                if status:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if error_message:
                    task.error_message = error_message
                if pr_url:
                    task.pr_url = pr_url
                if status == "running" and not task.started_at:
                    task.started_at = datetime.utcnow()
                elif status in ["completed", "failed", "cancelled"]:
                    task.completed_at = datetime.utcnow()
                
                db.commit()
        except Exception as e:
            print(f"[TaskService] ERROR updating task status: {e}")
        finally:
            db.close()
    
    async def _log_progress(self, task_id: str, event_type: str, message: str):
        """Log progress to execution history"""
        db = SessionLocal()
        try:
            log_entry = ExecutionHistory(
                task_id=task_id,
                event_type=event_type,
                message=message
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            print(f"[TaskService] ERROR logging progress: {e}")
        finally:
            db.close()
    
    async def _notify_progress(self, task_id: str, progress: int, phase: str):
        """Notify progress via callback and log to database"""
        # Update task progress in database
        await self._update_task_status(task_id, None, progress=progress)
        
        # Log the phase information to execution history
        await self._log_progress(task_id, "progress", phase)
        
        # Notify via callback if available
        if task_id in self.progress_callbacks:
            try:
                callback = self.progress_callbacks[task_id]
                progress_data = {
                    "task_id": task_id,
                    "progress": progress,
                    "current_phase": phase,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await callback(progress_data)
            except Exception as e:
                print(f"[TaskService] ERROR in progress callback for task {task_id}: {e}")
    
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

    def _parse_repo_url_fallback(self, url: str) -> Dict[str, Any]:
        """Fallback repo URL parsing when GitHubIntegration is not available"""
        import re
        
        if not url:
            raise ValueError("Repository URL is required")
        
        # Handle different GitHub URL formats
        patterns = [
            # Full issue URL: https://github.com/owner/repo/issues/123
            r'github\.com/([^/]+)/([^/]+)/issues/(\d+)',
            # Repository URL: https://github.com/owner/repo
            r'github\.com/([^/]+)/([^/]+)/?$',
            # Repository URL with .git: https://github.com/owner/repo.git
            r'github\.com/([^/]+)/([^/]+)\.git/?$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner = match.group(1)
                repo = match.group(2)
                
                result = {
                    'owner': owner,
                    'repo': repo,
                    'repo_url': f"https://github.com/{owner}/{repo}",
                    'type': 'repository'
                }
                
                # If it's an issue URL, extract issue number
                if len(match.groups()) >= 3:
                    issue_number = int(match.group(3))
                    result.update({
                        'issue_number': issue_number,
                        'issue_url': url,
                        'type': 'issue'
                    })
                
                return result
        
        raise ValueError(f"Invalid GitHub repository URL: {url}")
    
    def _get_issue_details(self, owner: str, repo: str, issue_number: int, token: str) -> Dict[str, Any]:
        """Get issue details using GitHub API"""
        import requests
        
        headers = {'Authorization': f'token {token}'}
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch issue details: {str(e)}")
    
    def _synthesize_task_prompt(self, issue_data: Dict[str, Any], repo_info: Dict[str, Any]) -> str:
        """Synthesize a detailed task prompt from GitHub issue data"""
        title = issue_data.get('title', 'No title')
        body = issue_data.get('body', 'No description provided')
        
        # Create a comprehensive task prompt
        prompt = f"""Resolve GitHub issue: {title}

Issue Description:
{body}

Repository: https://github.com/repos/{repo_info['owner']}/{repo_info['repo']}/

Please analyze the issue, understand the requirements, and implement the necessary changes to resolve this issue. Make sure to:
1. Understand the problem described in the issue
2. Identify the relevant code files and components
3. Implement a clean, well-tested solution
4. Follow the project's coding standards and conventions
5. Ensure the solution addresses all aspects of the issue"""

        return prompt

    async def _extract_pr_url(self, task_id: str, repo_owner: str, repo_name: str) -> Optional[str]:
        """Try to extract PR URL from execution output files or recent reports"""
        try:
            # Check execution output directory for recent reports
            output_dir = config.execution_output_path
            
            if not os.path.exists(output_dir):
                return None
            
            # Look for recent execution reports (last 30 minutes)
            import time
            current_time = time.time()
            cutoff_time = current_time - (30 * 60)  # 30 minutes ago
            
            for filename in os.listdir(output_dir):
                if filename.endswith('.json') and (repo_name in filename or 'execution_report' in filename):
                    filepath = os.path.join(output_dir, filename)
                    file_mtime = os.path.getmtime(filepath)
                    
                    if file_mtime > cutoff_time:
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                report_data = json.load(f)
                                
                            pr_url = report_data.get('pr_url')
                            if pr_url and f"/{repo_owner}/{repo_name}/" in pr_url:
                                await self._log_progress(task_id, "info", f"Found PR URL in report: {pr_url}")
                                return pr_url
                        except (json.JSONDecodeError, IOError):
                            continue
            
            return None
        except Exception as e:
            await self._log_progress(task_id, "warning", f"Error extracting PR URL: {str(e)}")
            return None 