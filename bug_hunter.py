import os
import sys
import time
import pyperclip
import subprocess
from urllib.parse import urlparse
from computer_use_utils import ClaudeComputerUse, wait_for_focus
import json
import asyncio
import pyautogui

from ide_completion_detector import wait_until_ide_finishes

INTERFACE_CONFIG = {
    "windsurf": {
        "interface_state_prompt": 
            "You are analyzing a screenshot of the Cascade AI coding assistant interface. You only care about the right panel that says 'Cascade | Write Mode'. IGNORE ALL THE REST OF THE SCREENSHOT. " 
                "Determine the Cascade's current state based on visual cues in the right pane of the image. "
                    "Return the following state for the following scenarios: "
                    "'user_input_required' if there is an accept and reject button or 'waiting on response' text in the right handside pane"
                    "'done' if there is a thumbs-up or thumbs-down icon in the right handside pane"
                    "'still_working' for all other cases"
                    "IMPORTANT: Respond with a JSON object containing exactly these two keys: "
                "- 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' "
                    "- 'reasoning': a brief explanation for your decision "
                    "Example response format: "
                    "```json "
                    "{ "
                "  \"interface_state\": \"done\", "
                    "  \"reasoning\": \"I can see a thumbs-up/thumbs-down icons in the right panel\" "
                    "} "
                    "``` "
                    "Only analyze the right panel and provide nothing but valid JSON in your response.",
        "computer_use_selector_prompt": "Input box for the Cascade agent which starts with 'Ask anything'. Usually, it's in the right pane of the screen.",
        "copy_button_prompt": "The Copy text of the last message in the Cascade terminal. Usually, it's in the right pane of the screen next to the Insert text button."
    },
    "cursor": {
        "interface_state_prompt": 
            "You are analyzing a screenshot of the Cursor AI coding assistant interface. You only care about the right panel. IGNORE ALL THE REST OF THE SCREENSHOT. " 
                "Determine the Cursor's current state based on visual cues in the right pane of the image. "
                    "Return the following state for the following scenarios: "
                    "'user_input_required' if there is a Cancel and Run buttons as the last message in the right pane, above the input box. Don't return this state even if the last message ends with a question to the user."
                    "'done' if there is a thumbs-up or thumbs-down icon in the right handside pane"
                    "'still_working' if there is a 'Generating' text in the right handside pane"
                    "IMPORTANT: Respond with a JSON object containing exactly these two keys: "
                "- 'interface_state': must be EXACTLY ONE of these values: 'user_input_required', 'still_working', or 'done' "
                    "- 'reasoning': a brief explanation for your decision "
                    "Example response format: "
                    "```json "
                    "{ "
                "  \"interface_state\": \"done\", "
                    "  \"reasoning\": \"I can see a thumbs-up/thumbs-down icons in the right panel\" "
                    "} "
                    "``` "
                    "Only analyze the right panel and provide nothing but valid JSON in your response.",
        "computer_use_selector_prompt": "Text input field in the right pane of the screen that says \"Plan, search, build anything\". This is the main input box for the Cursor Agent where users type their prompts.",
        #  "copy_button_prompt": "A grey thumbs-down button. Always in the right pane of the screen."
         "copy_button_prompt": "A grey small thumbs-down button. Always in the right pane of the screen."
    },
}

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
    
    async def open_ide(self, ide_name: str, project_path: str, wait_for_focus: bool = False):
        print(f"Opening IDE: {ide_name} with project path: {project_path}")
        
        if ide_name.lower() == "cursor":
            window_name = "Cursor"
        elif ide_name.lower() == "windsurf":
            window_name = "Windsurf" 
        else:
            print(f"Error: Unsupported IDE {ide_name}")
            raise ValueError(f"Unsupported IDE: {ide_name}")
        
        try:
            subprocess.run(["open", "-a", window_name, project_path])
            print("Waiting 3 seconds for app to start...")
            time.sleep(3)  # wait for the app to start
            
            activate_script = f'''
            tell application "{window_name}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", activate_script], check=True)
            time.sleep(1)
            
            if wait_for_focus:
                is_focused_and_opened = wait_for_focus(window_name)            
                if not is_focused_and_opened:
                    print("Error: IDE failed to open or gain focus")
                    raise Exception("IDE did not open or focus")
                
            if ide_name.lower() == "windsurf":
                print("Handling 'Trust this workspace' prompt for Windsurf...")
                result = await self.claude.get_coordinates_from_claude("A button that states 'I trust this workspace' as part of a popup", support_non_existing_elements=True)
                if result:
                    pyautogui.moveTo(result.coordinates.x, result.coordinates.y)
                    pyautogui.click(result.coordinates.x, result.coordinates.y)
                else:
                    print("Warning: Could not find Trust button coordinates")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not set window to full screen: {str(e)}")
            print(f"Attempting fallback open command for {window_name}...")
            subprocess.run(["open", "-na", window_name, project_path])
            print("Waiting 5 seconds after fallback open...")
            time.sleep(5)


    async def get_input_field_coordinates(self, ide_name: str):
        """Get the coordinates of the input field"""
        result = await self.claude.get_coordinates_from_claude(
            INTERFACE_CONFIG[ide_name]["computer_use_selector_prompt"]
        )
        return result
    
    async def type_bug_hunting_prompt(self, input_field_coordinates: tuple, repo_url: str):
        """Type the bug hunting prompt into the IDE's input field"""
        prompt = f"""You are a world-class develope analyzing code for bugs. Respond only with a JSON array of bug findings.

<output_format>
{{
    "bugs": [
        {{
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


My colleague told me they found three bugs in this codebase. One of them is extremely severe. Find those bugs and return them in the specified JSON format above. Make sure the lines field generates clickable GitHub links.
ONLY RETURN THE JSON ARRAY. NOTHING ELSE."""
        

        # Move to the input field
        print(f"Moving to input field at ({input_field_coordinates.x}, {input_field_coordinates.y})...")
        pyautogui.moveTo(input_field_coordinates.x, input_field_coordinates.y, duration=1.0)
        time.sleep(0.5)  # Wait for mouse movement
        pyautogui.click(input_field_coordinates.x, input_field_coordinates.y)
        time.sleep(1.0)  # Wait longer for focus
        
        print("Typing prompt...")
        # Type the prompt line by line, inserting a newline break (Shift+Enter) after each line
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            pyautogui.write(line)
            if i < len(lines) - 1:  # Don't add newline after last line
                pyautogui.hotkey('shift', 'enter')  # inserts a line break without submitting

        pyautogui.press('enter')
        time.sleep(1.0)  # Wait longer before pressing Enter
    
    async def get_last_message(self, ide_name: str):        
        # Use Claude computer use to find the copy button and click it
        result = await self.claude.get_coordinates_from_claude(INTERFACE_CONFIG[ide_name]["copy_button_prompt"])
        if result:
            result.coordinates.x = result.coordinates.x + 30
            pyautogui.moveTo(result.coordinates.x, result.coordinates.y)
            pyautogui.click(result.coordinates.x, result.coordinates.y)
        else:
            raise Exception("Could not find Copy button coordinates")
    
        # Get clipboard contents
        response = pyperclip.paste()
        try:
            # Try to parse and pretty print the JSON response
            parsed = json.loads(response)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            # If not valid JSON, return as is
            return response

def clean_input_box():
    pyautogui.hotkey('command', 'a')
    pyautogui.hotkey('command', 'backspace')

def open_agentic_coding_interface():
    #TODO add check if the agentic coding interface is not already open
    pyautogui.hotkey('command', 'l')
    
    # clean the input box
    # clean_input_box(ide_name)

async def main():
    # # TODO  Revert, only for dev purposes
    # if len(sys.argv) != 3:
    #     print("Usage: python bug_hunter.py <repository_url> <ide_name>")
    #     sys.exit(1)
        
    # ide_name = sys.argv[1]
    # repo_url = sys.argv[2]
    
    #TODO  Revert, only for dev purposes
    repo_url = "https://github.com/saharmor/gemini-multimodal-playground"
    ide_name = "cursor"
    
    hunter = BugHunter()
    
    try:
        # Clone repository
        local_path = hunter.clone_repository(repo_url)
        
        await hunter.open_ide(ide_name, local_path)
        time.sleep(1)

        open_agentic_coding_interface()
        time.sleep(1)

        # Get the coordinates of the input field
        input_field_coordinates = await hunter.get_input_field_coordinates(ide_name)
        if input_field_coordinates:
            await hunter.type_bug_hunting_prompt(input_field_coordinates.coordinates, repo_url)
        else:
            raise Exception("Could not find input field coordinates")
        
        # wait for IDE to finish processing command
        await wait_until_ide_finishes(ide_name, INTERFACE_CONFIG[ide_name]["interface_state_prompt"], 120)

        # Get and print response
        response = await hunter.get_last_message(ide_name)
        print("\nResponse from AI:\n")
        print(response)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":    # Add a safety delay before starting
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    asyncio.run(main()) 
