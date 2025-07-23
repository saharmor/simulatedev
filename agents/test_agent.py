#!/usr/bin/env python3
"""
Test Agent Implementation

A simple test agent that analyzes the codebase for inconsistencies and updates the README.
This agent is designed to test the pipeline functionality without requiring complex UI interactions.
This agent simulates the orchestrator's _execute_agent method behavior for testing purposes.
"""

import os
import time
from typing import Optional
from .base import CodingAgent, AgentResponse


class TestAgent(CodingAgent):
    """Test agent implementation for pipeline testing that simulates orchestrator behavior"""
    
    @property
    def window_name(self) -> str:
        return "Test Agent"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        return None  # Test agent is opened via command line
    
    @property
    def interface_state_prompt(self) -> str:
        return """You are analyzing a screenshot of a text editor or terminal interface showing codebase analysis results. 
Determine the test agent's current state based on visual cues in the interface. 
Return the following state for the following scenarios: 
'still_working' if you see text indicating analysis is in progress
'user_input_required' if the agent is waiting for user confirmation or input
'done' if the analysis appears complete and results are displayed
IMPORTANT: Respond with a JSON object containing exactly these two keys: 
- 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' 
- 'reasoning': a brief explanation for your decision 
Example response format: 
```json 
{ 
  "interface_state": "done", 
  "reasoning": "Analysis completed with results displayed" 
} 
``` 
Provide nothing but valid JSON in your response."""
    
    @property
    def resume_button_prompt(self) -> str:
        return "Resume button or continue option in the test agent interface (not typically used)"
    
    @property
    def input_field_prompt(self) -> str:
        return "Command prompt or input field in the terminal or text editor where commands can be entered for the test agent."
    
    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute the test agent analysis with orchestrator-like behavior"""
        print(f"Test Agent: Starting execution simulation...")
        print(f"Prompt received: {prompt}")
        
        try:
            # Simulate orchestrator's _execute_agent method behavior
            await self._simulate_orchestrator_execution(prompt)
            
            # Run the actual analysis
            await self._run_analysis(prompt)
            
            # Get and save results
            results = self._get_analysis_results()
            
            # Save to output file
            print(f"Test Agent: Saving results to {self.output_file}...")
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Test Agent Analysis Results\n\n")
                f.write(f"**Prompt:** {prompt}\n\n")
                f.write(f"**Analysis Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write("IMPORTANT: Do NOT create or update any documentation files (such as README.md or docs/*) unless you are explicitly asked to do so in the original prompt. If you believe that creating a documentation file would help you better implement the required coding task, you may create it, but you must delete it once you are finished and before you finish the task.\n\n")
                f.write(results)
            
            print("Test Agent: Analysis complete, results saved to file")
            
            # Read the file back
            content = await self._read_output_file()
            
            return AgentResponse(content=content, success=True)
            
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"Test agent failed: {str(e)}"
            )

    async def _simulate_orchestrator_execution(self, prompt: str):
        """Simulate the orchestrator's _execute_agent method behavior"""
        print("Test Agent: Simulating orchestrator execution behavior...")
        
        # Simulate getting current working directory (like orchestrator does)
        work_directory = os.getcwd()
        print(f"Test Agent: Current work directory: {work_directory}")
        
        # Simulate setting current project for window title checking (like orchestrator does)
        if self._current_project_name:
            print(f"Test Agent: Project name already set to: {self._current_project_name}")
        else:
            repo_name = os.path.basename(work_directory)
            self.set_current_project(work_directory)
            print(f"Test Agent: Set current project to: {repo_name}")
        
        # Simulate closing existing IDE windows (like orchestrator does at line 348-349)
        await self._simulate_close_ide_windows()
        
        # Simulate opening coding interface (like orchestrator does)
        await self._simulate_open_coding_interface()
        
        print("Test Agent: Orchestrator simulation complete")

    async def _simulate_close_ide_windows(self):
        """Simulate closing IDE windows like the orchestrator does"""
        print("Test Agent: Simulating IDE window closure...")
        
        if not self._current_project_name:
            print("Test Agent: No project name set, skipping window closure simulation")
            return
        
        # Simulate the orchestrator's behavior from lines 348-349
        repo_name = os.path.basename(os.getcwd())
        print(f"Test Agent: Simulating close_ide_window_for_project('{self.window_name}', '{repo_name}')")
        
        # For test agent, we don't actually close windows, just simulate the behavior
        print(f"Test Agent: [SIMULATED] Closing any existing {self.window_name} windows for project '{repo_name}'")
        
        # Simulate the 2-second wait like in the orchestrator
        print("Test Agent: [SIMULATED] Waiting 2 seconds for window to close completely...")
        time.sleep(2)
        
        print("Test Agent: IDE window closure simulation complete")

    async def _simulate_open_coding_interface(self):
        """Simulate opening the coding interface like the orchestrator does"""
        print("Test Agent: Simulating coding interface opening...")
        
        # Simulate checking if interface is already open
        interface_open = await self.is_coding_agent_open_with_project()
        
        if interface_open:
            print("Test Agent: [SIMULATED] Interface already open with correct project")
        else:
            print("Test Agent: [SIMULATED] Opening coding interface...")
            # The actual opening is handled by our open_coding_interface method
            opened = await self.open_coding_interface()
            if not opened:
                raise Exception("Test Agent: [SIMULATED] Failed to open coding interface")
            print("Test Agent: [SIMULATED] Coding interface opened successfully")
        
        print("Test Agent: Coding interface simulation complete")

    async def is_coding_agent_open(self) -> bool:
        """Check if test agent is running (always returns True for simplicity)"""
        print("Test Agent: Checking if agent is running...")
        return True  # Test agent is always "running" since it's just a script

    async def is_coding_agent_open_with_project(self) -> bool:
        """Check if test agent is running with correct project (always returns True for simplicity)"""
        print("Test Agent: Checking if agent is running with correct project...")
        if self._current_project_name:
            print(f"Test Agent: Current project is set to: {self._current_project_name}")
            return True
        else:
            print("Test Agent: No current project set")
            return False

    async def open_coding_interface(self) -> bool:
        """Open test agent interface (no actual interface needed)"""
        print("Test Agent: Opening interface...")
        print("Test Agent: Interface ready")
        return True

    async def close_coding_interface(self) -> bool:
        """Close test agent interface (no actual interface to close)"""
        print("Test Agent: Closing interface...")
        print("Test Agent: Interface closed (no persistent interface to close)")
        return True

    async def _run_analysis(self, prompt: str):
        """Run the actual codebase analysis"""
        print("Test Agent: Analyzing codebase structure...")
        
        # Analyze the codebase
        analysis_results = []
        
        # Check for common inconsistencies
        analysis_results.extend(self._check_agent_registration())
        analysis_results.extend(self._check_readme_accuracy())
        analysis_results.extend(self._check_file_consistency())
        
        # Store results for later retrieval
        self._analysis_results = analysis_results
        
        print(f"Test Agent: Found {len(analysis_results)} potential inconsistencies")

    def _check_agent_registration(self) -> list:
        """Check if all agents are properly registered"""
        issues = []
        
        try:
            # Check if all agent files have corresponding entries in factory.py
            agent_files = []
            agents_dir = "agents"
            
            if os.path.exists(agents_dir):
                for file in os.listdir(agents_dir):
                    if file.endswith("_agent.py") and file != "base.py":
                        agent_files.append(file)
            
            # Check factory.py for missing agents
            with open("agents/factory.py", "r") as f:
                factory_content = f.read()
            
            for agent_file in agent_files:
                agent_name = agent_file.replace("_agent.py", "").replace("_", "")
                if agent_name not in factory_content.lower():
                    issues.append(f"Agent {agent_file} may not be registered in factory.py")
                    
        except Exception as e:
            issues.append(f"Error checking agent registration: {str(e)}")
            
        return issues

    def _check_readme_accuracy(self) -> list:
        """Check if README mentions all available agents"""
        issues = []
        
        try:
            # Get list of agent files
            agent_files = []
            if os.path.exists("agents"):
                for file in os.listdir("agents"):
                    if file.endswith("_agent.py") and file != "base.py":
                        agent_name = file.replace("_agent.py", "").replace("_", " ").title()
                        agent_files.append(agent_name)
            
            # Check README content
            if os.path.exists("README.md"):
                with open("README.md", "r") as f:
                    readme_content = f.read().lower()
                
                for agent in agent_files:
                    if agent.lower() not in readme_content:
                        issues.append(f"README.md does not mention the {agent} agent")
            else:
                issues.append("README.md file not found")
                
        except Exception as e:
            issues.append(f"Error checking README accuracy: {str(e)}")
            
        return issues

    def _check_file_consistency(self) -> list:
        """Check for general file consistency issues"""
        issues = []
        
        try:
            # Check if all Python files have proper headers
            for root, dirs, files in os.walk("."):
                # Skip venv and other common directories
                dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules']]
                
                for file in files:
                    if file.endswith(".py") and not file.startswith("."):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r") as f:
                                first_line = f.readline().strip()
                                if not first_line.startswith("#!") and not first_line.startswith('"""') and not first_line.startswith("'''"):
                                    issues.append(f"{file_path} missing proper header or docstring")
                        except Exception:
                            pass  # Skip files that can't be read
                            
        except Exception as e:
            issues.append(f"Error checking file consistency: {str(e)}")
            
        return issues

    def _get_analysis_results(self) -> str:
        """Format and return analysis results"""
        if not hasattr(self, '_analysis_results'):
            return "No analysis results available"
        
        if not self._analysis_results:
            return "No inconsistencies found! The codebase appears to be well-structured."
        
        results = "## Test Agent Analysis Results\n\n"
        results += f"Found {len(self._analysis_results)} potential issues:\n\n"
        
        for i, issue in enumerate(self._analysis_results, 1):
            results += f"{i}. {issue}\n"
        
        results += "\n---\n\n"
        results += "Consider updating the README.md to reflect these findings.\n"
        results += "This analysis helps ensure the codebase documentation stays current."
        
        return results 