#!/usr/bin/env python3
"""
Base classes and shared components for coding agents.
"""

import time
import pyautogui
import pyperclip
import json
import os
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class CodingAgentType(Enum):
    """Enum for supported coding agents"""
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    CLAUDE_CODE = "claude_code"
    TEST = "test"


@dataclass
class AgentResponse:
    """Response from an AI coding agent"""
    content: str
    success: bool
    error_message: Optional[str] = None


class CodingAgent(ABC):
    """Abstract base class for AI coding agents"""
    
    def __init__(self, claude_computer_use):
        self.claude = claude_computer_use
        self.agent_name = self.__class__.__name__.lower().replace('agent', '')
        self.output_file = "agent_execution_output.md"
    
    @property
    @abstractmethod
    def window_name(self) -> str:
        """The application window name for opening the IDE"""
        pass
    
    @property
    @abstractmethod
    def interface_state_prompt(self) -> str:
        """Prompt for analyzing the agent's interface state"""
        pass
    
    @property
    @abstractmethod
    def resume_button_prompt(self) -> str:
        """Prompt for finding the resume button coordinates"""
        pass
    
    @property
    @abstractmethod
    def input_field_prompt(self) -> str:
        """Prompt for finding the input field coordinates"""
        pass
    
    @property
    @abstractmethod
    def copy_button_prompt(self) -> str:
        """Prompt for finding the copy button coordinates"""
        pass
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        """Optional keyboard shortcut to open the agent interface"""
        return None
    
    @abstractmethod
    async def is_coding_agent_open(self) -> bool:
        """Check if the agent is currently running and ready to accept commands
        
        Each agent should implement its own logic for checking if it's running.
        This could involve checking for specific windows, processes, or interface elements.
        
        Returns:
            bool: True if the agent is running and ready, False otherwise
        """
        pass
    
    @abstractmethod
    async def open_coding_interface(self) -> bool:
        """Open the agent's coding interface and ensure it's ready to accept commands
        
        Each agent should implement its own logic for:
        1. Checking if already running (using is_agent_running())
        2. Opening the interface if not running
        3. Handling any setup popups or prompts
        4. Verifying the interface is ready
        
        Returns:
            bool: True if interface is open and ready, False otherwise
        """
        pass
    
    async def get_input_field_coordinates(self):
        """Get the coordinates of the input field"""
        result = await self.claude.get_coordinates_from_claude(self.input_field_prompt)
        return result
    
    async def get_copy_button_coordinates(self):
        """Get the coordinates of the copy button"""
        result = await self.claude.get_coordinates_from_claude(self.copy_button_prompt)
        return result
    
    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute the complete workflow: send prompt -> wait -> save to file -> return content
        
        This is the main method that orchestrates the entire agent interaction.
        """
        try:
            # Step 1: Send the prompt
            print(f"Sending prompt to {self.agent_name}...")
            await self._send_prompt_to_interface(prompt)
            # wait for 5 seconds to make sure the prompt is sent
            time.sleep(5)

            # Step 2: Wait for completion
            print(f"Waiting for {self.agent_name} to complete...")
            await self._wait_for_completion()
            
            # Step 3: Ask agent to save output
            print(f"Asking {self.agent_name} to save output to {self.output_file}...")
            save_prompt = f"""Save a comprehensive summary of everything you did to a file called '{self.output_file}' in the current directory. Include:
- All changes made
- Explanations of what was done
"""
            await self._send_prompt_to_interface(save_prompt)
            time.sleep(3)

            # Wait a bit for file save operation (use shorter timeout for file save)
            await self._wait_for_completion(timeout_seconds=120)
            
            # Step 4: Read the file
            print(f"Reading output from {self.output_file}...")
            content = await self._read_output_file()
            
            return AgentResponse(content=content, success=True)
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"Failed to execute prompt: {str(e)}"
            )
    
    async def _send_prompt_to_interface(self, prompt: str):
        """Send a prompt to the agent interface (GUI-based implementation)"""
        # Get input field coordinates
        input_coords = await self.get_input_field_coordinates()
        if not input_coords:
            raise Exception(f"Could not locate {self.agent_name} input field")
        
        # Click the input field
        print(f"Moving to {self.agent_name} input field...")
        pyautogui.moveTo(input_coords.coordinates.x, input_coords.coordinates.y, duration=0.5)
        time.sleep(0.5)
        pyautogui.click(input_coords.coordinates.x, input_coords.coordinates.y)
        time.sleep(1.0)
        
        # Copy prompt to clipboard and paste it
        print(f"Pasting prompt into {self.agent_name}...")
        pyperclip.copy(prompt)
        time.sleep(0.5)
        
        # Paste the prompt using Cmd+V on macOS
        pyautogui.hotkey('command', 'v')
        time.sleep(1.0)
        
        # Submit the prompt
        pyautogui.press('enter')
        time.sleep(1.0)
    
    async def _wait_for_completion(self, timeout_seconds: int = None):
        """Wait for the agent to complete processing"""
        from ide_completion_detector import wait_until_ide_finishes
        from exceptions import AgentTimeoutException
        from config import config
        
        # Use configured timeout if not explicitly provided
        if not timeout_seconds:
            timeout_seconds = config.agent_timeout_seconds
        
        await wait_until_ide_finishes(self.agent_name, self.interface_state_prompt, timeout_seconds, self.resume_button_prompt, require_two_subsequent_done_states=True)
    
    async def _read_output_file(self) -> str:
        """Read the output file and return its content"""
        file_path = os.path.join(os.getcwd(), self.output_file)
        
        # Wait for file to exist (max 10 seconds)
        for i in range(10):
            if os.path.exists(file_path):
                break
            time.sleep(1)
        else:
            raise Exception(f"Output file {self.output_file} was not created")
        
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Clean up the file after reading
        try:
            os.remove(file_path)
            print(f"Cleaned up {self.output_file}")
        except:
            pass  # Ignore cleanup errors
        
        return content 