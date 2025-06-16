import os
import base64
import io
import subprocess
import pyautogui
import platform
from enum import Enum
from typing import Optional, Tuple, List
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

# IDE Configuration mapping
IDE_CONFIG = {
    "windsurf": {
        "process_name": "Electron",
        "display_name": "Windsurf"
    },
    "cursor": {
        "process_name": "Cursor", 
        "display_name": "Cursor"
    }
}

def _get_ide_process_name(app_name: str) -> str:
    """Get the process name for a given IDE application"""
    app_name = app_name.lower()
    if app_name in IDE_CONFIG:
        return IDE_CONFIG[app_name]["process_name"]
    return app_name.capitalize()

def _get_ide_display_name(app_name: str) -> str:
    """Get the display name for a given IDE application"""
    app_name = app_name.lower()
    if app_name in IDE_CONFIG:
        return IDE_CONFIG[app_name]["display_name"]
    return app_name.capitalize()

def _run_applescript(script: str) -> Tuple[bool, str]:
    """
    Run an AppleScript and return success status and output.
    
    Returns:
        Tuple[bool, str]: (success, output_or_error)
    """
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip() if e.stderr else "AppleScript execution failed"
    except Exception as e:
        return False, str(e)

def _get_process_window_titles(process_name: str) -> Tuple[bool, List[str]]:
    """
    Get all window titles for a given process using AppleScript.
    
    Returns:
        Tuple[bool, List[str]]: (success, list_of_window_titles)
    """
    script = f'''
    tell application "System Events"
        tell process "{process_name}"
            set windowTitles to name of every window
        end tell
    end tell
    return windowTitles
    '''
    
    success, output = _run_applescript(script)
    if success:
        # Handle empty output or single empty string
        if not output or output == '""' or output == "":
            return True, []
        window_titles = [title.strip().strip('"') for title in output.split(",")]
        return True, window_titles
    else:
        return False, []

def _get_frontmost_process() -> Tuple[bool, str]:
    """
    Get the name of the frontmost process using AppleScript.
    
    Returns:
        Tuple[bool, str]: (success, process_name)
    """
    script = '''
    tell application "System Events"
        set frontProcess to name of first application process whose frontmost is true
    end tell
    return frontProcess
    '''
    
    return _run_applescript(script)

