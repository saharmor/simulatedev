#!/usr/bin/env python3
"""
Windsurf Agent Implementation
"""

import time
import pyautogui
from typing import Optional
from .base import CodingAgent
import os

from utils.computer_use_utils import bring_to_front_window, close_ide_window_for_project


class WindsurfAgent(CodingAgent):
    """Windsurf AI coding agent implementation"""
    
    @property
    def window_name(self) -> str:
        return "Windsurf"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        from utils.platform_utils import keyboard_shortcuts, PlatformDetector
        if PlatformDetector.is_macos():
            return "cmd+i"  # Keep original format for compatibility
        elif PlatformDetector.is_windows():
            return "ctrl+i"
        else:  # Linux
            return "ctrl+i"
    
    @property
    def interface_state_prompt(self) -> str:
        return """You are analyzing a screenshot of the Cascade AI coding assistant interface. You only care about the right chat panel that is called 'Cascade'. IGNORE ALL THE REST OF THE SCREENSHOT.

CRITICAL: First, systematically scan the right panel from top to bottom looking for these specific visual indicators in this exact order:

STEP 1 - CHECK FOR ACTIVE PROCESSING:
- Look for 'Running' text with a green dot/circle
- Look for a red square in the input field
- If either is present → state is 'still_working'

STEP 2 - CHECK FOR PAUSE STATE:
- Look for 'Continue response?' or similar continuation prompts
- Look for any message indicating Windsurf has paused due to execution/time limits
- If present → state is 'paused_and_wanting_to_resume'

STEP 3 - CHECK FOR COMPLETION:
- Look for thumbs-up/thumbs-down feedback icons
- If no signs of steps 1 or 2 are present → state is 'done'

VERIFICATION: Before finalizing your answer, double-check the bottom portion of the right chat panel where status indicators typically appear. Can you see ANY green indicators, running text, or active processing signals? If yes, the state cannot be 'done'.

Return the state based on these scenarios:
- 'still_working': Green dot with 'Running' text OR red square in input field
- 'paused_and_wanting_to_resume': 'Continue response?' prompt or pause indicators
- 'done': Thumbs-up/down icons visible OR no active/pause indicators found

IMPORTANT: Respond with a JSON object containing exactly these two keys:
- 'interface_state': must be EXACTLY ONE of: 'still_working', 'paused_and_wanting_to_resume', or 'done'
- 'reasoning': brief explanation including what specific visual indicator you found

Example response format:
{
 "interface_state": "still_working",
 "reasoning": "Found 'Running' text with green dot indicator in the bottom of the right panel"
}

Only analyze the right panel and provide nothing but valid JSON in your response."""

    @property
    def resume_button_prompt(self) -> str:
        return "Button stating Continue to the right of the chatbot panel"

    @property
    def input_field_prompt(self) -> str:
        return 'Input box for the Cascade agent which starts with "Ask anything". Usually, it\'s in the right pane of the screen.'


    
    async def open_coding_interface(self) -> bool:
        """Open Windsurf IDE and Cascade interface, handle any setup popups"""
        # Set current project for window title checking
        project_path = os.getcwd()
        self.set_current_project(project_path)
        
        # First ensure Windsurf application is running
        await self._ensure_windsurf_app_open()
        
        # Then check if Cascade interface is already running with correct project
        if await self.is_coding_agent_open_with_project():
            return True
        
        # Interface is not open or not with correct project, open Cascade interface with keyboard shortcut
        print(f"Opening {self.agent_name} Cascade interface with shortcut: {self.keyboard_shortcut}")
        from utils.platform_utils import keyboard_shortcuts
        keyboard_shortcuts.execute_shortcut('windsurf_cascade')
        time.sleep(2)  # Wait for interface to open
        
        # TODO commend out for now as it's not working that well, prompt needs to be improved
        # Handle trust workspace popup if it appears
        # await self.handle_trust_workspace_popup()
        
        # Verify the Cascade opened with correct project
        if await self.is_coding_agent_open_with_project():
            print(f"SUCCESS: {self.agent_name} interface opened successfully with project")
            return True
        else:
            print(f"WARNING: Could not verify {self.agent_name} interface opened with correct project")
            return False
    

    
    async def _ensure_windsurf_app_open(self):
        """Ensure Windsurf application is open"""
        import os
        from utils.platform_utils import app_launcher, PlatformDetector
        
        try:
            # Get current project path
            project_path = os.getcwd()
            
            # Open Windsurf with the current project using cross-platform launcher
            if app_launcher.open_application(self.window_name, project_path):
                print("Waiting 5 seconds for app to start...")
                time.sleep(5)  # wait for the app to start
                
                # Platform-specific activation
                if PlatformDetector.is_macos():
                    # Activate the application on macOS
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
                    print("Warning: Could not activate Windsurf window, but continuing...")
            else:
                print("Warning: Could not launch Windsurf application")
                
        except Exception as e:
            print(f"Warning: Could not open Windsurf application: {str(e)}")
            print("Assuming Windsurf is already open, continuing with Cascade interface...")
    
    async def handle_trust_workspace_popup(self):
        """Handle the 'Trust this workspace' popup specific to Windsurf"""
        print("Checking for 'Trust this workspace' prompt for Windsurf...")
        
        result = await self.computer_use_client.get_coordinates_from_vision_model(
            "A button that states 'I trust this workspace' as part of a popup", 
            support_non_existing_elements=True,
            ide_name=self.window_name,
            project_name=self._current_project_name
        )
        if result:
            print("Found trust workspace button, clicking it...")
            pyautogui.moveTo(result.coordinates.x, result.coordinates.y)
            pyautogui.click(result.coordinates.x, result.coordinates.y)
            time.sleep(1.0)
            return True
        else:
            print("INFO: No trust workspace popup found (this is normal if workspace is already trusted)")
            return False 