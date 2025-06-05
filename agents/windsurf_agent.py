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
'done' the first thing you should check is if you see a thumbs-up or thumbs-down icon in the right panel. If you see thumbs-up/thumbs-down, that's necessarily mean that the status is done!
'still_working' if it says Running or Generating and there's a green dot on the bottom right of the chatbot panel.
IMPORTANT: Respond with a JSON object containing exactly these two keys: - 'interface_state': must be EXACTLY ONE of these values: 'still_working', or 'done' - 'reasoning': a brief explanation for your decision Example response format: ```json { "interface_state": "done", "reasoning": "I can see a thumbs-up/thumbs-down icons in the right panel" } ``` Only analyze the right panel and provide nothing but valid JSON in your response."""
    
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
            # TODO improve this prompt
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