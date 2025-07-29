import sys
import os
import asyncio
import uuid
import time
import logging
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
from app.services.progress_monitor import ProgressMonitor
from app.schemas.progress import PhaseType, StepType


class TaskService:
    """Service for managing SimulateDev task execution"""
    
    def __init__(self):
        self.github_integration = GitHubIntegration() if GitHubIntegration else None
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
        
        # Initialize CLI agent services
        self.tmux_service = TmuxService()
        self.output_adapter = OutputStreamAdapter(self.tmux_service)
        self._cli_services_started = False
        self.logger = logging.getLogger(__name__)
    
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
            
            # Generate steps plan before creating task
            from app.services.progress_monitor import ProgressMonitor
            task_id = str(uuid.uuid4())
            progress_monitor = ProgressMonitor(task_id)
            steps_plan = progress_monitor.generate_steps_plan(agents_config, workflow_type)
            
            # Create task record
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
                steps_plan=steps_plan.dict(),  # Store as JSON
                status="pending",
                estimated_duration=options.get('timeout_seconds', 1800) if options else 1800
            )
            
            db.add(task)
            db.commit()
            
            print(f"Task created: {task_id} for repo {repo_info['repo_url']}")
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
        """Internal task execution using Orchestrator in a separate thread"""
        
        # Get task from database to access steps plan
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise Exception(f"Task {task_id} not found")
            
            # Create steps lookup from stored steps plan
            steps_lookup = {}
            if task.steps_plan and task.steps_plan.get('steps'):
                for step_data in task.steps_plan['steps']:
                    from app.schemas.progress import PreGeneratedStep, PhaseType, StepType, AgentContext
                    step = PreGeneratedStep(
                        step_id=step_data['step_id'],
                        phase=PhaseType(step_data['phase']),
                        step=StepType(step_data['step']),
                        agent_context=AgentContext(**step_data['agent_context']) if step_data.get('agent_context') else None,
                        step_order=step_data['step_order'],
                        description=step_data.get('description')
                    )
                    steps_lookup[step.step_id] = step
                    
        finally:
            db.close()
        
        # Create progress monitor with WebSocket callback and steps plan
        progress_monitor = ProgressMonitor(
            task_id, 
            self._create_websocket_callback(task_id),
            steps_lookup
        )
        
        try:
            
            # Update task status to running
            await self._update_task_status(task_id, "running")
            
            # Brief pause for WebSocket connection establishment
            await asyncio.sleep(2)
            
            # Initialization steps
            await progress_monitor.mark_step_in_progress(
                PhaseType.INITIALIZATION, 
                StepType.CONNECTING_SERVER
            )
            
            await progress_monitor.mark_step_completed(
                PhaseType.INITIALIZATION, 
                StepType.CONNECTING_SERVER
            )
            
            await progress_monitor.mark_step_in_progress(
                PhaseType.INITIALIZATION, 
                StepType.INITIALIZING_EXECUTION
            )
            
            # Validate required modules are available
            if not Orchestrator or not TaskRequest or not AgentDefinition:
                await progress_monitor.mark_step_failed(
                    PhaseType.INITIALIZATION,
                    StepType.INITIALIZING_EXECUTION,
                    "SimulateDev core modules not available"
                )
                raise Exception("SimulateDev core modules not available")
            
            await progress_monitor.mark_step_completed(
                PhaseType.INITIALIZATION, 
                StepType.INITIALIZING_EXECUTION
            )
            
            await progress_monitor.mark_step_in_progress(
                PhaseType.INITIALIZATION, 
                StepType.CREATING_REQUEST
            )
            
            await progress_monitor.mark_step_completed(
                PhaseType.INITIALIZATION, 
                StepType.CREATING_REQUEST
            )
            
            # Create TaskRequest from task data
            task_request = self._create_task_request(task)
            
            # Execute orchestrator in a separate thread to avoid blocking the event loop
            print(f"[TaskService] Starting orchestrator execution in separate thread for task: {task_id}")
            response = await asyncio.get_event_loop().run_in_executor(
                None,  # Use default thread pool
                self._execute_orchestrator_sync,
                task_request,
                github_token,
                progress_monitor
            )
            
            # Process results
            if response and response.success:
                await progress_monitor.mark_step_in_progress(
                    PhaseType.COMPLETION,
                    StepType.PROCESSING_RESULTS
                )
                
                await progress_monitor.mark_step_completed(
                    PhaseType.COMPLETION,
                    StepType.PROCESSING_RESULTS
                )
                
                if not pr_url:
                    # Try to extract PR URL from output or recent reports
                    pr_url = await self._extract_pr_url(task_id, task.repo_owner, task.repo_name)
                
                if pr_url:
                    await progress_monitor.mark_step_in_progress(
                        PhaseType.COMPLETION,
                        StepType.CREATING_PR
                    )
                    
                    await progress_monitor.mark_step_completed(
                        PhaseType.COMPLETION,
                        StepType.CREATING_PR
                    )
                
                # Mark task as completed
                await self._update_task_status(task_id, "completed", progress=100, pr_url=pr_url)
                
                return {
                    'success': True,
                    'pr_url': pr_url,
                    'final_output': final_output
                }
            else:
                await self._update_task_status(task_id, "failed", error_message=error_msg)
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"[TaskService] ERROR in task execution: {str(e)}")
            await self._update_task_status(task_id, "failed", error_message=str(e))
            
            # Report task failure if we have a progress monitor
            if 'progress_monitor' in locals():
                await progress_monitor.mark_step_failed(
                    PhaseType.INITIALIZATION,  # Assume failure during initialization if early
                    StepType.INITIALIZING_EXECUTION,
                    str(e)
                )
            
            raise e

    def _execute_orchestrator_sync(self, task_request: TaskRequest, github_token: str, progress_monitor) -> Any:
        """Synchronous wrapper for orchestrator execution that runs in a separate thread"""
        try:
            print(f"[TaskService] Creating orchestrator in thread for task execution")
            
            # Create and execute orchestrator
            orchestrator = Orchestrator(github_token)
            
            # Create a new event loop for this thread since we're in a separate thread
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Execute orchestrator - it will handle AGENT_EXECUTION phase progress
            print(f"[TaskService] Executing orchestrator in thread")
            response = loop.run_until_complete(
                orchestrator.execute_task(task_request, progress_monitor)
            )
            
            print(f"[TaskService] Orchestrator execution completed in thread")
            return response
            
        except Exception as e:
            print(f"[TaskService] ERROR in orchestrator execution thread: {str(e)}")
            import traceback
            traceback.print_exc()
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
    
    def _create_websocket_callback(self, task_id: str):
        """Create WebSocket callback for progress monitoring"""
        async def websocket_callback(progress_data: dict):
            """Send progress update via WebSocket"""
            if task_id in self.progress_callbacks:
                try:
                    callback = self.progress_callbacks[task_id]
                    await callback(progress_data)
                except Exception as e:
                    print(f"[TaskService] ERROR in WebSocket callback for task {task_id}: {e}")
        
        return websocket_callback
    
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
        
    async def cleanup(self):
        """Cleanup task service and CLI services"""
        if self._cli_services_started:
            await self.output_adapter.stop()
            await self.tmux_service.stop()
            self._cli_services_started = False
            self.logger.info("CLI agent services stopped") 

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

