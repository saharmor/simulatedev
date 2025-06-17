import os
import base64
import io
import subprocess
import pyautogui
import platform
from enum import Enum
from typing import Optional, Tuple, List, Union
from dotenv import load_dotenv
from dataclasses import dataclass
from mss import mss
from PIL import Image
from functools import wraps
from .llm_client import llm_client, ActionResponse

load_dotenv()

class ScalingSource(Enum):
    API = 1      # Coordinates from API (need to be scaled to real screen)
    SCREEN = 2   # Coordinates from screen (need to be scaled to API format)

class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"

class ScreenshotType(Enum):
    FULL_SCREEN = "full_screen"
    WINDOW_SPECIFIC = "window_specific"

@dataclass
class Coordinates:
    x: int
    y: int

@dataclass
class ComputerUseAction:
    action_type: ActionType
    coordinates: Coordinates

@dataclass
class ScreenshotMetadata:
    """Metadata about how a screenshot was captured"""
    screenshot_type: ScreenshotType
    window_x: int = 0  # Window position on screen (for window screenshots)
    window_y: int = 0  # Window position on screen (for window screenshots)
    original_width: int = 0  # Original screenshot dimensions
    original_height: int = 0  # Original screenshot dimensions
    
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

def darwin_only(operation_name: str):
    """Decorator to ensure function only runs on macOS"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if platform.system() != "Darwin":
                print(f"{operation_name} not implemented for {platform.system()}")
                return None if func.__annotations__.get('return') == Optional[str] else False
            return func(*args, **kwargs)
        return wrapper
    return decorator

@dataclass
class IDEContext:
    """Context object for IDE operations"""
    app_name: str
    process_name: str
    display_name: str
    
    @classmethod
    def create(cls, app_name: str) -> 'IDEContext':
        """Create IDE context from app name"""
        app_name_lower = app_name.lower()
        if app_name_lower in IDE_CONFIG:
            config = IDE_CONFIG[app_name_lower]
            return cls(
                app_name=app_name_lower,
                process_name=config["process_name"],
                display_name=config["display_name"]
            )
        else:
            capitalized = app_name.capitalize()
            return cls(
                app_name=app_name_lower,
                process_name=capitalized,
                display_name=capitalized
            )

class WindowMatcher:
    """Handles window matching logic with multiple strategies"""
    
    @staticmethod
    def find_window_with_project(window_titles: List[str], project_name: str) -> Optional[str]:
        """Find a window title that matches the project name using comprehensive matching"""
        if not window_titles or not project_name:
            return None
        
        project_name_lower = project_name.lower()
        
        # Try each window title with comprehensive matching
        for title in window_titles:
            if WindowMatcher.window_matches_project(title, project_name):
                return title
        
        return None
    
    @staticmethod
    def window_matches_project(window_title: str, project_name: str) -> bool:
        """Check if a window title matches the project name using improved matching logic"""
        if not window_title or not project_name:
            return False
        
        window_title_lower = window_title.lower()
        project_name_lower = project_name.lower()
        
        # Strategy 1: Exact match
        if window_title_lower == project_name_lower:
            return True
        
        # Strategy 2: Window title ends with " - projectname" or " — projectname"
        if (window_title_lower.endswith(f" - {project_name_lower}") or 
            window_title_lower.endswith(f" — {project_name_lower}")):
            return True
        
        # Strategy 3: Window title starts with "projectname - " or "projectname — "
        if (window_title_lower.startswith(f"{project_name_lower} - ") or 
            window_title_lower.startswith(f"{project_name_lower} — ")):
            return True
        
        # Strategy 4: Project name surrounded by separators
        separators = [" - ", " — ", " | ", " :: ", " / "]
        for sep in separators:
            if f"{sep}{project_name_lower}{sep}" in window_title_lower:
                return True
        
        # Strategy 5: Fallback to simple substring match
        if project_name_lower in window_title_lower:
            return True
        
        return False

class AppleScriptRunner:
    """Handles AppleScript execution"""
    
    @staticmethod
    def run(script: str) -> Tuple[bool, str]:
        """Run an AppleScript and return success status and output"""
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip() if e.stderr else "AppleScript execution failed"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_process_window_titles(process_name: str) -> Tuple[bool, List[str]]:
        """Get all window titles for a given process"""
        script = f'''
        tell application "System Events"
            tell process "{process_name}"
                set windowTitles to name of every window
            end tell
        end tell
        return windowTitles
        '''
        
        success, output = AppleScriptRunner.run(script)
        if success:
            # Handle empty output or single empty string
            if not output or output == '""' or output == "":
                return True, []
            window_titles = [title.strip().strip('"') for title in output.split(",")]
            return True, window_titles
        else:
            return False, []
    
    @staticmethod
    def get_frontmost_process() -> Tuple[bool, str]:
        """Get the name of the frontmost process"""
        script = '''
        tell application "System Events"
            set frontProcess to name of first application process whose frontmost is true
        end tell
        return frontProcess
        '''
        return AppleScriptRunner.run(script)
    
    @staticmethod
    def get_window_position(process_name: str, window_name: str) -> Tuple[bool, int, int]:
        """Get the position of a specific window"""
        script = f'''
        tell application "System Events"
            tell process "{process_name}"
                repeat with w in windows
                    if name of w is "{window_name}" then
                        set windowPosition to position of w
                        set x to item 1 of windowPosition
                        set y to item 2 of windowPosition
                        return x & "," & y
                    end if
                end repeat
            end tell
        end tell
        return "0,0"
        '''
        
        success, output = AppleScriptRunner.run(script)
        if success and "," in output:
            try:
                x, y = map(int, output.split(","))
                return True, x, y
            except ValueError:
                return False, 0, 0
        return False, 0, 0

class WindowOperations:
    """Handles common window operations"""
    
    @staticmethod
    def validate_ide_with_project(ide_context: IDEContext, project_name: str) -> bool:
        """Check if IDE is running with the specified project"""
        return is_ide_open_with_project(ide_context.app_name, project_name, verbose=False)
    
    @staticmethod
    def discover_project_window(ide_context: IDEContext, project_name: str) -> Optional[str]:
        """Discover the window that contains the project"""
        success, window_titles = AppleScriptRunner.get_process_window_titles(ide_context.process_name)
        if not success:
            print(f"Could not get window titles for {ide_context.display_name}")
            return None
        
        matching_window = WindowMatcher.find_window_with_project(window_titles, project_name)
        if not matching_window:
            print(f"No window found containing project '{project_name}'")
            return None
        
        return matching_window
    
    @staticmethod
    def check_window_focus(ide_context: IDEContext, project_name: str) -> bool:
        """Check if the IDE window with project is currently focused"""
        current_window = get_current_window_name()
        success, frontmost_process = AppleScriptRunner.get_frontmost_process()
        
        if not success:
            print("Could not determine frontmost process")
            return False
        
        return (frontmost_process == ide_context.process_name and 
                WindowMatcher.window_matches_project(current_window, project_name))

class ImageProcessor:
    """Handles image processing operations"""
    
    @staticmethod
    def process_image_to_buffer(image: Image.Image, target_width: int, target_height: int, 
                              encode_base64: bool = False) -> Union[str, io.BytesIO]:
        """Process image and return as base64 string or BytesIO buffer"""
        # Resize to target dimensions
        image = image.resize((target_width, target_height))
        
        # Save to in-memory buffer
        img_buffer = io.BytesIO()
        image.save(img_buffer, format="PNG", optimize=True)
        img_buffer.seek(0)
        
        if encode_base64:
            return base64.b64encode(img_buffer.read()).decode()
        else:
            return img_buffer

class LLMComputerUse:
    """Enhanced class to interact with LLM Computer Use with proper coordinate scaling"""
    
    def __init__(self):
        # Get the actual screen dimensions
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Set target dimensions (what LLM expects)
        self.target_width = 1280  # LLM's max screenshot width
        self.target_height = int(self.screen_height * (self.target_width / self.screen_width))
        
        # Track screenshot metadata for coordinate scaling
        self.last_screenshot_metadata: Optional[ScreenshotMetadata] = None
    
    def scale_coordinates(self, source: ScalingSource, x: int, y: int, 
                         metadata: Optional[ScreenshotMetadata] = None) -> Tuple[int, int]:
        """Scale coordinates between LLM's coordinate system and real screen coordinates"""
        
        # Use provided metadata or fall back to last screenshot metadata
        screenshot_metadata = metadata or self.last_screenshot_metadata
        
        if screenshot_metadata and screenshot_metadata.screenshot_type == ScreenshotType.WINDOW_SPECIFIC:
            # For window-specific screenshots, we need to:
            # 1. Scale from target dimensions to original window dimensions
            # 2. Offset by window position on screen
            
            if source == ScalingSource.API:
                # LLM coordinates (based on target_width/height) -> real screen coordinates
                
                # First, scale from target dimensions to original window dimensions
                window_x_scale = screenshot_metadata.original_width / self.target_width
                window_y_scale = screenshot_metadata.original_height / self.target_height
                
                window_x = round(x * window_x_scale)
                window_y = round(y * window_y_scale)
                
                # Then offset by window position on screen
                screen_x = window_x + screenshot_metadata.window_x
                screen_y = window_y + screenshot_metadata.window_y
                
                return screen_x, screen_y
            else:
                # Real screen coordinates -> LLM coordinate system
                # First, subtract window offset
                window_x = x - screenshot_metadata.window_x
                window_y = y - screenshot_metadata.window_y
                
                # Then scale from original window dimensions to target dimensions
                window_x_scale = self.target_width / screenshot_metadata.original_width
                window_y_scale = self.target_height / screenshot_metadata.original_height
                
                target_x = round(window_x * window_x_scale)
                target_y = round(window_y * window_y_scale)
                
                return target_x, target_y
        else:
            # Full screen scaling (original behavior)
            x_scaling_factor = self.screen_width / self.target_width
            y_scaling_factor = self.screen_height / self.target_height
            
            if source == ScalingSource.API:
                # LLM's coordinates -> real screen coordinates
                return round(x * x_scaling_factor), round(y * y_scaling_factor)
            else:
                # Real screen coordinates -> LLM's coordinate system
                return round(x / x_scaling_factor), round(y / y_scaling_factor)
    
    async def get_coordinates_from_vision_model(self, prompt: str, support_non_existing_elements: bool = False, 
                                               ide_name: str = None, project_name: str = None) -> Optional[ComputerUseAction]:
        """Get coordinates and action type from vision model based on a natural language prompt"""
        try:
            # Check if LLM client is available
            if not llm_client.is_available():
                print("Error: LLM client not available")
                return None
            
            # Take a screenshot - use IDE window screenshot if both ide_name and project_name are provided
            screenshot_metadata = None
            if ide_name and project_name:
                screenshot_result = take_ide_window_screenshot_with_metadata(ide_name, project_name, self.target_width, self.target_height, encode_base64=True)
                if screenshot_result:
                    base64_image_data, screenshot_metadata = screenshot_result
                    self.last_screenshot_metadata = screenshot_metadata
                else:
                    print(f"WARNING: Could not capture {ide_name} window for project '{project_name}'. Falling back to full screen.")
                    base64_image_data = take_screenshot(self.target_width, self.target_height, encode_base64=True)
                    self.last_screenshot_metadata = ScreenshotMetadata(ScreenshotType.FULL_SCREEN)
            else:
                base64_image_data = take_screenshot(self.target_width, self.target_height, encode_base64=True)
                self.last_screenshot_metadata = ScreenshotMetadata(ScreenshotType.FULL_SCREEN)
            
            # Convert base64 string to BytesIO for llm_client
            image_data = base64.b64decode(base64_image_data)
            image_buffer = io.BytesIO(image_data)
            
            # Create the system prompt
            system_prompt = """You are a UI Element Detection AI. Analyze the attached screenshot to locate UI elements.

IMPORTANT: If there is more than one element that matches the prompt, choose the one that is more prominent, for example, the one that is more visible, or the one in the focused and front window.

Use "click" for buttons/links and "type" for text inputs."""

            if support_non_existing_elements:
                system_prompt += """ If the requested UI element is not found in the screenshot, you may indicate this in your response."""
            
            # Use llm_client with structured response
            result = llm_client.analyze_image_with_structured_response(
                image_input=image_buffer,
                prompt=prompt,
                response_model=ActionResponse,
                system_prompt=system_prompt,
                max_tokens=1024
            )
            
            if not result:
                print("Error getting response from LLM: No response received")
                return None
            
            # Extract action type and coordinates from the Pydantic model
            action_type_str = result.action.type
            action_type = ActionType.CLICK if action_type_str == "click" else ActionType.TYPE
            
            x = result.action.coordinates.x
            y = result.action.coordinates.y
            
            # Scale coordinates using the appropriate metadata
            real_x, real_y = self.scale_coordinates(ScalingSource.API, x, y, screenshot_metadata)
            
            return ComputerUseAction(
                action_type=action_type,
                coordinates=Coordinates(real_x, real_y)
            )
                
        except Exception as e:
            print(f"Error getting coordinates from LLM: {e}")
            return None

