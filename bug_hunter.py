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
from coding_agents import AgentFactory, WindsurfAgent, CodingAgentType


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
    
    async def open_ide(self, agent_type: CodingAgentType, project_path: str, should_wait_for_focus: bool = False):
        print(f"Opening IDE: {agent_type.value} with project path: {project_path}")
        
        # Create agent instance
        agent = AgentFactory.create_agent(agent_type, self.claude)
        window_name = agent.window_name
        
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
            
            if should_wait_for_focus:
                is_focused_and_opened = wait_for_focus(window_name)            
                if not is_focused_and_opened:
                    print("Error: IDE failed to open or gain focus")
                    raise Exception("IDE did not open or focus")
            
            # Handle Windsurf-specific popup
            if isinstance(agent, WindsurfAgent):
                await agent.handle_trust_workspace_popup()
                
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not set window to full screen: {str(e)}")
            print(f"Attempting fallback open command for {window_name}...")
            subprocess.run(["open", "-na", window_name, project_path])
            print("Waiting 5 seconds after fallback open...")
            time.sleep(5)

    async def get_input_field_coordinates(self, agent_type: CodingAgentType):
        """Get the coordinates of the input field using agent class"""
        agent = AgentFactory.create_agent(agent_type, self.claude)
        return await agent.get_input_field_coordinates()
    
    async def send_prompt_to_agent(self, agent_type: CodingAgentType, prompt: str):
        """Send a prompt to the specified agent"""
        agent = AgentFactory.create_agent(agent_type, self.claude)
        await agent.send_prompt(prompt)
    
    async def get_last_message(self, agent_type: CodingAgentType):
        """Get the last message from the agent"""
        agent = AgentFactory.create_agent(agent_type, self.claude)
        response = await agent.read_agent_output()
        
        if response.success:
            return response.content
        else:
            raise Exception(f"Failed to read agent output: {response.error_message}")
    
    async def wait_for_agent_completion(self, agent_type: CodingAgentType, timeout_seconds: int = 300):
        """Wait for the agent to complete processing"""
        agent = AgentFactory.create_agent(agent_type, self.claude)
        await wait_until_ide_finishes(agent_type.value, agent.interface_state_prompt, timeout_seconds)
    
    async def type_bug_hunting_prompt(self, input_field_coordinates: tuple, repo_url: str):
        """Type the bug hunting prompt into the IDE's input field"""
        prompt = f"""You are a world-class developer analyzing code for bugs. Respond only with a JSON array of bug findings.

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


def clean_input_box():
    pyautogui.hotkey('command', 'a')
    pyautogui.hotkey('command', 'backspace')

def open_agentic_coding_interface():
    #TODO add check if the agentic coding interface is not already open
    pyautogui.hotkey('command', 'l')
    
    # clean the input box
    # clean_input_box(ide_name)

async def main():
    #TODO  Revert, only for dev purposes
    repo_url = "https://github.com/saharmor/gemini-multimodal-playground"
    agent_type = CodingAgentType.CURSOR
    
    hunter = BugHunter()
    
    try:
        # Clone repository
        local_path = hunter.clone_repository(repo_url)
        
        await hunter.open_ide(agent_type, local_path)
        time.sleep(1)

        open_agentic_coding_interface()
        time.sleep(1)

        # Get the coordinates of the input field
        input_field_coordinates = await hunter.get_input_field_coordinates(agent_type)
        if input_field_coordinates:
            await hunter.type_bug_hunting_prompt(input_field_coordinates.coordinates, repo_url)
        else:
            raise Exception("Could not find input field coordinates")
        
        # wait for IDE to finish processing command
        await hunter.wait_for_agent_completion(agent_type, 120)

        # Get and print response
        response = await hunter.get_last_message(agent_type)
        print("\nResponse from AI:\n")
        print(response)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":    # Add a safety delay before starting
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    # move mouse here (1189, 450)
    pyautogui.moveTo(1189, 450)

    asyncio.run(main()) 
