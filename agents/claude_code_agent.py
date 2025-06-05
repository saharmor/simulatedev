#!/usr/bin/env python3
"""
Claude Code Agent Implementation
"""

import time
import subprocess
import pyautogui
import pyperclip
import os
from typing import Optional
from .base import CodingAgent


class ClaudeCodeAgent(CodingAgent):
    """Claude Code agent implementation"""
    
    @property
    def window_name(self) -> str:
        return "Claude Code"
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        return None  # Claude Code is opened via terminal command
    
    @property
    def interface_state_prompt(self) -> str:
        return """You are analyzing a screenshot of the Claude Code interface. 
Determine the Claude Code's current state based on visual cues in the interface. 
Return the following state for the following scenarios: 
'still_working' if you see text indicating Claude is working like "esc to interrupt"
'user_input_required' if Claude is presenting the user with a question and options to choose from or if you see a prompt asking for user input
'done' if the operation appears complete without the "esc to interrupt" text or options to choose from
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
        return "Main input field or command line prompt in the Claude Code terminal interface where users can type commands or prompts."
    
    @property
    def copy_button_prompt(self) -> str:
        return "Copy button or copy icon in the Claude Code interface, typically near output or results area, or text selection that can be copied."
    
    async def send_prompt(self, prompt: str):
        """Send a prompt to Claude Code terminal (optimized for terminal interface)"""
        print(f"Sending prompt to {self.agent_name} terminal...")
        
        # For terminal interface, we don't need to locate and click input field
        # The terminal is already focused and ready for input
        
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

    async def is_coding_agent_open(self) -> bool:
        """Check if Claude Code is currently running in a terminal"""
        try:
            # Get the current repository name from the directory
            repo_dir = os.getcwd()
            repo_name = os.path.basename(repo_dir)
            
            # Use AppleScript to check for running terminals with Claude and repo name in title
            # Handle both formats: with and without folder emoji
            applescript = f'''
            tell application "System Events"
                set terminalWindows to (windows of application process "Terminal")
                repeat with termWindow in terminalWindows
                    set windowTitle to (name of termWindow as string)
                    if (windowTitle contains "📁 {repo_name}" or windowTitle contains "{repo_name}") and windowTitle contains "claude" then
                        return "found"
                    end if
                end repeat
                return "not_found"
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', applescript], 
                                  capture_output=True, text=True, check=True)
            
            if result.stdout.strip() == "found":
                print(f"SUCCESS: {self.agent_name} is already running (found terminal with title containing '{repo_name}' and 'claude')")
                return True
            else:
                print(f"INFO: {self.agent_name} not detected")
                return False
                
        except Exception as e:
            print(f"INFO: Could not check for running {self.agent_name} terminal: {str(e)}")
            return False
    
    async def open_coding_interface(self) -> bool:
        """Open Claude Code by opening terminal, navigating to repo directory, and running 'claude' command"""
        # First check if already running
        if await self.is_coding_agent_open():
            return True
        
        print(f"Opening {self.agent_name} via terminal...")
        
        # Get the current repository name from the directory
        repo_dir = os.getcwd()
        repo_name = os.path.basename(repo_dir)
        
        try:
            # Open Terminal using AppleScript (more reliable than pyautogui)
            print("Opening Terminal via AppleScript...")
            open_terminal_script = '''
            tell application "Terminal"
                activate
                do script ""
            end tell
            '''
            subprocess.run(['osascript', '-e', open_terminal_script], check=True)
            time.sleep(2)  # Wait for Terminal to open
            
            # Navigate to the repository directory and run claude
            print(f"Navigating to repository directory: {repo_dir}")
            
            # Change to the repo directory and run claude
            command = f"cd '{repo_dir}'"
            pyautogui.typewrite(command)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(1)  # Wait for cd to complete

            command = f"claude"
            pyautogui.typewrite(command)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(1)  # Wait for claude to start
            
            # Claude Code will show a security prompt asking if we trust the files in this folder
            # We need to press Enter to confirm "Yes, proceed"
            print("Confirming repository trust (pressing Enter)...")
            pyautogui.press('enter')
            time.sleep(3)  # Wait for Claude to fully initialize after confirmation
            
            # Verify Claude Code opened by checking for terminal title again
            if await self.is_coding_agent_open():
                print(f"SUCCESS: {self.agent_name} opened successfully")
                return True
            else:
                print(f"WARNING: Could not verify {self.agent_name} opened - may need manual verification")
                return False
                
        except Exception as e:
            print(f"ERROR: Failed to open {self.agent_name}: {str(e)}")
            return False 