# Legacy function - kept for backward compatibility but simplified
def get_windsurf_project_window_name(project_contained_name: str):
    """Get Windsurf project window name since it runs as an Electron app"""
    success, window_titles = AppleScriptRunner.get_process_window_titles("Electron")
    if success:
        return WindowMatcher.find_window_with_project(window_titles, project_contained_name)
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

@darwin_only("Window focusing")
def bring_to_front_window(app_name: str, project_name: str) -> bool:
    """Focus the appropriate IDE window that contains the project name"""
    try:
        ide_context = IDEContext.create(app_name)
        
        # Validate IDE is running with project
        if not WindowOperations.validate_ide_with_project(ide_context, project_name):
            print(f"{ide_context.display_name} is not open with project '{project_name}'")
            return False
        
        # Discover the project window
        matching_window = WindowOperations.discover_project_window(ide_context, project_name)
        if not matching_window:
            return False
        
        # Use AppleScript to bring the specific window to front without affecting other windows
        script = f'''
        tell application "System Events"
            tell process "{ide_context.process_name}"
                repeat with w in windows
                    if name of w is "{matching_window}" then
                        perform action "AXRaise" of w
                        set position of w to {{0, 0}}
                        delay 0.5
                        exit repeat
                    end if
                end repeat
                set frontmost to true
            end tell
        end tell
        '''

        success, _ = AppleScriptRunner.run(script)
        if not success:
            print(f"Failed to bring {ide_context.display_name} window for project '{project_name}' to focus")
            return False

        return True
        
    except Exception as e:
        print(f"Error focusing window: {e}")
        return False

