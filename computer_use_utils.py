import os
import base64
import io
import subprocess
import pyautogui
from enum import Enum
from typing import Optional, Tuple
from dotenv import load_dotenv
import json
from dataclasses import dataclass
from mss import mss
from PIL import Image

load_dotenv()

class ScalingSource(Enum):
    API = 1      # Coordinates from API (need to be scaled to real screen)
    SCREEN = 2   # Coordinates from screen (need to be scaled to API format)

class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"

@dataclass
class Coordinates:
    x: int
    y: int

@dataclass
class ComputerUseAction:
    action_type: ActionType
    coordinates: Coordinates

class ClaudeComputerUse:
    """Simple class to interact with Claude Computer Use for getting coordinates"""
    
    def __init__(self):
        # Get the actual screen dimensions
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Set target dimensions (what Claude expects)
        self.target_width = 1280  # Claude's max screenshot width
        self.target_height = int(self.screen_height * (self.target_width / self.screen_width))
    
    def scale_coordinates(self, source: ScalingSource, x: int, y: int) -> Tuple[int, int]:
        """Scale coordinates between Claude's coordinate system and real screen coordinates"""
        x_scaling_factor = self.screen_width / self.target_width
        y_scaling_factor = self.screen_height / self.target_height
        
        if source == ScalingSource.API:
            # Claude's coordinates -> real screen coordinates
            return round(x * x_scaling_factor), round(y * y_scaling_factor)
        else:
            # Real screen coordinates -> Claude's coordinate system
            return round(x / x_scaling_factor), round(y / y_scaling_factor)
    
    
    
    async def get_coordinates_from_claude(self, prompt: str, support_non_existing_elements: bool = False) -> Optional[ComputerUseAction]:
        """Get coordinates and action type from Claude based on a natural language prompt
        
        Returns:
            Optional[ComputerUseAction]: A ComputerUseAction object containing:
                - action_type: ActionType enum (CLICK or TYPE)
                - coordinates: Coordinates object with x and y attributes
        """
        try:
            from anthropic import Anthropic
            
            # Get API key from environment
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                print("Error: ANTHROPIC_API_KEY not found in environment variables")
                return None
            
            # Initialize Anthropic client
            client = Anthropic(api_key=api_key)
            
            # Take a screenshot
            base64_image = take_screenshot(self.target_width, self.target_height, encode_base64=True, save_to_file=True)
            
            # Create the message with the screenshot and prompt
            system_prompt = """You are a UI Element Detection AI. Analyze screenshots to locate UI elements and output in JSON format with these exact keys:
{
    "action": {
        "type": "click" or "type" (use "click" for buttons/links, "type" for text inputs),
        "coordinates": {
            "x": number (horizontal position),
            "y": number (vertical position)
        },
    }
}"""

            if support_non_existing_elements:
                system_prompt = system_prompt + """ If the requested UI element is not found in the screenshot, respond with None. Otherwise, respond ONLY with the JSON format above and nothing else."""
            else:
                system_prompt = system_prompt + """ Respond ONLY with the JSON format above and nothing else."""

            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            # Extract coordinates from response
            response_text = response.content[0].text

            try:
                # Strip any code block markers from response text before parsing
                response_text = response_text.strip('`').replace('json\n', '')
                response_data = json.loads(response_text)
                x = response_data['action']['coordinates']['x']
                y = response_data['action']['coordinates']['y']
                action_type_str = response_data['action']['type']
                
                # Convert string action type to enum
                action_type = ActionType(action_type_str)

                # Scale coordinates from API format to screen format
                scaled_x, scaled_y = self.scale_coordinates(ScalingSource.API, x, y)
                
                return ComputerUseAction(
                    action_type=action_type,
                    coordinates=Coordinates(x=scaled_x, y=scaled_y)
                )
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing response from Claude: {str(e)}")
                print(f"Response text was: {response_text}")
                return None
            
        except Exception as e:
            print(f"Error getting coordinates from Claude: {str(e)}")
            return None


def get_coordinates_for_prompt(prompt: str) -> Optional[Tuple[int, int]]:
    import asyncio
    
    claude = ClaudeComputerUse()
    
    # Run the async function in a new event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        coordinates = loop.run_until_complete(claude.get_coordinates_from_claude(prompt))
        loop.close()
    except Exception as e:
        print(f"Error running async function: {str(e)}")
        return None
    
    if coordinates:
        api_x, api_y = coordinates
        print(f"Claude coordinates: ({api_x}, {api_y})")
        
        # Scale the coordinates to match the actual screen dimensions
        scaled_x, scaled_y = claude.scale_coordinates(ScalingSource.API, api_x, api_y)        
        return scaled_x, scaled_y
    else:
        print("Failed to get coordinates from Claude")
        return None


def wait_for_focus(app_name, timeout=10):
    """Wait until the specified app is frontmost."""
    script = f'''
    tell application "System Events"
        repeat until (name of first application process whose frontmost is true) is "{app_name}"
            delay 0.5
        end repeat
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"Timed out waiting for {app_name} to become active.")
        return False
    return True

def take_screenshot(target_width, target_height, encode_base64: bool = False, monitor_number: int = 0, save_to_file: bool = False) -> str:
    """
    Capture screenshot using mss library with multi-monitor support.
    
    Args:
        monitor_number (int, optional): The monitor number to capture (0-based index).
                                        If None, captures the entire screen across all monitors.
    """
    with mss() as sct:
        if monitor_number < 0 or monitor_number >= len(sct.monitors):
            raise ValueError(f"Invalid monitor number. Available monitors: 0-{len(sct.monitors)-1}")
        # Capture specific monitor (add 1 since monitors[0] is the virtual screen)
        screenshot = sct.grab(sct.monitors[monitor_number + 1])
        
        # Convert to PIL Image for resizing
        screenshot = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
        
        # Resize to target dimensions
        screenshot = screenshot.resize((target_width, target_height))
        
        if save_to_file:
            screenshot.save("screenshot.png")

        # Save to in-memory buffer
        img_buffer = io.BytesIO()
        screenshot.save(img_buffer, format="PNG", optimize=True)
        img_buffer.seek(0)
        
        if encode_base64:# Return base64 encoded image
            return base64.b64encode(img_buffer.read()).decode()
        else:
            return img_buffer
