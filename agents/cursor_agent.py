#!/usr/bin/env python3
"""
Cursor Agent Implementation
"""

import time
import pyautogui
from typing import Optional
from .base import CodingAgent
import os

from utils.computer_use_utils import bring_to_front_window, close_ide_window_for_project

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
        return """You are analyzing a screenshot of the Cursor AI coding assistant interface. You only care about the right panel. IGNORE ALL THE REST OF THE SCREENSHOT. Determine Cursor's current state based on visual cues in the right pane of the image. Return the following state for the following scenarios:

'done' - the first thing you should check is if you see a thumbs-up or thumbs-down icon in the right panel. If you see thumbs-up/thumbs-down, that's necessarily mean that the status is done!

'still_working' - If Cursor is working and it says "Generating" and you see "Stop" buttons

'paused_and_wanting_to_resume' - If you see the message "Note: we default stop the agent after 25 tool calls. You can resume the conversation." or similar pause/resume message indicating Cursor has hit tool call limits and needs manual resume

IMPORTANT: Respond with a JSON object containing exactly these two keys:
- 'interface_state': must be EXACTLY ONE of these values: 'still_working', 'paused_and_wanting_to_resume', or 'done'
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
    def resume_button_prompt(self) -> str:
        return "Button or clickable text that says 'Resume the Conversation' or 'Resume' related to continuing after tool call limits or pausing"
    
    @property
    def input_field_prompt(self) -> str:
        return 'Input box for the Cursor Agent which starts with \'Plan, search, build anything\'. Usually, it\'s in the right pane of the screen'
    

    
    async def open_coding_interface(self) -> bool:
        """Open Cursor IDE and chat interface"""
        # Set current project for window title checking
        project_path = os.getcwd()
        self.set_current_project(project_path)
        
        # First ensure Cursor application is running
        await self._ensure_cursor_app_open()
        
        # Then check if chat interface is already running with correct project
        if await self.is_coding_agent_open_with_project():
            return True
        
        # Interface is not open or not with correct project, open chat interface with keyboard shortcut
        print(f"Opening {self.agent_name} chat interface with shortcut: {self.keyboard_shortcut}")
        pyautogui.hotkey('command', 'l')
        time.sleep(2)  # Wait for interface to open
        
        # Verify the chat interface opened with correct project
        if await self.is_coding_agent_open_with_project():
            print(f"SUCCESS: {self.agent_name} interface opened successfully with project")
            return True
        else:
            print(f"WARNING: Could not verify {self.agent_name} interface opened with correct project")
            return False
    

    
    async def _ensure_cursor_app_open(self):
        """Ensure Cursor application is open"""
        import subprocess
        import os
        
        try:
            # Get current project path
            project_path = os.getcwd()
            
            # Open Cursor with the current project
            subprocess.run(["open", "-a", self.window_name, project_path])
            print("Waiting 3 seconds for app to start...")
            time.sleep(3)  # wait for the app to start
            
            # Activate the application
            activate_script = f'''
            tell application "{self.window_name}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", activate_script], check=True)
            time.sleep(1)
            
            # Use computer_use_utils to activate window and steal focus for initial setup
            repo_name = os.path.basename(project_path)
            ide_open_success = bring_to_front_window(self.window_name, repo_name)
            if not ide_open_success:
                print("Warning: Could not activate Cursor window, but continuing...")
                
        except Exception as e:
            print(f"Warning: Could not open Cursor application: {str(e)}")
            print("Assuming Cursor is already open, continuing with chat interface...") 