def _find_window_with_project(window_titles: List[str], project_name: str) -> Optional[str]:
    """
    Find a window title that contains the project name.
    
    Returns:
        Optional[str]: The matching window title, or None if not found
    """
    for title in window_titles:
        if project_name.lower() in title.lower():
            return title
    return None

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
    
    
    
    async def get_coordinates_from_claude(self, prompt: str, support_non_existing_elements: bool = False, ide_name: str = None, project_name: str = None) -> Optional[ComputerUseAction]:
        """Get coordinates and action type from Claude based on a natural language prompt
        
        Args:
            prompt (str): Natural language description of the UI element to find
            support_non_existing_elements (bool): Whether to handle non-existing elements gracefully
            ide_name (str, optional): Name of the IDE to capture window for (e.g., "Cursor", "Windsurf")
            project_name (str, optional): Name of the project to find in window titles
        
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
            
            # Take a screenshot - use IDE window screenshot if both ide_name and project_name are provided
            if ide_name and project_name:
                base64_image_data = take_ide_window_screenshot(ide_name, project_name, self.target_width, self.target_height, encode_base64=True)
                if base64_image_data is None:
                    print(f"WARNING: Could not capture {ide_name} window for project '{project_name}'. Falling back to full screen.")
                    base64_image_data = take_screenshot(self.target_width, self.target_height, encode_base64=True)
            else:
                base64_image_data = take_screenshot(self.target_width, self.target_height, encode_base64=True)
            
            # Create the message with the screenshot and prompt
            system_prompt = """You are a UI Element Detection AI. Analyze the attached screenshot to locate UI elements and output in JSON format with these exact keys:
{
    "action": {
        "type": "click" or "type" (use "click" for buttons/links, "type" for text inputs),
        "coordinates": {
            "x": number (horizontal position),
            "y": number (vertical position)
        },
    }

    IMPORTANT: If there is more than one element that matches the prompt, choose the one that is more prominent, for example, the one that is more visible, or the one in the focused and front window.
}"""

            if support_non_existing_elements:
                system_prompt = system_prompt + """ If the requested UI element is not found in the screenshot, respond with None. Otherwise, respond ONLY with the JSON format above and nothing else."""
            else:
                system_prompt = system_prompt + """ Respond ONLY with the JSON format above and nothing else."""
            
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
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
                                    "data": base64_image_data
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
            
            # Parse the response
            response_text = message.content[0].text.strip()
            
            # Handle None response for non-existing elements
            if support_non_existing_elements and response_text.lower() == "none":
                return None
            
            # Parse JSON response
            try:
                response_json = json.loads(response_text)
                action_data = response_json.get("action", {})
                
                # Extract action type and coordinates
                action_type_str = action_data.get("type", "click")
                action_type = ActionType.CLICK if action_type_str == "click" else ActionType.TYPE
                
                coords_data = action_data.get("coordinates", {})
                x = coords_data.get("x", 0)
                y = coords_data.get("y", 0)
                
                # Scale coordinates from Claude's coordinate system to real screen coordinates
                real_x, real_y = self.scale_coordinates(ScalingSource.API, x, y)
                
                return ComputerUseAction(
                    action_type=action_type,
                    coordinates=Coordinates(real_x, real_y)
                )
                
            except json.JSONDecodeError as e:
                print(f"Error parsing Claude response as JSON: {e}")
                print(f"Response was: {response_text}")
                return None
                
        except Exception as e:
            print(f"Error getting coordinates from Claude: {e}")
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


def get_windsurf_project_window_name(project_contained_name: str):
    """Get Windsurf project window name since it runs as an Electron app"""
    success, window_titles = _get_process_window_titles("Electron")
    if success:
        return next((name for name in window_titles if project_contained_name in name), None)
    else:
        print(f"Error getting Windsurf window names")
        return None


def get_ide_window_name(app_name: str, window_title: str):
    """Extract the appropriate window name based on the IDE"""
    if app_name == "windsurf":
        return window_title.split(" — ")[0] if " — " in window_title else window_title
    elif app_name == "cursor":
        return window_title.split(" — ")[1] if " — " in window_title else window_title
    else:
        return window_title


def bring_to_front_window(app_name: str, project_name: str):
    """
    Focus the appropriate IDE window that contains the project name.
    
    Args:
        app_name (str): Name of the IDE application (e.g., "Cursor", "Windsurf")
        project_name (str): Name of the project to find in window titles
    
    Returns:
        bool: True if the window was successfully focused, False otherwise
    """
    try:
        app_name = app_name.lower()
        process_name = _get_ide_process_name(app_name)
        display_name = _get_ide_display_name(app_name)
        
        # First check if the IDE is running with the project
        if not is_ide_open_with_project(app_name, project_name, verbose=False):
            print(f"{display_name} is not open with project '{project_name}'")
            return False
        
        # Get window titles for the process
        success, window_titles = _get_process_window_titles(process_name)
        if not success:
            print(f"Could not get window titles for {display_name}")
            return False
        
        # Find the window that contains the project name
        matching_window = _find_window_with_project(window_titles, project_name)
        if not matching_window:
            print(f"No window found containing project '{project_name}'")
            return False
        
        if platform.system() == "Darwin":
            # Use AppleScript to bring the specific window to front
            script = f'''
            tell application "System Events"
                tell process "{process_name}"
                    set frontmost to true
                    delay 0.5
                    repeat with w in windows
                        if name of w contains "{project_name}" then
                            perform action "AXRaise" of w
                            set position of w to {{0, 0}}
                            delay 0.5
                            exit repeat
                        end if
                    end repeat
                end tell
            end tell
            '''

            success, _ = _run_applescript(script)
            if not success:
                print(f"Failed to bring {display_name} window for project '{project_name}' to focus")
                return False

            return True
        elif platform.system() == "Windows":
            # Windows-specific focusing script would be implemented here
            print("Window focusing not implemented for Windows")
            return False
        else:
            print(f"Window focusing not implemented for {platform.system()}")
            return False
    except Exception as e:
        print(f"Error focusing window: {e}")
        return False


def wait_for_focus(app_name, timeout=10):
    """Wait until the specified app is frontmost. Updated to handle Windsurf as Electron app."""
    # Use the helper function to get process name
    process_name = _get_ide_process_name(app_name)
    
    script = f'''
    tell application "System Events"
        repeat until (name of first application process whose frontmost is true) is "{process_name}"
            delay 0.5
        end repeat
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        print(f"Timed out waiting for {app_name} (process: {process_name}) to become active.")
        return False
    except Exception as e:
        print(f"Error waiting for focus: {str(e)}")
        return False


def get_current_window_name():
    """Get the name of the currently active window, with robust error handling."""
    script = '''
    try
        tell application "System Events"
            set frontProcess to first process whose frontmost is true
            set processName to name of frontProcess
        end tell

        if processName is "Google Chrome" then
            tell application "Google Chrome"
                if (count of windows) > 0 then
                    return title of active tab of front window
                else
                    return "Google Chrome"
                end if
            end tell
        else
            tell application "System Events"
                if exists front window of frontProcess then
                    return name of front window of frontProcess
                else
                    return processName
                end if
            end tell
        end if
    on error errorMessage
        return "Unknown"
    end try
    '''
    
    success, output = _run_applescript(script)
    if success:
        return output
    else:
        print(f"Warning: AppleScript error when getting window name: {output}")
        return "Unknown Window"


def is_ide_open_with_project(app_name: str, project_name: str, verbose: bool = True) -> bool:
    """
    Check if a specific IDE is running and has the specified project open.
    
    Args:
        app_name (str): Name of the IDE application (e.g., "Cursor", "Windsurf")
        project_name (str): Name of the project to check for in window titles
        verbose (bool): Whether to print status messages
        
    Returns:
        bool: True if the IDE is running with the specified project, False otherwise
    """
    try:
        if platform.system() != "Darwin":
            if verbose:
                print(f"IDE project checking not implemented for {platform.system()}")
            return False
            
        app_name = app_name.lower()
        process_name = _get_ide_process_name(app_name)
        display_name = _get_ide_display_name(app_name)
        
        # Get window titles for the process
        success, window_titles = _get_process_window_titles(process_name)
        
        if not success:
            if verbose:
                print(f"{display_name} ({process_name}) is not running")
            return False
        
        # Check if any window title contains the project name
        matching_window = _find_window_with_project(window_titles, project_name)
        
        if matching_window:
            if verbose:
                print(f"Found {display_name} window with project '{project_name}': {matching_window}")
            return True
        else:
            if verbose:
                print(f"{display_name} is running but no window found with project '{project_name}'")
                print(f"Available windows: {window_titles}")
            return False
            
    except Exception as e:
        if verbose:
            print(f"Error checking if {app_name} is open with project '{project_name}': {e}")
        return False


def close_ide_window_for_project(app_name: str, project_name: str) -> bool:
    """
    Close a specific IDE window that contains the project name.
    
    Args:
        app_name (str): Name of the IDE application (e.g., "Cursor", "Windsurf")
        project_name (str): Name of the project to close the window for
        
    Returns:
        bool: True if window was closed successfully, False otherwise
    """
    try:
        if platform.system() != "Darwin":
            print(f"IDE window closing not implemented for {platform.system()}")
            return False
            
        app_name = app_name.lower()
        process_name = _get_ide_process_name(app_name)
        
        # Use AppleScript to close the specific window containing the project name
        close_script = f'''
        tell application "System Events"
            tell process "{process_name}"
                repeat with w in windows
                    if name of w contains "{project_name}" then
                        click button 1 of w
                        exit repeat
                    end if
                end repeat
            end tell
        end tell
        '''
        
        success, _ = _run_applescript(close_script)
        if success:
            print(f"SUCCESS: Attempted to close {app_name} window for project '{project_name}'")
            return True
        else:
            print(f"ERROR: Failed to close {app_name} window for project '{project_name}'")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to close {app_name} window for project '{project_name}': {e}")
        return False


def take_screenshot(target_width, target_height, encode_base64: bool = False, monitor_number: int = 0) -> str:
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
        


        # Save to in-memory buffer
        img_buffer = io.BytesIO()
        screenshot.save(img_buffer, format="PNG", optimize=True)
        img_buffer.seek(0)
        
        if encode_base64:# Return base64 encoded image
            return base64.b64encode(img_buffer.read()).decode()
        else:
            return img_buffer


def play_beep_sound():
    """Play a beep sound to alert the user"""
    try:
        if platform.system() == "Darwin":
            # Use macOS system beep
            subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"], check=False)
        elif platform.system() == "Windows":
            # Use Windows system beep
            import winsound
            winsound.Beep(1000, 500)  # 1000 Hz for 500ms
        else:
            # Linux - try to use system bell
            subprocess.run(["pactl", "upload-sample", "/usr/share/sounds/alsa/Front_Left.wav", "bell"], check=False)
            subprocess.run(["pactl", "play-sample", "bell"], check=False)
    except Exception as e:
        print(f"Warning: Could not play beep sound: {e}")


def take_ide_window_screenshot(ide_name: str, project_name: str, target_width: int = 1280, target_height: int = 720, encode_base64: bool = False, verbose: bool = False):
    """
    Capture a screenshot of the specific IDE window that contains the project name.
    Automatically brings the window to focus before taking the screenshot.
    
    Args:
        ide_name (str): Name of the IDE application (e.g., "Cursor", "Windsurf")
        project_name (str): Name of the project to find in window titles
        target_width (int): Target width for the screenshot
        target_height (int): Target height for the screenshot
        encode_base64 (bool): Whether to return base64 encoded image
        verbose (bool): Whether to print detailed status messages
        
    Returns:
        str or BytesIO: Screenshot data (base64 string if encode_base64=True, BytesIO buffer otherwise)
        Returns None if the IDE window is not found or not focused
    """
    try:
        if platform.system() != "Darwin":
            print(f"IDE window screenshot not implemented for {platform.system()}")
            return None
            
        ide_name = ide_name.lower()
        process_name = _get_ide_process_name(ide_name)
        display_name = _get_ide_display_name(ide_name)
        
        # First check if the IDE is running with the project
        if not is_ide_open_with_project(ide_name, project_name, verbose=False):
            print(f"{display_name} is not open with project '{project_name}'")
            return None
        
        # Get window titles for the process
        success, window_titles = _get_process_window_titles(process_name)
        if not success:
            print(f"Could not get window titles for {display_name}")
            return None
        
        # Find the window that contains the project name
        matching_window = _find_window_with_project(window_titles, project_name)
        if not matching_window:
            print(f"No window found containing project '{project_name}'")
            return None
        
        # IMPORTANT: Bring the window to focus before taking screenshot
        focus_success = bring_to_front_window(ide_name, project_name)
        if not focus_success:
            print(f"Warning: Could not bring {display_name} window to focus, but continuing...")
        else:
            # Wait a moment for the window to come to focus
            import time
            time.sleep(1.5)
        
        # Create a temporary file for the screenshot
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        # Use AppleScript to ensure the window is frontmost and capture it
        script = f'''
        tell application "System Events"
            set targetWindow to window "{matching_window}" of process "{process_name}"
            if exists targetWindow then
                set frontmost of process "{process_name}" to true
                perform action "AXRaise" of targetWindow
                delay 1.0
            end if
        end tell
        '''
        
        # Run the AppleScript to bring window to front
        subprocess.run(["osascript", "-e", script], capture_output=True)
        
        # Find the window ID for screencapture
        list_cmd = ["screencapture", "-C", "-L"]
        list_result = subprocess.run(list_cmd, capture_output=True, text=True)
        window_id = None
        
        # Try multiple matching strategies to find the window ID
        for line in list_result.stdout.splitlines():
            # Strategy 1: Exact match with the full window title
            if matching_window in line:
                window_id = line.split(':')[0].strip()
                break
            # Strategy 2: Match with project name only (more flexible)
            elif project_name in line:
                window_id = line.split(':')[0].strip()
                break
        
        if window_id:
            # Capture the specific window
            subprocess.run(["screencapture", "-l", window_id, path], check=True)
        else:
            # Fallback to full screen if window ID not found
            # Only print warning in verbose mode to reduce noise
            if verbose:
                print(f"Warning: Could not find window ID for '{matching_window}', falling back to full screen")
            subprocess.run(["screencapture", "-x", path], check=True)
        
        # Open and process the image
        image = Image.open(path)
        
        # Resize to target dimensions
        image = image.resize((target_width, target_height))
        
        # Save to in-memory buffer
        img_buffer = io.BytesIO()
        image.save(img_buffer, format="PNG", optimize=True)
        img_buffer.seek(0)
        
        # Delete the temporary file
        os.unlink(path)
        
        if encode_base64:
            return base64.b64encode(img_buffer.read()).decode()
        else:
            return img_buffer
            
    except Exception as e:
        print(f"Error taking IDE window screenshot: {e}")
        return None


def is_project_window_visible(agent_name: str, project_name: str, auto_focus: bool = True) -> bool:
    """
    Returns True if there is a visible and focused window for the given agent and project.
    
    This function checks both:
    1. That the IDE is running with the specified project
    2. That the IDE window with the project is currently focused/frontmost
    
    Args:
        agent_name (str): Name of the IDE application (e.g., "Cursor", "Windsurf")
        project_name (str): Name of the project to check for in window titles
        auto_focus (bool): Whether to automatically bring the window to focus if it's not focused
        
    Returns:
        bool: True if the IDE window for the project is visible and focused, False otherwise
    """
    try:
        if platform.system() != "Darwin":
            print(f"Project window visibility checking not implemented for {platform.system()}")
            return False
            
        agent_name = agent_name.lower()
        
        # First check if the IDE is running with the project
        if not is_ide_open_with_project(agent_name, project_name, verbose=False):
            return False
        
        # Then check if the current focused window belongs to this IDE and project
        current_window = get_current_window_name()
        
        # Get the frontmost process
        success, frontmost_process = _get_frontmost_process()
        if not success:
            print("Could not determine frontmost process")
            return False
        
        # Get expected process name for this IDE
        expected_process = _get_ide_process_name(agent_name)
        display_name = _get_ide_display_name(agent_name)
        
        # Check if the expected IDE is frontmost and current window contains project
        if frontmost_process == expected_process and project_name.lower() in current_window.lower():
            return True
        else:
            # If auto_focus is enabled, try to bring the window to focus
            if auto_focus:
                focus_success = bring_to_front_window(agent_name, project_name)
                if focus_success:
                    # Wait a moment for the window to come to focus
                    import time
                    time.sleep(1.5)
                    
                    # Check again if the window is now focused
                    current_window = get_current_window_name()
                    success, frontmost_process = _get_frontmost_process()
                    
                    if success and frontmost_process == expected_process and project_name.lower() in current_window.lower():
                        return True
                    else:
                        print(f"WARNING: Could not bring {display_name} window for project '{project_name}' to focus")
                        return False
                else:
                    print(f"ERROR: Failed to bring {display_name} window for project '{project_name}' to focus")
                    return False
            else:
                return False
            
    except Exception as e:
        print(f"Error checking if {agent_name} project window is visible: {e}")
        return False
