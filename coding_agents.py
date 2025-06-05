#!/usr/bin/env python3
"""
Coding Agents Module

This module contains agent classes for different AI coding assistants.
Each agent has its own specific behavior, prompts, and interaction methods.
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
    
    async def open_interface(self):
        """Open the agent interface using keyboard shortcut if available, but first check if it's already open"""
        # First, check if the interface is already open by looking for the input field
        print(f"Checking if {self.agent_name} interface is already open...")
        try:
            input_coords = await self.get_input_field_coordinates()
            if input_coords:
                print(f"SUCCESS: {self.agent_name} interface is already open")
                return
        except Exception as e:
            print(f"INFO: {self.agent_name} interface not detected, will try to open it")
        
        # Interface is not open, try to open it with keyboard shortcut
        if self.keyboard_shortcut:
            print(f"Opening {self.agent_name} interface with shortcut: {self.keyboard_shortcut}")
            if self.keyboard_shortcut == "cmd+l":
                pyautogui.hotkey('command', 'l')
            elif self.keyboard_shortcut == "cmd+k":
                pyautogui.hotkey('command', 'k')
            elif self.keyboard_shortcut == "cmd+i":
                pyautogui.hotkey('command', 'i')
            time.sleep(2)  # Wait a bit longer for interface to open
            
            # Verify the interface opened by checking for input field again
            try:
                input_coords = await self.get_input_field_coordinates()
                if input_coords:
                    print(f"SUCCESS: {self.agent_name} interface opened successfully")
                else:
                    print(f"WARNING: Could not verify {self.agent_name} interface opened")
            except Exception as e:
                print(f"WARNING: Could not verify {self.agent_name} interface opened: {str(e)}")
        else:
            print(f"INFO: No keyboard shortcut available for {self.agent_name}")
    
    async def get_input_field_coordinates(self):
        """Get the coordinates of the input field"""
        result = await self.claude.get_coordinates_from_claude(self.input_field_prompt)
        return result
    
    async def get_copy_button_coordinates(self):
        """Get the coordinates of the copy button"""
        result = await self.claude.get_coordinates_from_claude(self.copy_button_prompt)
        return result
    
    async def analyze_interface_state(self):
        """Analyze the current state of the agent interface"""
        result = await self.claude.get_coordinates_from_claude(
            self.interface_state_prompt, 
            support_non_existing_elements=True
        )
        return result
    
    async def send_prompt(self, prompt: str):
        """Send a prompt to the agent"""
        # Open interface first if needed
        await self.open_interface()
        
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


class CursorAgent(CodingAgent):
    """Cursor AI coding agent implementation"""
    
    @property
    def window_name(self) -> str:
        return "Cursor"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        return "cmd+l"  # Command+L opens Cursor chat
    
    @property
    def interface_state_prompt(self) -> str:
        return """You are analyzing a screenshot of the Cursor AI coding assistant interface. You only care about the right panel. IGNORE ALL THE REST OF THE SCREENSHOT. 
Determine the Cursor's current state based on visual cues in the right pane of the image. 
Return the following state for the following scenarios: 
'user_input_required' if there is a Cancel and Run buttons as the last message in the right pane, above the input box. Don't return this state even if the last message ends with a question to the user.
'done' if there is a thumbs-up or thumbs-down icon in the right handside pane
'still_working' if there is a 'Generating' text in the right handside pane
IMPORTANT: Respond with a JSON object containing exactly these two keys: 
- 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' 
- 'reasoning': a brief explanation for your decision 
Example response format: 
```json 
{ 
  "interface_state": "done", 
  "reasoning": "I can see a thumbs-up/thumbs-down icons in the right panel" 
} 
``` 
Only analyze the right panel and provide nothing but valid JSON in your response."""
    
    @property
    def input_field_prompt(self) -> str:
        return 'Text input field in the right pane of the screen that says "Plan, search, build anything". This is the main input box for the Cursor Agent where users type their prompts.'
    
    @property
    def copy_button_prompt(self) -> str:
        return "A grey small thumbs-down button. Always in the right pane of the screen."


