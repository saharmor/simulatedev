#!/usr/bin/env python3
"""
Unified Orchestrator Module

This module provides a unified interface for both single-agent and multi-agent workflows.
Single-agent workflows are treated as a special case of multi-agent workflows with one coder agent.
"""

import os
import json
import time
import webbrowser
from typing import Optional, Dict, Any, List, Union
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
from workflows.bug_hunting import BugHunter
from workflows.code_optimization import CodeOptimizer
from workflows.general_coding import GeneralCodingWorkflow


@dataclass
class UnifiedRequest:
    """Unified request structure for both single and multi-agent workflows"""
    task_description: str
    agents: List[AgentDefinition]
    repo_url: Optional[str] = None
    target_dir: Optional[str] = None
    create_pr: bool = True
    work_directory: Optional[str] = None
    workflow: Optional[str] = None
    coding_task_prompt: Optional[str] = None  # For general_coding workflow


class UnifiedOrchestrator:
    """Unified orchestrator for both single-agent and multi-agent workflows"""
    
    def __init__(self):
        self.computer_use_client = ClaudeComputerUse()
        self.github_integration = GitHubIntegration()
        self.execution_log = []
        
        # Create necessary directories
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos")
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.responses_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CodingAgentResponses")
        os.makedirs(self.responses_dir, exist_ok=True)
    
    @classmethod
    def create_single_agent_request(cls, task_description: str, agent_type: Union[str, CodingAgentIdeType], 
                                  repo_url: Optional[str] = None, target_dir: Optional[str] = None,
                                  create_pr: bool = True, work_directory: Optional[str] = None) -> UnifiedRequest:
        """
        Create a single-agent request (convenience method for backward compatibility)
        
        Args:
            task_description: The coding task to perform
            agent_type: The agent type (string or CodingAgentIdeType enum)
            repo_url: Optional repository URL to clone
            target_dir: Optional target directory for cloning
            create_pr: Whether to create a pull request
            work_directory: Optional work directory override
            
        Returns:
            UnifiedRequest: A unified request with one coder agent
        """
        # Convert string to CodingAgentIdeType if needed
        if isinstance(agent_type, str):
            try:
                agent_type = CodingAgentIdeType(agent_type.lower().strip())
            except ValueError:
                raise ValueError(f"Unsupported agent type: {agent_type}. Valid agent types are: {', '.join([e.value for e in CodingAgentIdeType])}")
        
        # Create a single coder agent
        agent_def = AgentDefinition(
            coding_ide=agent_type.value,
            model="N/A",  # Default model
            role=AgentRole.CODER
        )
        
        return UnifiedRequest(
            task_description=task_description,
            agents=[agent_def],
            repo_url=repo_url,
            target_dir=target_dir,
            create_pr=create_pr,
            work_directory=work_directory
        )
    
    @classmethod
    def create_multi_agent_request(cls, task: MultiAgentTask, repo_url: Optional[str] = None,
                                 target_dir: Optional[str] = None, create_pr: bool = True,
                                 work_directory: Optional[str] = None) -> UnifiedRequest:
        """
        Create a multi-agent request from a MultiAgentTask
        
        Args:
            task: The multi-agent task definition
            repo_url: Optional repository URL to clone (overrides task.repo_url if provided)
            target_dir: Optional target directory for cloning
            create_pr: Whether to create a pull request
            work_directory: Optional work directory override
            
        Returns:
            UnifiedRequest: A unified request with multiple agents
        """
        # Use provided repo_url or fall back to task.repo_url
        effective_repo_url = repo_url or task.repo_url
        
        return UnifiedRequest(
            task_description=task.get_task_description(),
            agents=task.agents,
            repo_url=effective_repo_url,
            target_dir=target_dir,
            create_pr=create_pr,
            work_directory=work_directory,
            workflow=task.workflow,
            coding_task_prompt=task.coding_task_prompt
        )
    

    
    def _setup_work_directory(self, request: UnifiedRequest) -> str:
        """Setup and return the work directory for the request"""
        if request.work_directory:
            return request.work_directory
        
        if request.repo_url:
            # Clone repository if URL provided
            if request.target_dir:
                repo_path = request.target_dir
                success = clone_repository(request.repo_url, request.target_dir)
                if not success:
                    raise Exception("Failed to clone repository")
            else:
                # Use default cloning logic
                repo_name = os.path.splitext(os.path.basename(request.repo_url.rstrip('/')))[0]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
                
                repo_path = os.path.join(self.base_dir, repo_name)
                success = clone_repository(request.repo_url, repo_path)
                if not success:
                    raise Exception("Failed to clone repository")
            
            print(f"SUCCESS: Repository cloned to: {repo_path}")
            return repo_path
        else:
            # Use current directory if no repo URL
            return os.getcwd()
    
    def _create_role_specific_prompt(self, role: AgentRole, context: AgentContext, 
                                   agent_definition: AgentDefinition) -> str:
        """Create a role-specific prompt based on the agent's role"""
        try:
            role_instance = RoleFactory.create_role(role)
            return role_instance.create_prompt(context.task_description, context, agent_definition)
        except ValueError as e:
            print(f"Warning: {e}. Using default coder prompt.")
            # Fallback to coder role for unknown roles
            coder_role = RoleFactory.create_role(AgentRole.CODER)
            return coder_role.create_prompt(context.task_description, context, agent_definition)
    
    async def _execute_agent_with_retry(self, agent_definition: AgentDefinition, 
                                      prompt: str, context: AgentContext, 
                                      work_directory: str) -> Dict[str, Any]:
        """Execute an agent with retry logic"""
        try:
            agent_type = CodingAgentIdeType(agent_definition.coding_ide.lower().strip())
        except ValueError:
            raise ValueError(f"Unsupported agent type: {agent_definition.coding_ide}. Valid agent types are: {', '.join([e.value for e in CodingAgentIdeType])}")
        
        # Get role-specific configuration
        try:
            role_instance = RoleFactory.create_role(agent_definition.role)
            max_retries = role_instance.get_max_retries()
            should_retry = role_instance.should_retry_on_failure()
        except ValueError:
            # Fallback to default values
            max_retries = 1
            should_retry = True
        
        for attempt in range(max_retries + 1):
            try:
                print(f"Executing {agent_definition.coding_ide} ({agent_definition.role.value}) - Attempt {attempt + 1}")
                
                # Change to work directory
                original_cwd = os.getcwd()
                os.chdir(work_directory)
                
                try:
                    # Create and execute agent
                    agent = AgentFactory.create_agent(agent_type, self.computer_use_client)
                    
                    # Check if agent interface is already open, if not open it
                    if not await agent.is_coding_agent_open():
                        await agent.open_coding_interface()
                    
                    response = await agent.execute_prompt(prompt)
                    
                    result = {
                        "coding_ide": agent_definition.coding_ide,
                        "agent_model": agent_definition.model,
                        "role": agent_definition.role.value,
                        "attempt": attempt + 1,
                        "success": response.success,
                        "output": response.content,
                        "error": response.error_message,
                        "timestamp": time.time()
                    }
                    
                    # Apply role-specific post-execution processing
                    try:
                        result = role_instance.post_execution_hook(result, context)
                    except Exception as e:
                        print(f"Warning: Post-execution hook failed: {e}")
                    
                    if response.success:
                        print(f"{agent_definition.coding_ide} completed successfully")
                        return result
                    else:
                        print(f"{agent_definition.coding_ide} failed: {response.error_message}")
                        if attempt < max_retries and should_retry:
                            print(f"Retrying {agent_definition.coding_ide}...")
                        else:
                            return result
                
                finally:
                    os.chdir(original_cwd)
                    
            except Exception as e:
                error_msg = f"Exception executing {agent_definition.coding_ide}: {str(e)}"
                print(f"{error_msg}")
                
                if attempt >= max_retries:
                    return {
                        "coding_ide": agent_definition.coding_ide,
                        "agent_model": agent_definition.model,
                        "role": agent_definition.role.value,
                        "attempt": attempt + 1,
                        "success": False,
                        "output": "",
                        "error": error_msg,
                        "timestamp": time.time()
                    }
        
        # Should not reach here, but just in case
        return {
            "coding_ide": agent_definition.coding_ide,
            "agent_model": agent_definition.model,
            "role": agent_definition.role.value,
            "attempt": max_retries + 1,
            "success": False,
            "output": "",
            "error": "Maximum retries exceeded",
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
    
    async def _execute_workflow(self, request: UnifiedRequest, work_directory: str) -> str:
        """Execute a specific workflow if specified"""
        if not request.workflow:
            return None
            
        print(f"Executing workflow: {request.workflow}")
        
        # Get the primary agent (first one)
        primary_agent = request.agents[0] if request.agents else None
        if not primary_agent:
            raise ValueError("No agents specified for workflow execution")
            
        try:
            agent_type = CodingAgentIdeType(primary_agent.coding_ide.lower().strip())
        except ValueError:
            raise ValueError(f"Unsupported agent type: {primary_agent.coding_ide}. Valid agent types are: {', '.join([e.value for e in CodingAgentIdeType])}")
        
        if request.workflow == "bug_hunting":
            workflow = BugHunter()
            return await workflow.hunt_bugs(agent_type, request.repo_url, work_directory)
            
        elif request.workflow == "code_optimization":
            workflow = CodeOptimizer()
            return await workflow.optimize_performance(agent_type, request.repo_url, work_directory)
            
        elif request.workflow == "general_coding":
            workflow = GeneralCodingWorkflow()
            if request.coding_task_prompt:
                # Use the custom prompt provided
                return await workflow.execute_simple_task(agent_type, request.repo_url, request.coding_task_prompt, work_directory)
            else:
                # This shouldn't happen due to validation, but fallback to task description
                return await workflow.execute_coding_task(agent_type, request.repo_url, request.task_description, work_directory)
                
        else:
            raise ValueError(f"Unknown workflow: {request.workflow}")

    async def execute_unified_request(self, request: UnifiedRequest) -> MultiAgentResponse:
        """Execute a unified request (single or multi-agent)"""
        try:
            # Setup work directory
            work_directory = self._setup_work_directory(request)
            
            # Check if this is a workflow execution
            if request.workflow:
                print(f"Starting workflow execution: {request.workflow}")
                print(f"Task: {request.task_description}")
                print(f"Work Directory: {work_directory}")
                
                if request.repo_url:
                    print(f"Repository: {request.repo_url}")
                
                # Execute the workflow
                workflow_output = await self._execute_workflow(request, work_directory)
                
                # Create a simple response for workflow execution
                response = MultiAgentResponse(
                    success=True,
                    final_output=workflow_output,
                    execution_log=[{
                        "workflow": request.workflow,
                        "output": workflow_output,
                        "success": True
                    }]
                )
                
                # Handle PR creation for workflow
                if request.create_pr and request.repo_url:
                    print("\nProcessing changes and creating pull request...")
                    try:
                        pr_url = self.github_integration.smart_workflow(
                            repo_path=work_directory,
                            original_repo_url=request.repo_url,
                            agent_name=f"{request.workflow}-workflow",
                            agent_execution_report_summary=workflow_output[:1000] + "..." if len(workflow_output) > 1000 else workflow_output
                        )
                        
                        if pr_url:
                            print(f"SUCCESS: Pull request created: {pr_url}")
                            print("Opening pull request in your default browser...")
                            webbrowser.open(pr_url)
                            response.pr_url = pr_url
                        else:
                            print("WARNING: Pull request creation failed")
                    except Exception as e:
                        print(f"WARNING: Pull request creation failed: {e}")
                
                return response
            
            # Determine if this is single or multi-agent
            is_single_agent = len(request.agents) == 1 and request.agents[0].role == AgentRole.CODER
            workflow_type = "Single-Agent" if is_single_agent else "Multi-Agent"
            
            print(f"Starting {workflow_type} execution")
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
                
                # Create role-specific prompt
                prompt = self._create_role_specific_prompt(agent_def.role, context, agent_def)
                
                # Execute agent with retry
                result = await self._execute_agent_with_retry(
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
                    pr_url = self.github_integration.smart_workflow(
                        repo_path=work_directory,
                        original_repo_url=request.repo_url,
                        agent_name=f"{workflow_type} ({len(request.agents)} agents)",
                        agent_execution_report_summary=final_output[:1000] + "..." if len(final_output) > 1000 else final_output
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
            print(f"{workflow_type.upper()} EXECUTION COMPLETE")
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
            error_msg = f"{workflow_type} execution failed: {str(e)}"
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
        
        print(f"Execution report saved to: {output_file}")
        return output_file 