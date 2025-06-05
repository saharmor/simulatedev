#!/usr/bin/env python3
"""
Cursor Agent Implementation
"""

from typing import Optional
from .base import CodingAgent


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
'done' the first thing you should check is if you see a thumbs-up or thumbs-down icon in the right panel. If you see thumbs-up/thumbs-down, that's necessarily mean that the status is done!
'still_working' If Cursor is working and it says "Generating" and you see "Stop" buttons
IMPORTANT: Respond with a JSON object containing exactly these two keys: - 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' - 'reasoning': a brief explanation for your decision Example response format: ```json { "interface_state": "done", "reasoning": "I can see a thumbs-up/thumbs-down icons in the right panel" } ``` Only analyze the right panel and provide nothing but valid JSON in your response."""
    
    @property
    def input_field_prompt(self) -> str:
        return 'Input box for the Cursor Agent which starts with \'Plan, search, build anything\'. Usually, it\'s in the right pane of the screen'
    
    @property
    def copy_button_prompt(self) -> str:
        return "A grey small thumbs-down button. Always in the right pane of the screen." 