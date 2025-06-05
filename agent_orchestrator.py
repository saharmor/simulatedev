#!/usr/bin/env python3
"""
Agent Orchestrator Module

This module provides high-level orchestration for AI coding agents,
handling IDE management, repository operations, and agent workflow coordination.
"""

import os
import time
import subprocess
from urllib.parse import urlparse
from computer_use_utils import ClaudeComputerUse, bring_to_front_window, wait_for_focus
from coding_agents import AgentFactory, WindsurfAgent, CodingAgentType


class AgentOrchestrator:
    """High-level orchestrator for AI coding agent operations"""
    
    def __init__(self):
        self.claude = ClaudeComputerUse()
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos")
        os.makedirs(self.base_dir, exist_ok=True)
    
    def get_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL"""
        return os.path.splitext(os.path.basename(urlparse(repo_url).path))[0]
    
    def clone_repository(self, repo_url: str) -> str:
        """Clone the repository and return the local path"""
        repo_name = self.get_repo_name(repo_url)
        local_path = os.path.join(self.base_dir, repo_name)
        
        # Check if directory exists and is a valid git repository
        if os.path.exists(local_path) and os.path.isdir(os.path.join(local_path, '.git')):
            print(f"Repository already exists at {local_path}")
            return local_path
            
        # Remove directory if it exists but isn't a valid git repo
        if os.path.exists(local_path):
            import shutil
            print(f"Removing invalid repository directory at {local_path}")
            shutil.rmtree(local_path)
            
        print(f"Cloning repository to {local_path}...")
        subprocess.run(["git", "clone", repo_url, local_path], check=True)
        return local_path
    
    
    
    async def open_ide(self, agent_type: CodingAgentType, project_path: str, repo_name: str):
        """Open the specified IDE with the project"""
        print(f"Opening IDE: {agent_type.value} with project path: {project_path}")
        
        # Create agent instance
        agent = AgentFactory.create_agent(agent_type, self.claude)
        window_name = agent.window_name
        
        try:
            subprocess.run(["open", "-a", window_name, project_path])
            print("Waiting 3 seconds for app to start...")
            time.sleep(3)  # wait for the app to start
            
            activate_script = f'''
            tell application "{window_name}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", activate_script], check=True)
            time.sleep(1)
            

            ide_open_success = bring_to_front_window(window_name, repo_name)
            if not ide_open_success:
                print("Error: IDE failed to open or gain focus")
                raise Exception("IDE did not open or focus")
            
            # Handle Windsurf-specific popup
            if isinstance(agent, WindsurfAgent):
                await agent.handle_trust_workspace_popup()
                
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not set window to full screen: {str(e)}")
            print(f"Attempting fallback open command for {window_name}...")
            subprocess.run(["open", "-na", window_name, project_path])
            print("Waiting 5 seconds after fallback open...")
            time.sleep(5)

    async def send_prompt_to_agent(self, agent_type: CodingAgentType, prompt: str):
        """Send a prompt to the specified agent"""
        agent = AgentFactory.create_agent(agent_type, self.claude)
        await agent.send_prompt(prompt)
    
    async def get_agent_response(self, agent_type: CodingAgentType):
        """Get the response from the agent"""
        agent = AgentFactory.create_agent(agent_type, self.claude)
        response = await agent.read_agent_output()
        
        if response.success:
            return response.content
        else:
            raise Exception(f"Failed to read agent output: {response.error_message}")
    
    async def wait_for_agent_completion(self, agent_type: CodingAgentType, timeout_seconds: int = 300):
        """Wait for the agent to complete processing"""
        from ide_completion_detector import wait_until_ide_finishes
        agent = AgentFactory.create_agent(agent_type, self.claude)
        await wait_until_ide_finishes(agent_type.value, agent.interface_state_prompt, timeout_seconds)
    
    async def execute_workflow(self, agent_type: CodingAgentType, repo_url: str, prompt: str, 
                              project_path: str = None) -> str:
        """Execute a complete workflow: open IDE, send prompt, wait for completion, get response"""
        try:
            # Step 1: Clone repository if no project path provided
            if not project_path:
                project_path = self.clone_repository(repo_url)
            
            # Step 2: Open IDE
            repo_name = self.get_repo_name(repo_url)
            await self.open_ide(agent_type, project_path, repo_name)
            
            # Step 3: Send prompt
            await self.send_prompt_to_agent(agent_type, prompt)
            
            # Step 4: Wait for completion
            await self.wait_for_agent_completion(agent_type)
            
            # Step 5: Get response
            response = await self.get_agent_response(agent_type)
            
            return response
            
        except Exception as e:
            raise Exception(f"Workflow execution failed: {str(e)}") 