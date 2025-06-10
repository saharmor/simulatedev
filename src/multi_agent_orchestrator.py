#!/usr/bin/env python3
"""
Multi-Agent Orchestrator Module

This module coordinates multiple AI agents working in different roles (Planner, Coder, Tester)
to solve coding tasks collaboratively through sequential execution and context passing.
"""

import os
import json
import time
from typing import Dict, Any
from utils.computer_use_utils import ClaudeComputerUse
from agents import (
    AgentFactory, CodingAgentIdeType, AgentRole, MultiAgentTask, 
    AgentDefinition, AgentContext, MultiAgentResponse
)
from roles import RoleFactory


class MultiAgentOrchestrator:
    """Orchestrator for multi-agent collaborative workflows"""
    
    def __init__(self):
        self.claude = ClaudeComputerUse()
        self.execution_log = []
        
    def _map_coding_ide_to_type(self, coding_ide: str) -> CodingAgentIdeType:
        """Map agent name from JSON to CodingAgentType enum"""
        try:
            return CodingAgentIdeType(coding_ide.lower().strip())
        except ValueError:
            raise ValueError(f"Unsupported coding IDE: {coding_ide}. "
                           f"Supported IDEs: {[ide.value for ide in CodingAgentIdeType]}")
    
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
        agent_type = self._map_coding_ide_to_type(agent_definition.coding_ide)
        
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
                    agent = AgentFactory.create_agent(agent_type, self.claude)
                    
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
    
    async def execute_multi_agent_task(self, task: MultiAgentTask, 
                                     work_directory: str = None) -> MultiAgentResponse:
        """Execute a multi-agent task with sequential role-based coordination"""
        try:
            # Setup work directory
            if not work_directory:
                work_directory = os.getcwd()
            
            print(f"Starting multi-agent task execution")
            print(f"Task: {task.task}")
            print(f"Agents: {len(task.agents)}")
            print(f"Work Directory: {work_directory}")
            
            # Initialize context
            context = AgentContext(
                task_description=task.task,
                previous_outputs=[],
                current_step=0,
                total_steps=len(task.agents),
                work_directory=work_directory
            )
            
            self.execution_log = []
            successful_executions = 0
            
            # Execute agents sequentially
            for i, agent_def in enumerate(task.agents):
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
            
            print(f"\n{'='*60}")
            print(f"MULTI-AGENT EXECUTION COMPLETE")
            print(f"Successful agents: {successful_executions}/{len(task.agents)}")
            print(f"Overall success: {overall_success}")
            print(f"{'='*60}")
            
            return MultiAgentResponse(
                success=overall_success,
                final_output=final_output,
                execution_log=self.execution_log,
                test_results=test_results
            )
            
        except Exception as e:
            error_msg = f"Multi-agent execution failed: {str(e)}"
            print(f"{error_msg}")
            
            return MultiAgentResponse(
                success=False,
                final_output="",
                execution_log=self.execution_log,
                error_message=error_msg
            )
    
    def save_execution_report(self, response: MultiAgentResponse, 
                            output_file: str = "multi_agent_execution_report.json") -> str:
        """Save detailed execution report to file"""
        report = {
            "success": response.success,
            "final_output": response.final_output,
            "execution_log": response.execution_log,
            "test_results": response.test_results,
            "error_message": response.error_message,
            "timestamp": time.time()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Execution report saved to: {output_file}")
        return output_file 