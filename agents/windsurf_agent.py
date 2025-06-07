#!/usr/bin/env python3
"""
Windsurf Agent Implementation
"""

import time
import pyautogui
from typing import Optional
from .base import CodingAgent


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
        return """You are analyzing a screenshot of the Cascade AI coding assistant interface. You only care about the right panel that says 'Cascade | Write Mode'. IGNORE ALL THE REST OF THE SCREENSHOT. Determine the Cascade's current state based on visual cues in the right pane of the image. Return the following state for the following scenarios:
'done' the first thing you should check is if you see a thumbs-up or thumbs-down icon in the right panel. If you see thumbs-up/thumbs-down, that's necessarily mean that the status is done! Accept/Reject buttons do not imply Windsurf is done, it's just a way to give feedback to the agent!
'still_working' if it says Running or Generating and there's a green dot on the bottom right of the chatbot panel. Another indicator is if you see a red rectangle in the bottom right of the chatbot panel.
IMPORTANT: Respond with a JSON object containing exactly these two keys: - 'interface_state': must be EXACTLY ONE of these values: 'still_working', or 'done' - 'reasoning': a brief explanation for your decision Example response format: ```json { "interface_state": "done", "reasoning": "I can see a thumbs-up/thumbs-down icons in the right panel" } ``` Only analyze the right panel and provide nothing but valid JSON in your response."""
    
    @property
    def input_field_prompt(self) -> str:
        return 'Input box for the Cascade agent which starts with "Ask anything". Usually, it\'s in the right pane of the screen.'

    @property
    def copy_button_prompt(self) -> str:
        return "The Copy text of the last message in the Cascade terminal. Usually, it's in the right pane of the screen next to the Insert text button."
    
    async def is_coding_agent_open(self) -> bool:
        """Check if Windsurf Cascade interface is currently open and ready"""
        try:
            print(f"Checking if {self.agent_name} interface is already open...")
            input_coords = await self.get_input_field_coordinates()
            if input_coords:
                print(f"SUCCESS: {self.agent_name} interface is already open")
                return True
            else:
                print(f"INFO: {self.agent_name} interface not detected")
                return False
        except Exception as e:
            print(f"INFO: Could not detect {self.agent_name} interface: {str(e)}")
            return False
    
    async def open_coding_interface(self) -> bool:
        """Open Windsurf IDE and Cascade interface, handle any setup popups"""
        # First ensure Windsurf application is running
        await self._ensure_windsurf_app_open()
        
        # Then check if Cascade interface is already running
        if await self.is_coding_agent_open():
            return True
        
        # Interface is not open, open Cascade interface with keyboard shortcut
        print(f"Opening {self.agent_name} Cascade interface with shortcut: {self.keyboard_shortcut}")
        pyautogui.hotkey('command', 'i')
        time.sleep(2)  # Wait for interface to open
        
        # TODO commend out for now as it's not working that well, prompt needs to be improved
        # Handle trust workspace popup if it appears
        # await self.handle_trust_workspace_popup()
        
        # Verify the Cascade opened by checking for input field again
        if await self.is_coding_agent_open():
            print(f"SUCCESS: {self.agent_name} interface opened successfully")
            return True
        else:
            print(f"WARNING: Could not verify {self.agent_name} interface opened")
            return False
    
    async def _ensure_windsurf_app_open(self):
        """Ensure Windsurf application is open"""
        import subprocess
        import os
        
        try:
            # Get current project path
            project_path = os.getcwd()
            
            # Open Windsurf with the current project
            print(f"Opening Windsurf application with project: {project_path}")
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
            
            # Use computer_use_utils to bring window to front
            from computer_use_utils import bring_to_front_window
            repo_name = os.path.basename(project_path)
            ide_open_success = bring_to_front_window(self.window_name, repo_name)
            if not ide_open_success:
                print("Warning: Could not bring Windsurf window to front, but continuing...")
                
        except Exception as e:
            print(f"Warning: Could not open Windsurf application: {str(e)}")
            print("Assuming Windsurf is already open, continuing with Cascade interface...")
    
    async def handle_trust_workspace_popup(self):
        """Handle the 'Trust this workspace' popup specific to Windsurf"""
        print("Checking for 'Trust this workspace' prompt for Windsurf...")
        result = await self.claude.get_coordinates_from_claude(
            "A button that states 'I trust this workspace' as part of a popup", 
            support_non_existing_elements=True
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