Repository: {repo_info['repo_url']}

Please analyze the issue, understand the requirements, and implement the necessary changes to resolve this issue. Make sure to:
1. Understand the problem described in the issue
2. Identify the relevant code files and components
3. Implement a clean, well-tested solution
4. Follow the project's coding standards and conventions
5. Ensure the solution addresses all aspects of the issue"""

        return prompt

    async def create_sequential_agents_config(self, base_agents_config: List[Dict], sequential_agents_config: Dict = None) -> List[Dict]:
        """Create sequential agent configuration: Coder -> Tester -> Coder"""
        if not base_agents_config:
            raise ValueError("Base agent configuration is required for sequential execution")
        
        # If specific sequential agents are provided, use them
        if sequential_agents_config and 'coder1' in sequential_agents_config:
            sequential_agents = [
                # First Coder agent
                {
                    "coding_ide": sequential_agents_config['coder1']['id'],
                    "model": "claude-sonnet-4",  # Default model
                    "role": "Coder"
                },
                # Tester agent
                {
                    "coding_ide": sequential_agents_config['tester']['id'],
                    "model": "claude-sonnet-4",  # Default model
                    "role": "Tester"
                },
                # Second Coder agent for iteration
                {
                    "coding_ide": sequential_agents_config['coder2']['id'],
                    "model": "claude-sonnet-4",  # Default model
                    "role": "Coder"
                }
            ]
            
            print(f"[TaskService] Created sequential agents config with custom agents:")
            print(f"[TaskService] Coder1: {sequential_agents_config['coder1']['name']}")
            print(f"[TaskService] Tester: {sequential_agents_config['tester']['name']}")
            print(f"[TaskService] Coder2: {sequential_agents_config['coder2']['name']}")
        else:
            # Fallback to using the first agent for all stages
            base_agent = base_agents_config[0]
            
            sequential_agents = [
                # First Coder agent
                {
                    "coding_ide": base_agent["coding_ide"],
                    "model": base_agent["model"],
                    "role": "Coder"
                },
                # Tester agent with same IDE and model
                {
                    "coding_ide": base_agent["coding_ide"],
                    "model": base_agent["model"],
                    "role": "Tester"
                },
                # Second Coder agent for iteration
                {
                    "coding_ide": base_agent["coding_ide"],
                    "model": base_agent["model"],
                    "role": "Coder"
                }
            ]
            
            print(f"[TaskService] Created sequential agents config from base: {base_agent}")
        
        print(f"[TaskService] Sequential agents: {sequential_agents}")
        return sequential_agents

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
            
    def _is_cli_agent_task(self, agents_config: List[Dict]) -> bool:
        """Check if the task uses CLI agents"""
        cli_agent_types = {'claude_cli', 'gemini_cli'}
        
        for agent_config in agents_config:
            coding_ide = agent_config.get('coding_ide', '').lower()
            if coding_ide in cli_agent_types:
                return True
        return False
        
    async def _ensure_cli_services_started(self):
        """Ensure CLI agent services are started"""
        if not self._cli_services_started:
            await self.tmux_service.start()
            await self.output_adapter.start()
            self._cli_services_started = True
            self.logger.info("CLI agent services started")
            
    async def _execute_cli_agent(self, task_id: str, task: Task, github_token: str) -> Dict[str, Any]:
        """Execute task using CLI agents through tmux"""
        try:
            # Ensure CLI services are running
            await self._ensure_cli_services_started()
            
            # Get first CLI agent config (for now, support single agent)
            cli_agent_config = None
            for agent_config in task.agents_config:
                coding_ide = agent_config.get('coding_ide', '').lower()
                if coding_ide in {'claude_cli', 'gemini_cli'}:
                    cli_agent_config = agent_config
                    break
                    
            if not cli_agent_config:
                raise Exception("No CLI agent configuration found")
                
            agent_type_str = cli_agent_config['coding_ide'].lower()
            
            # Map to AgentType enum
            if agent_type_str == 'claude_cli':
                agent_type = AgentType.CLAUDE
            elif agent_type_str == 'gemini_cli':
                agent_type = AgentType.GEMINI
            else:
                raise Exception(f"Unsupported CLI agent type: {agent_type_str}")
                
            await self._notify_progress(task_id, 20, f"Creating {agent_type.value} session...")
            
            # Create tmux session
            session_id = f"task_{task_id}_{int(time.time())}"
            yolo_mode = cli_agent_config.get('yolo_mode', False)
            
            await self.tmux_service.create_session(
                session_id=session_id,
                agent_type=agent_type,
                prompt=task.task_description,
                repo_url=task.repo_url,
                yolo_mode=yolo_mode
            )
            
            await self._notify_progress(task_id, 30, "Starting output streaming...")
            
            # Start output streaming
            await self.output_adapter.start_streaming(task_id, session_id)
            
            # The prompt will be sent automatically by tmux_service monitoring task
            # when the agent is ready (status changes from SPAWNING to RUNNING)
            await self._notify_progress(task_id, 40, f"Waiting for {agent_type.value} agent to be ready...")
            
            await self._notify_progress(task_id, 60, "Agent is processing the task...")
            
            # Monitor session execution
            result = await self._monitor_cli_agent_execution(task_id, session_id)
            
            # Stop streaming
            await self.output_adapter.stop_streaming(task_id, "completed" if result['success'] else "failed")
            
            return result
            
        except Exception as e:
            # Cleanup on error
            if 'session_id' in locals():
                try:
                    await self.tmux_service.cleanup_session(session_id)
                    await self.output_adapter.stop_streaming(task_id, "failed")
                except:
                    pass
            raise e
            
    async def _monitor_cli_agent_execution(self, task_id: str, session_id: str) -> Dict[str, Any]:
        """Monitor CLI agent execution until completion"""
        start_time = time.time()
        timeout_seconds = 1800  # 30 minutes
        check_interval = 5.0  # Check every 5 seconds
        last_progress = 60
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed > timeout_seconds:
                    await self._notify_progress(task_id, last_progress, "Task timed out")
                    await self.tmux_service.cleanup_session(session_id)
                    return {'success': False, 'error': 'Task execution timed out'}
                
                # Get session status
                session_info = await self.tmux_service.get_session_status(session_id)
                if not session_info:
                    await self._notify_progress(task_id, last_progress, "Session ended unexpectedly")
                    return {'success': False, 'error': 'Session ended unexpectedly'}
                
                # Update progress based on status and elapsed time
                progress_percentage = min(90, 60 + int((elapsed / timeout_seconds) * 30))
                
                if progress_percentage > last_progress:
                    if session_info.status.value == "RUNNING":
                        await self._notify_progress(task_id, progress_percentage, f"Agent is actively working...")
                    elif session_info.status.value == "REQUIRES_USER_INPUT":
                        await self._notify_progress(task_id, progress_percentage, "Agent requires user input (handling automatically)")
                    
                    last_progress = progress_percentage
                
                # Check if session is complete
                if session_info.status.value in ["DONE", "STOPPED"]:
                    if session_info.status.value == "DONE":
                        await self._notify_progress(task_id, 95, "Agent completed successfully")
                        
                        # Capture final output
                        final_output = await self.tmux_service.capture_session_output(session_id)
                        
                        # Cleanup session
                        await self.tmux_service.cleanup_session(session_id)
                        
                        return {
                            'success': True,
                            'final_output': final_output,
                            'pr_url': None  # CLI agents don't directly create PRs yet
                        }
                    else:
                        await self._notify_progress(task_id, last_progress, "Agent stopped unexpectedly")
                        await self.tmux_service.cleanup_session(session_id)
                        return {'success': False, 'error': 'Agent stopped unexpectedly'}
                
                await asyncio.sleep(check_interval)
                
        except Exception as e:
            await self._notify_progress(task_id, last_progress, f"Error monitoring execution: {str(e)}")
            try:
                await self.tmux_service.cleanup_session(session_id)
            except:
                pass
            return {'success': False, 'error': str(e)} 