def wait_for_focus(app_name, timeout=10):
    """Wait until the specified app is frontmost"""
    ide_context = IDEContext.create(app_name)
    
    script = f'''
    tell application "System Events"
        repeat until (name of first application process whose frontmost is true) is "{ide_context.process_name}"
            delay 0.5
        end repeat
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        print(f"Timed out waiting for {app_name} (process: {ide_context.process_name}) to become active.")
        return False
    except Exception as e:
        print(f"Error waiting for focus: {str(e)}")
        return False

def get_current_window_name():
    """Get the name of the currently active window, with robust error handling"""
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
    
    success, output = AppleScriptRunner.run(script)
    if success:
        return output
    else:
        print(f"Warning: AppleScript error when getting window name: {output}")
        return "Unknown Window"

@darwin_only("IDE project checking")
def is_ide_open_with_project(app_name: str, project_name: str, verbose: bool = True) -> bool:
    """Check if a specific IDE is running and has the specified project open"""
    try:
        ide_context = IDEContext.create(app_name)
        
        # Get window titles for the process
        success, window_titles = AppleScriptRunner.get_process_window_titles(ide_context.process_name)
        
        if not success:
            if verbose:
                print(f"{ide_context.display_name} ({ide_context.process_name}) is not running")
            return False
        
        # Check if any window title contains the project name
        matching_window = WindowMatcher.find_window_with_project(window_titles, project_name)
        
        if matching_window:
            if verbose:
                print(f"Found {ide_context.display_name} window with project '{project_name}': {matching_window}")
            return True
        else:
            if verbose:
                print(f"{ide_context.display_name} is running but no window found with project '{project_name}'")
                print(f"Available windows: {window_titles}")
            return False
            
    except Exception as e:
        if verbose:
            print(f"Error checking if {app_name} is open with project '{project_name}': {e}")
        return False

@darwin_only("IDE window closing")
def close_ide_window_for_project(app_name: str, project_name: str) -> bool:
    """Close a specific IDE window that contains the project name"""
    try:
        ide_context = IDEContext.create(app_name)
        
        # Validate IDE is running with project
        if not WindowOperations.validate_ide_with_project(ide_context, project_name):
            print(f"{ide_context.display_name} is not open with project '{project_name}'")
            return True  # Nothing to close
        
        # Discover the project window
        matching_window = WindowOperations.discover_project_window(ide_context, project_name)
        if not matching_window:
            return True  # Nothing to close
        
        # Use AppleScript to close the specific window by exact title match
        close_script = f'''
        tell application "System Events"
            tell process "{ide_context.process_name}"
                repeat with w in windows
                    if name of w is "{matching_window}" then
                        click button 1 of w
                        exit repeat
                    end if
                end repeat
            end tell
        end tell
        '''
        
        success, _ = AppleScriptRunner.run(close_script)
        if success:
            return True
        else:
            print(f"ERROR: Failed to close {app_name} window for project '{project_name}'")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to close {app_name} window for project '{project_name}': {e}")
        return False

def take_screenshot(target_width, target_height, encode_base64: bool = False, monitor_number: int = 0) -> Union[str, io.BytesIO]:
    """Capture screenshot using mss library with multi-monitor support"""
    with mss() as sct:
        if monitor_number < 0 or monitor_number >= len(sct.monitors):
            raise ValueError(f"Invalid monitor number. Available monitors: 0-{len(sct.monitors)-1}")
        # Capture specific monitor (add 1 since monitors[0] is the virtual screen)
        screenshot = sct.grab(sct.monitors[monitor_number + 1])
        
        # Convert to PIL Image for resizing
        screenshot = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
        
        return ImageProcessor.process_image_to_buffer(screenshot, target_width, target_height, encode_base64)

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

@darwin_only("IDE window screenshot")
def take_ide_window_screenshot(ide_name: str, project_name: str, target_width: int = 1280, target_height: int = 720, 
                              encode_base64: bool = False, verbose: bool = False) -> Optional[Union[str, io.BytesIO]]:
    """Capture a screenshot of the specific IDE window that contains the project name"""
    result = take_ide_window_screenshot_with_metadata(ide_name, project_name, target_width, target_height, encode_base64, verbose)
    if result:
        return result[0]  # Return just the image data, not the metadata
    return None

@darwin_only("IDE window screenshot with metadata")
def take_ide_window_screenshot_with_metadata(ide_name: str, project_name: str, target_width: int = 1280, target_height: int = 720, 
                                           encode_base64: bool = False, verbose: bool = False) -> Optional[Tuple[Union[str, io.BytesIO], ScreenshotMetadata]]:
    """Capture a screenshot of the specific IDE window and return both image data and metadata"""
    try:
        ide_context = IDEContext.create(ide_name)
        
        # Validate IDE is running with project
        if not WindowOperations.validate_ide_with_project(ide_context, project_name):
            print(f"{ide_context.display_name} is not open with project '{project_name}'")
            return None
        
        # Discover the project window
        matching_window = WindowOperations.discover_project_window(ide_context, project_name)
        if not matching_window:
            return None
        
        # IMPORTANT: Bring the window to focus before taking screenshot
        focus_success = bring_to_front_window(ide_name, project_name)
        if not focus_success:
            print(f"Warning: Could not bring {ide_context.display_name} window to focus, but continuing...")
        else:
            # Wait a moment for the window to come to focus
            import time
            time.sleep(1.5)
        
        # Get window position for coordinate scaling
        window_pos_success, window_x, window_y = AppleScriptRunner.get_window_position(ide_context.process_name, matching_window)
        if not window_pos_success:
            window_x, window_y = 0, 0
        
        # Create a temporary file for the screenshot
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        # Use AppleScript to ensure the specific window is frontmost and capture it
        script = f'''
        tell application "System Events"
            tell process "{ide_context.process_name}"
                set targetWindow to window "{matching_window}"
                if exists targetWindow then
                    perform action "AXRaise" of targetWindow
                    delay 1.0
                end if
                set frontmost to true
            end tell
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
        
        screenshot_type = ScreenshotType.WINDOW_SPECIFIC
        
        if window_id:
            # Capture the specific window
            subprocess.run(["screencapture", "-l", window_id, path], check=True)
        else:
            # Fallback to full screen if window ID not found
            if verbose:
                print(f"Warning: Could not find window ID for '{matching_window}', falling back to full screen")
            subprocess.run(["screencapture", "-x", path], check=True)
            screenshot_type = ScreenshotType.FULL_SCREEN
            window_x, window_y = 0, 0
        
        # Open and process the image
        image = Image.open(path)
        original_width, original_height = image.size
        
        # Create metadata
        metadata = ScreenshotMetadata(
            screenshot_type=screenshot_type,
            window_x=window_x,
            window_y=window_y,
            original_width=original_width,
            original_height=original_height
        )
        
        # Delete the temporary file
        os.unlink(path)
        
        # Process the image
        processed_image = ImageProcessor.process_image_to_buffer(image, target_width, target_height, encode_base64)
        
        return processed_image, metadata
            
    except Exception as e:
        print(f"Error taking IDE window screenshot: {e}")
        return None

@darwin_only("Project window visibility checking")
def is_project_window_visible(agent_name: str, project_name: str, auto_focus: bool = True) -> bool:
    """Returns True if there is a visible and focused window for the given agent and project"""
    try:
        ide_context = IDEContext.create(agent_name)
        
        # First check if the IDE is running with the project
        if not WindowOperations.validate_ide_with_project(ide_context, project_name):
            return False
        
        # Check if the window is currently focused
        if WindowOperations.check_window_focus(ide_context, project_name):
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
                    if WindowOperations.check_window_focus(ide_context, project_name):
                        return True
                    else:
                        print(f"WARNING: Could not bring {ide_context.display_name} window for project '{project_name}' to focus")
                        return False
                else:
                    print(f"ERROR: Failed to bring {ide_context.display_name} window for project '{project_name}' to focus")
                    return False
            else:
                return False
            
    except Exception as e:
        print(f"Error checking if {agent_name} project window is visible: {e}")
        return False