class WindsurfAgent(CodingAgent):
    """Windsurf AI coding agent implementation"""
    
    @property
    def window_name(self) -> str:
        return "Windsurf"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        return "cmd+i"  # Command+I opens Windsurf Cascade
    
    @property
    def interface_state_prompt(self) -> str:
        return """You are analyzing a screenshot of the Cascade AI coding assistant interface. You only care about the right panel that says 'Cascade | Write Mode'. IGNORE ALL THE REST OF THE SCREENSHOT. 
Determine the Cascade's current state based on visual cues in the right pane of the image. 
Return the following state for the following scenarios: 
'user_input_required' if there is an accept and reject button or 'waiting on response' text in the right handside pane
'done' if there is a thumbs-up or thumbs-down icon in the right handside pane
'still_working' for all other cases
IMPORTANT: Respond with a JSON object containing exactly these two keys: 
- 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' 
- 'reasoning': a brief explanation for your decision 
Example response format: 
```json 
{ 
  "interface_state": "done", 
  "reasoning": "I can see a thumbs-up/thumbs-down icons in the right panel" 
} 
``` 
Only analyze the right panel and provide nothing but valid JSON in your response."""
    
    @property
    def input_field_prompt(self) -> str:
        return 'Input box for the Cascade agent which starts with "Ask anything". Usually, it\'s in the right pane of the screen.'
    
    @property
    def copy_button_prompt(self) -> str:
        return "The Copy text of the last message in the Cascade terminal. Usually, it's in the right pane of the screen next to the Insert text button."
    
    async def handle_trust_workspace_popup(self):
        """Handle the 'Trust this workspace' popup specific to Windsurf"""
        print("Handling 'Trust this workspace' prompt for Windsurf...")
        result = await self.claude.get_coordinates_from_claude(
            "A button that states 'I trust this workspace' as part of a popup", 
            support_non_existing_elements=True
        )
        if result:
            pyautogui.moveTo(result.coordinates.x, result.coordinates.y)
            pyautogui.click(result.coordinates.x, result.coordinates.y)
            time.sleep(1.0)
            return True
        else:
            print("Warning: Could not find Trust button coordinates")
            return False


class ClaudeCodeAgent(CodingAgent):
    """Claude Code agent implementation"""
    
    @property
    def window_name(self) -> str:
        return "Claude Code"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        return None  # Claude Code interface is open by default
    
    @property
    def interface_state_prompt(self) -> str:
        return """You are analyzing a screenshot of the Claude Code interface. 
Determine the Claude Code's current state based on visual cues in the interface. 
Return the following state for the following scenarios: 
'user_input_required' if there are action buttons waiting for user input
'done' if the operation appears complete with results shown
'still_working' if there are loading indicators or progress bars
IMPORTANT: Respond with a JSON object containing exactly these two keys: 
- 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' 
- 'reasoning': a brief explanation for your decision 
Example response format: 
```json 
{ 
  "interface_state": "done", 
  "reasoning": "Operation completed with results displayed" 
} 
``` 
Provide nothing but valid JSON in your response."""
    
    @property
    def input_field_prompt(self) -> str:
        return "Main input field or command palette in the Claude Code interface where users can type commands or prompts."
    
    @property
    def copy_button_prompt(self) -> str:
        return "Copy button or copy icon in the Claude Code interface, typically near output or results area."


class AgentFactory:
    """Factory for creating coding agent instances"""
    
    @staticmethod
    def create_agent(agent_type: CodingAgentType, claude_computer_use) -> CodingAgent:
        """Create an agent instance based on the agent type"""
        if agent_type == CodingAgentType.CURSOR:
            return CursorAgent(claude_computer_use)
        elif agent_type == CodingAgentType.WINDSURF:
            return WindsurfAgent(claude_computer_use)
        elif agent_type == CodingAgentType.CLAUDE_CODE:
            return ClaudeCodeAgent(claude_computer_use)
        else:
            raise ValueError(f"Unsupported agent: {agent_type}")
    
    @staticmethod
    def create_agent_from_string(agent_name: str, claude_computer_use) -> CodingAgent:
        """Create an agent instance based on a string name (for backward compatibility)"""
        agent_name = agent_name.lower()
        
        if agent_name == "cursor":
            return CursorAgent(claude_computer_use)
        elif agent_name == "windsurf":
            return WindsurfAgent(claude_computer_use)
        elif agent_name == "claude_code" or agent_name == "cloud_code":
            return ClaudeCodeAgent(claude_computer_use)
        else:
            raise ValueError(f"Unsupported agent: {agent_name}")
    
    @staticmethod
    def get_supported_agents() -> list:
        """Get list of supported agent types"""
        return list(CodingAgentType) 