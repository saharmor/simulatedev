#!/usr/bin/env python3
"""
Test Agent Implementation

A simple test agent that analyzes the codebase for inconsistencies and updates the README.
This agent is designed to test the pipeline functionality without requiring complex UI interactions.
"""

import time
import os
import subprocess
import pyautogui
import pyperclip
from typing import Optional
from .base import CodingAgent


class TestAgent(CodingAgent):
    """Test agent implementation for pipeline testing"""
    
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
    def input_field_prompt(self) -> str:
        return "Command prompt or input field in the terminal or text editor where commands can be entered for the test agent."
    
    @property
    def copy_button_prompt(self) -> str:
        return "Copy button, copy icon, or text selection area where analysis results can be copied from the test agent interface."
    
    async def send_prompt(self, prompt: str):
        """Send a prompt to the test agent (simulates running analysis)"""
        print(f"Test Agent: Running codebase analysis...")
        print(f"Prompt received: {prompt}")
        
        # Simulate analysis by running the test agent script
        await self._run_analysis(prompt)
        
        # Copy results to clipboard
        results = self._get_analysis_results()
        pyperclip.copy(results)
        print("Test Agent: Analysis complete, results copied to clipboard")

    async def is_coding_agent_open(self) -> bool:
        """Check if test agent is running (always returns True for simplicity)"""
        print("Test Agent: Checking if agent is running...")
        return True  # Test agent is always "running" since it's just a script

    async def open_coding_interface(self) -> bool:
        """Open test agent interface (no actual interface needed)"""
        print("Test Agent: Opening interface...")
        print("Test Agent: Interface ready")
        return True

    async def _run_analysis(self, prompt: str):
        """Run the actual codebase analysis"""
        print("Test Agent: Analyzing codebase structure...")
        
        # Get current directory
        repo_dir = os.getcwd()
        
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
            return "✅ No inconsistencies found! The codebase appears to be well-structured."
        
        results = "🔍 Test Agent Analysis Results\n"
        results += "=" * 35 + "\n\n"
        results += f"Found {len(self._analysis_results)} potential issues:\n\n"
        
        for i, issue in enumerate(self._analysis_results, 1):
            results += f"{i}. {issue}\n"
        
        results += "\n" + "=" * 35 + "\n"
        results += "💡 Consider updating the README.md to reflect these findings.\n"
        results += "This analysis helps ensure the codebase documentation stays current."
        
        return results 