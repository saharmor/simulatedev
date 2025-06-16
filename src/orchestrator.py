#!/usr/bin/env python3
"""
Unified Orchestrator Module

This module provides a single orchestrator for all agent execution scenarios.
Single-agent execution is treated as multi-agent with one agent.
Workflows are task type modifiers that influence role-specific prompts.
"""

import os
import json
import time
import webbrowser
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from utils.computer_use_utils import ClaudeComputerUse
from agents import (
    AgentFactory, CodingAgentIdeType, AgentRole, MultiAgentTask, 
    AgentDefinition, AgentContext, MultiAgentResponse
)
from roles import RoleFactory
from utils.clone_repo import clone_repository
from src.github_integration import GitHubIntegration
from common.config import config


@dataclass
class TaskRequest:
    """Unified request structure for all agent execution scenarios"""
    task_description: str
    agents: List[AgentDefinition]
    workflow_type: Optional[str] = None  # bug_hunting, code_optimization, custom_coding, etc.
    repo_url: Optional[str] = None
    target_dir: Optional[str] = None
    create_pr: bool = True
    work_directory: Optional[str] = None
    delete_existing_repo_env: bool = True
    

class Orchestrator:
    """Unified orchestrator for all agent execution scenarios"""
    
    def __init__(self):
        self.computer_use_client = ClaudeComputerUse()
        self.github_integration = GitHubIntegration()
        self.execution_log = []
        
        # Create necessary directories using config
        self.base_dir = config.scanned_repos_path
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.responses_dir = config.reports_path
        os.makedirs(self.responses_dir, exist_ok=True)
    
    @classmethod
    def create_request(cls, 
                      # Core parameters
                      task_description: Optional[str] = None,
                      agents: Optional[List[AgentDefinition]] = None,
                      
                      # Workflow parameters (for predefined workflows)
                      workflow_type: Optional[str] = None,
                      
                      # Single agent parameters (convenience)
                      agent_type: Optional[str] = None,
                      agent_model: str = "claude-sonnet-4",
                      agent_role: AgentRole = AgentRole.CODER,
                      
                      # Multi-agent parameters (convenience)
                      multi_agent_task: Optional[MultiAgentTask] = None,
                      
                      # Common parameters
                      repo_url: Optional[str] = None,
                      target_dir: Optional[str] = None,
                      create_pr: bool = True,
                      work_directory: Optional[str] = None,
                      delete_existing_repo_env: bool = True) -> TaskRequest:
        """
        Unified request creation method for all agent execution scenarios.
        
        Usage patterns:
        1. Predefined workflow: create_request(workflow_type="bugs", repo_url="...", agent_type="cursor")
        2. Single agent: create_request(task_description="...", agent_type="cursor")
        3. Multi-agent: create_request(task_description="...", agents=[...])
        4. From MultiAgentTask: create_request(multi_agent_task=task)
        """
        
        # Determine the scenario and generate appropriate task_description and agents
        final_task_description = None
        final_agents = None
        final_workflow_type = workflow_type
        
        # Scenario 1: Predefined workflow
        if workflow_type and workflow_type in ['bugs', 'optimize', 'refactor', 'low-hanging', 'test']:
            if not repo_url:
                raise ValueError("repo_url is required for predefined workflows")
            if not agent_type:
                raise ValueError("agent_type is required for predefined workflows")
                
            # Generate workflow-specific prompt
            final_task_description = cls._generate_workflow_prompt(workflow_type, repo_url)
            
            # Create single coder agent
            try:
                agent_enum = CodingAgentIdeType(agent_type.lower().strip())
            except ValueError:
                raise ValueError(f"Unsupported agent type: {agent_type}. Valid agent types are: {', '.join([e.value for e in CodingAgentIdeType])}")
            
            final_agents = [AgentDefinition(
                coding_ide=agent_enum.value,
                model=agent_model,
                role=agent_role
            )]
        
        # Scenario 2: Multi-agent task object
        elif multi_agent_task:
            final_task_description = multi_agent_task.get_task_description()
            final_agents = multi_agent_task.agents
            final_workflow_type = workflow_type or (multi_agent_task.workflow.value if multi_agent_task.workflow else None)
            repo_url = repo_url or multi_agent_task.repo_url
        
        # Scenario 3: Explicit agents provided
        elif agents:
            if not task_description:
                raise ValueError("task_description is required when providing explicit agents")
            final_task_description = task_description
            final_agents = agents
        
        # Scenario 4: Single agent (convenience)
        elif agent_type:
            if not task_description:
                raise ValueError("task_description is required for single agent requests")
                
            try:
                agent_enum = CodingAgentIdeType(agent_type.lower().strip())
            except ValueError:
                raise ValueError(f"Unsupported agent type: {agent_type}. Valid agent types are: {', '.join([e.value for e in CodingAgentIdeType])}")
            
            final_agents = [AgentDefinition(
                coding_ide=agent_enum.value,
                model=agent_model,
                role=agent_role
            )]
            final_task_description = task_description
        
        else:
            raise ValueError("Must provide one of: workflow_type, multi_agent_task, agents, or agent_type")
        
        return TaskRequest(
            task_description=final_task_description,
            agents=final_agents,
            workflow_type=final_workflow_type,
            repo_url=repo_url,
            target_dir=target_dir,
            create_pr=create_pr,
            work_directory=work_directory,
            delete_existing_repo_env=delete_existing_repo_env
        )
    
    @classmethod
    def _generate_workflow_prompt(cls, workflow_type: str, repo_url: str) -> str:
        """Generate workflow-specific prompts"""
        # Import workflow classes here to avoid circular imports
        from workflows.bug_hunting import BugHunter
        from workflows.code_optimization import CodeOptimizer
        from workflows.custom_coding import CustomCodingWorkflow
        from workflows.test_workflow import TestWorkflow
        
        workflow_instances = {
            'bugs': BugHunter(),
            'optimize': CodeOptimizer(),
            'refactor': CodeOptimizer(),
            'low-hanging': CodeOptimizer(),
            'custom': CustomCodingWorkflow(),
            'test': TestWorkflow()
        }
        
        if workflow_type not in workflow_instances:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        workflow_instance = workflow_instances[workflow_type]
        
        if workflow_type == 'bugs':
            return workflow_instance.generate_bug_hunting_prompt(repo_url)
        elif workflow_type == 'optimize':
            return workflow_instance.generate_performance_optimization_prompt(repo_url)
        elif workflow_type == 'refactor':
            return workflow_instance.generate_refactoring_prompt(repo_url)
        elif workflow_type == 'low-hanging':
            return workflow_instance.generate_low_hanging_fruit_prompt(repo_url)
        elif workflow_type == 'test':
            return workflow_instance.create_simple_hello_world_prompt()
        else:
            raise ValueError(f"Unsupported workflow in _generate_workflow_prompt: {workflow_type}")
    

    
    def _setup_work_directory(self, request: TaskRequest) -> str:
        """Setup and return the work directory for the request"""
        if request.work_directory:
            return request.work_directory
        
        if request.repo_url:
            # Clone repository if URL provided
            if request.target_dir:
                repo_path = request.target_dir
                success = clone_repository(request.repo_url, request.target_dir, request.delete_existing_repo_env)
                if not success:
                    raise Exception("Failed to clone repository")
            else:
                # Use default cloning logic
                repo_name = os.path.splitext(os.path.basename(request.repo_url.rstrip('/')))[0]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
                
                repo_path = os.path.join(self.base_dir, repo_name)
                success = clone_repository(request.repo_url, repo_path, request.delete_existing_repo_env)
                if not success:
                    raise Exception("Failed to clone repository")
            
            print(f"SUCCESS: Repository cloned to: {repo_path}")
            return repo_path
        else:
            # Use current directory if no repo URL
            return os.getcwd()
    
    def _create_role_specific_prompt(self, role: AgentRole, context: AgentContext, 
                                   agent_definition: AgentDefinition, 
                                   workflow_type: Optional[str] = None) -> str:
        """Create a role-specific prompt based on the agent's role and workflow type"""
        try:
            role_instance = RoleFactory.create_role(role)
            # Pass workflow_type to the role for workflow-specific prompt generation
            if hasattr(role_instance, 'create_prompt_with_workflow'):
                return role_instance.create_prompt_with_workflow(
                    context.task_description, context, agent_definition, workflow_type
                )
            else:
                # Fallback to standard prompt creation
                return role_instance.create_prompt(context.task_description, context, agent_definition)
        except ValueError as e:
            print(f"Warning: {e}. Using default coder prompt.")
            # Fallback to coder role for unknown roles
            coder_role = RoleFactory.create_role(AgentRole.CODER)
            return coder_role.create_prompt(context.task_description, context, agent_definition)
    
    async def _execute_agent(self, agent_definition: AgentDefinition, 
                            prompt: str, context: AgentContext, 
                            work_directory: str) -> Dict[str, Any]:
        """Execute an agent"""
        try:
            agent_type = CodingAgentIdeType(agent_definition.coding_ide.lower().strip())
        except ValueError:
            raise ValueError(f"Unsupported agent type: {agent_definition.coding_ide}. Valid agent types are: {', '.join([e.value for e in CodingAgentIdeType])}")
        
        # Get role instance for post-execution processing
        try:
            role_instance = RoleFactory.create_role(agent_definition.role)
        except ValueError:
            role_instance = None
        
        try:
            print(f"Executing {agent_definition.coding_ide} ({agent_definition.role.value})")
            
            # Change to work directory
            original_cwd = os.getcwd()
            os.chdir(work_directory)
            
            try:
                # Create and execute agent
                agent = AgentFactory.create_agent(agent_type, self.computer_use_client)
                
                # Set current project for window title checking
                agent.set_current_project(work_directory)
                
                # Check if agent interface is already open with correct project, if not open it
                if not await agent.is_coding_agent_open_with_project():
                    await agent.open_coding_interface()
                
                response = await agent.execute_prompt(prompt)
                
                result = {
                    "coding_ide": agent_definition.coding_ide,
                    "agent_model": agent_definition.model,
                    "role": agent_definition.role.value,
                    "success": response.success,
                    "output": response.content,
                    "error": response.error_message,
                    "timestamp": time.time()
                }
                
                # Apply role-specific post-execution processing
                if role_instance:
                    try:
                        result = role_instance.post_execution_hook(result, context)
                    except Exception as e:
                        print(f"Warning: Post-execution hook failed: {e}")
                
                if response.success:
                    print(f"{agent_definition.coding_ide} completed successfully")
                else:
                    print(f"{agent_definition.coding_ide} failed: {response.error_message}")
                
                # Close the coding interface for this project after task completion
                try:
                    print(f"Closing {agent_definition.coding_ide} interface for current project...")
                    close_success = await agent.close_coding_interface()
                    if close_success:
                        print(f"SUCCESS: {agent_definition.coding_ide} interface closed")
                    else:
                        print(f"WARNING: Failed to close {agent_definition.coding_ide} interface")
                except Exception as e:
                    print(f"WARNING: Error closing {agent_definition.coding_ide} interface: {str(e)}")
                
                return result
            
            finally:
                os.chdir(original_cwd)
                
        except Exception as e:
            error_msg = f"Exception executing {agent_definition.coding_ide}: {str(e)}"
            print(f"{error_msg}")
            
            return {
                "coding_ide": agent_definition.coding_ide,
                "agent_model": agent_definition.model,
                "role": agent_definition.role.value,
                "success": False,
                "output": "",
                "error": error_msg,
                "timestamp": time.time()
            }
    
    def save_agent_response(self, repo_url: Optional[str], agent_name: str, response: str) -> Optional[str]:
        """Save the agent response to a file"""
        try:
            # Generate filename
            if repo_url:
                repo_name = os.path.splitext(os.path.basename(repo_url.rstrip('/')))[0]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
            else:
                repo_name = "local_project"
            
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M")
            
            filename = f"{repo_name}_{date_str}_{time_str}.txt"
            filepath = os.path.join(self.responses_dir, filename)
            
            # Save response to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"SimulateDev Agent Response\n")
                f.write(f"{'='*50}\n")
                if repo_url:
                    f.write(f"Repository: {repo_url}\n")
                f.write(f"Agent: {agent_name}\n")
                f.write(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
                f.write(response)
            
            print(f"SUCCESS: Agent response saved to: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"WARNING: Failed to save agent response: {str(e)}")
            return None

    async def execute_task(self, request: TaskRequest) -> MultiAgentResponse:
        """Execute a task with one or more agents"""
        try:
            # Setup work directory
            work_directory = self._setup_work_directory(request)
            
            # Determine execution type for logging
            execution_type = f"{len(request.agents)}-Agent"
            if request.workflow_type:
                execution_type += f" ({request.workflow_type})"
            
            print(f"Starting {execution_type} execution")
            print(f"Task: {request.task_description}")
            print(f"Agents: {len(request.agents)}")
            print(f"Work Directory: {work_directory}")
            
            if request.repo_url:
                print(f"Repository: {request.repo_url}")
            
            # Initialize context
            context = AgentContext(
                task_description=request.task_description,
                previous_outputs=[],
                current_step=0,
                total_steps=len(request.agents),
                work_directory=work_directory
            )
            
            self.execution_log = []
            successful_executions = 0
            
            # Execute agents sequentially
            for i, agent_def in enumerate(request.agents):
                context.current_step = i + 1
                
                print(f"\n{'='*60}")
                print(f"Step {context.current_step}/{context.total_steps}: {agent_def.coding_ide} ({agent_def.role.value})")
                print(f"{'='*60}")
                
                # Create role-specific prompt with workflow context
                prompt = self._create_role_specific_prompt(
                    agent_def.role, context, agent_def, request.workflow_type
                )
                
                # Execute agent
                result = await self._execute_agent(
                    agent_def, prompt, context, work_directory
                )
                
                # Log execution
                self.execution_log.append(result)
                
                # Update context
                context.add_agent_output(
                    agent_def.coding_ide, agent_def.role, 
                    result["output"], result["success"]
                )
                
                if result["success"]:
                    successful_executions += 1
                else:
                    print(f"WARNING: Agent {agent_def.coding_ide} failed, continuing with remaining agents...")
            
            # Determine overall success
            overall_success = successful_executions > 0
            
            # Get final output (prefer Tester output, then Coder, then Planner)
            final_output = ""
            tester_output = context.get_latest_output_by_role(AgentRole.TESTER)
            coder_output = context.get_latest_output_by_role(AgentRole.CODER)
            planner_output = context.get_latest_output_by_role(AgentRole.PLANNER)
            
            if tester_output and tester_output["success"]:
                final_output = tester_output["output"]
            elif coder_output and coder_output["success"]:
                final_output = coder_output["output"]
            elif planner_output and planner_output["success"]:
                final_output = planner_output["output"]
            else:
                # Fallback to the last successful output
                for output in reversed(context.previous_outputs):
                    if output["success"]:
                        final_output = output["output"]
                        break
            
            # Extract test results if available
            test_results = None
            if tester_output:
                test_results = {
                    "executed": True,
                    "success": tester_output["success"],
                    "output": tester_output["output"]
                }
            
            # Save agent response
            if final_output:
                primary_agent = request.agents[0] if request.agents else None
                agent_name = primary_agent.coding_ide if primary_agent else "unknown"
                self.save_agent_response(request.repo_url, agent_name, final_output)
            
            # Create pull request if requested and we have a repo
            pr_url = None
            if request.create_pr and request.repo_url and overall_success:
                print("\nProcessing changes and creating pull request...")
                try:
                    # Construct agent information for PR description
                    agent_info_parts = []
                    for agent in request.agents:
                        agent_info_parts.append(f"{agent.coding_ide} with {agent.model} as {agent.role.value}")
                    coding_ides_info = ", ".join(agent_info_parts)
                    
                    pr_url = self.github_integration.smart_workflow(
                        repo_path=work_directory,
                        original_repo_url=request.repo_url,
                        workflow_name=f"{execution_type}",
                        agent_execution_report_summary=final_output[:1000] + "..." if len(final_output) > 1000 else final_output,
                        coding_ides_info=coding_ides_info,
                        task_description=request.task_description
                    )
                    
                    if pr_url:
                        print(f"SUCCESS: Pull request created: {pr_url}")
                        print("Opening pull request in your default browser...")
                        webbrowser.open(pr_url)
                    else:
                        print("WARNING: Pull request creation failed")
                except Exception as e:
                    print(f"WARNING: Pull request creation failed: {e}")
            
            print(f"\n{'='*60}")
            print(f"{execution_type.upper()} EXECUTION COMPLETE")
            print(f"Successful agents: {successful_executions}/{len(request.agents)}")
            print(f"Overall success: {overall_success}")
            if pr_url:
                print(f"Pull Request: {pr_url}")
            print(f"{'='*60}")
            
            response = MultiAgentResponse(
                success=overall_success,
                final_output=final_output,
                execution_log=self.execution_log,
                test_results=test_results
            )
            
            # Add PR URL to response if available
            if pr_url:
                response.pr_url = pr_url
            
            return response
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            print(f"{error_msg}")
            
            return MultiAgentResponse(
                success=False,
                final_output="",
                execution_log=self.execution_log,
                error_message=error_msg
            )
    
    def save_execution_report(self, response: MultiAgentResponse, 
                            output_file: str = "execution_report.json") -> str:
        """Save detailed execution report to file"""
        report = {
            "success": response.success,
            "final_output": response.final_output,
            "execution_log": response.execution_log,
            "test_results": response.test_results,
            "error_message": response.error_message,
            "timestamp": time.time()
        }
        
        # Add PR URL if available
        if hasattr(response, 'pr_url') and response.pr_url:
            report["pr_url"] = response.pr_url
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return output_file 