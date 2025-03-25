import os
import sys
import time
import pyperclip
import subprocess
from urllib.parse import urlparse
from computer_use_utils import ClaudeComputerUse
import json

class BugHunter:
    def __init__(self):
        self.claude = ClaudeComputerUse()
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_repos")
        os.makedirs(self.base_dir, exist_ok=True)
    
    def get_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL"""
        return os.path.splitext(os.path.basename(urlparse(repo_url).path))[0]
    
    def clone_repository(self, repo_url: str) -> str:
        """Clone the repository and return the local path"""
        repo_name = self.get_repo_name(repo_url)
        local_path = os.path.join(self.base_dir, repo_name)
        
        if os.path.exists(local_path):
            print(f"Repository already exists at {local_path}")
            return local_path
            
        print(f"Cloning repository to {local_path}...")
        subprocess.run(["git", "clone", repo_url, local_path], check=True)
        return local_path
    
    def open_ide(self, ide_name: str, project_path: str):
        """Open the specified IDE with the project in full screen on the active monitor"""
        if ide_name.lower() == "cursor":
            window_name = "Cursor"
        elif ide_name.lower() == "windsurf":
            window_name = "Windsurf"
        else:
            raise ValueError(f"Unsupported IDE: {ide_name}")
            
        try:
            # Open the IDE
            subprocess.run(["open", "-a", window_name, project_path])
            
            # Wait for IDE to open
            time.sleep(5)
            
            # Make the window frontmost using AppleScript
            activate_script = f'''
            tell application "{window_name}"
                activate
            end tell
            '''
            
            subprocess.run(["osascript", "-e", activate_script], check=True)
            time.sleep(1)  # Wait for window to become active
            
            # Use Command+Control+F to toggle full screen (standard macOS shortcut)
            pyautogui.hotkey('command', 'ctrl', 'f')
            print(f"Opened {window_name} in full screen mode")
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not set window to full screen: {str(e)}")
            # Fall back to just opening the IDE without full screen
            subprocess.run(["open", "-a", window_name, project_path])
            time.sleep(5)
    
    async def type_bug_hunting_prompt(self, repo_url: str):
        """Type the bug hunting prompt into the IDE's input field"""
        prompt = f"""You are a security expert analyzing code for bugs. Respond only with a JSON array of bug findings.

<output_format>
{{
    "bugs": [
        {{
            "package_name": "string",
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

My colleague told me they found three bugs in this codebase. One of them is extremely severe. Find those bugs and return them in the specified JSON format above. Make sure the lines field generates clickable GitHub links."""
        
        # Get coordinates for the input field
        result = await self.claude.get_coordinates_from_claude(
            "Text input field in the right pane of the screen that says \"Plan, search, build anything\". This is the main input box for the Cursor Agent where users type their prompts."
        )
        
        if not result:
            print("Could not find input field coordinates")
            raise Exception("Could not find input field coordinates")
            
        # Type the prompt
        print(f"Moving to input field at ({result.coordinates.x}, {result.coordinates.y})...")
        pyautogui.moveTo(result.coordinates.x, result.coordinates.y, duration=1.0)
        time.sleep(0.5)  # Wait for mouse movement
        pyautogui.click(result.coordinates.x, result.coordinates.y)
        time.sleep(1.0)  # Wait longer for focus
        
        print("Typing prompt...")
        pyautogui.typewrite(prompt, 
                            # interval=0.1
                            )
        time.sleep(1.0)  # Wait longer before pressing Enter
        pyautogui.press('enter')
    
    def get_last_message(self):
        """Wait for 1 minute and then copy the last message"""
        print("Waiting 60 seconds for response...")
        time.sleep(60)
        
        # Simulate Cmd+A (Select All) and Cmd+C (Copy)
        pyautogui.hotkey('command', 'a')
        time.sleep(0.5)
        pyautogui.hotkey('command', 'c')
        
        # Get clipboard contents
        response = pyperclip.paste()
        
        try:
            # Try to parse and pretty print the JSON response
            parsed = json.loads(response)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            # If not valid JSON, return as is
            return response

def open_agentic_coding_interface(ide_name: str):
    if ide_name.lower() == "cursor":
        pyautogui.hotkey('command', 'i')
    elif ide_name.lower() == "windsurf":
        pyautogui.hotkey('command', 'l')
    else:
        raise ValueError(f"Unsupported IDE: {ide_name}")
    
async def main():
    if len(sys.argv) != 3:
        print("Usage: python bug_hunter.py <repository_url> <ide_name>")
        sys.exit(1)
        
    repo_url = sys.argv[1]
    ide_name = sys.argv[2]
    
    hunter = BugHunter()
    
    try:
        # Clone repository
        local_path = hunter.clone_repository(repo_url)
        
        hunter.open_ide(ide_name, local_path)
        time.sleep(1)

        open_agentic_coding_interface(ide_name)
        time.sleep(1)

        await hunter.type_bug_hunting_prompt(repo_url)
        
        # Get and print response
        response = hunter.get_last_message()
        print("\nResponse from AI:\n")
        print(response)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    import pyautogui
    
    # Add a safety delay before starting
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    asyncio.run(main()) 