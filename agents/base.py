#!/usr/bin/env python3
"""
Base classes and shared components for coding agents.
"""

import time
import pyautogui
import pyperclip
import json
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
    
    async def send_prompt(self, prompt: str):
        """Send a prompt to the agent"""
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
        print(f"Copying prompt to clipboard and pasting into {self.agent_name}...")
        pyperclip.copy(prompt)
        time.sleep(0.5)  # Brief pause to ensure clipboard is updated
        
        # Paste the prompt using Cmd+V on macOS
        pyautogui.hotkey('command', 'v')
        time.sleep(1.0)  # Wait for paste to complete
        
        # Submit the prompt
        pyautogui.press('enter')
        time.sleep(1.0)
    
    async def read_agent_output(self) -> AgentResponse:
        """Read the output from the agent"""
        try:
            # Get copy button coordinates and click
            copy_coords = await self.get_copy_button_coordinates()
            if not copy_coords:
                return AgentResponse(
                    content="", 
                    success=False, 
                    error_message="Could not find copy button"
                )
            
            # Adjust coordinates slightly (original code had +30 offset)
            copy_coords.coordinates.x = copy_coords.coordinates.x + 30
            pyautogui.moveTo(copy_coords.coordinates.x, copy_coords.coordinates.y)
            pyautogui.click(copy_coords.coordinates.x, copy_coords.coordinates.y)
            time.sleep(1.0)
            
            # Get clipboard contents
            content = pyperclip.paste()
            
            # Try to format JSON if possible
            try:
                parsed = json.loads(content)
                formatted_content = json.dumps(parsed, indent=2)
                return AgentResponse(content=formatted_content, success=True)
            except json.JSONDecodeError:
                return AgentResponse(content=content, success=True)
                
        except Exception as e:
            return AgentResponse(
                content="", 
                success=False, 
                error_message=str(e)
            ) 