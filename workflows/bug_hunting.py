#!/usr/bin/env python3
"""
Bug Hunting Module

This module provides specialized functionality for AI-powered bug discovery,
extending the agent orchestrator with bug-specific prompts and workflows.
"""

import pyautogui
import time
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_orchestrator import AgentOrchestrator
from coding_agents import CodingAgentType


class BugHunter(AgentOrchestrator):
    """Specialized orchestrator for bug hunting workflows"""
    
    def generate_bug_hunting_prompt(self, repo_url: str) -> str:
        """Generate a bug hunting prompt for the specified repository"""
        return f"""You are a world-class developer analyzing code for bugs. Respond only with a JSON array of bug findings.

<output_format>
{{
    "bugs": [
        {{
            "file": "string", 
            "lines": "string (clickable link to {repo_url}/blob/main/FILE#L1-L2)",
            "bug_type": "string (security/memory/efficiency/etc)",
            "description": "string",
            "implications": "string", 
            "fix": "string"
        }}
    ]
}}
</output_format>

My colleague told me they found three bugs in this codebase. One of them is extremely severe. Find those bugs and return them in the specified JSON format above. Make sure the lines field generates clickable GitHub links.
ONLY RETURN THE JSON ARRAY. NOTHING ELSE."""

    async def hunt_bugs(self, agent_type: CodingAgentType, repo_url: str, project_path: str = None) -> str:
        """Execute a complete bug hunting workflow"""
        prompt = self.generate_bug_hunting_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)
    
    async def type_bug_hunting_prompt_legacy(self, input_field_coordinates: tuple, repo_url: str):
        """Legacy method for typing bug hunting prompt (kept for backward compatibility)"""
        prompt = self.generate_bug_hunting_prompt(repo_url)
        
        # Move to the input field
        print(f"Moving to input field at ({input_field_coordinates.x}, {input_field_coordinates.y})...")
        pyautogui.moveTo(input_field_coordinates.x, input_field_coordinates.y, duration=1.0)
        time.sleep(0.5)  # Wait for mouse movement
        pyautogui.click(input_field_coordinates.x, input_field_coordinates.y)
        time.sleep(1.0)  # Wait longer for focus
        
        print("Typing prompt...")
        # Type the prompt line by line, inserting a newline break (Shift+Enter) after each line
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            pyautogui.write(line)
            if i < len(lines) - 1:  # Don't add newline after last line
                pyautogui.hotkey('shift', 'enter')  # inserts a line break without submitting

        pyautogui.press('enter')
        time.sleep(1.0)  # Wait longer before pressing Enter


def clean_input_box():
    """Clean the input box using keyboard shortcuts"""
    pyautogui.hotkey('command', 'a')
    pyautogui.hotkey('command', 'backspace')


def open_agentic_coding_interface():
    """Open the agentic coding interface using keyboard shortcut"""
    # TODO: add check if the agentic coding interface is not already open
    pyautogui.hotkey('command', 'l') 