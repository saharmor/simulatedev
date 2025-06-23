import os
import base64
import io
import subprocess
import pyautogui
import platform
import time
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
        
        # Set target dimensions using the standard calculation
        self.target_width, self.target_height = get_llm_target_dimensions()
        
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
        """Get coordinates and action type from vision model based on a natural language prompt
        
        NOTE: This method always uses full screen screenshots since coordinates need to be 
        relative to the entire screen for accurate clicking operations.
        
        Args:
            prompt: Natural language prompt describing the UI element to find
            support_non_existing_elements: Whether to allow non-existing elements in response
            ide_name: Optional IDE name to provide window context (for prompt enhancement)
            project_name: Optional project name to provide window context (for prompt enhancement)
        """
        try:
            # Check if LLM client is available
            if not llm_client.is_available():
                print("Error: LLM client not available")
                return None
            
            # If IDE info is provided, ensure the window is visible (but not focused)
            # This uses the same visibility checking as _send_prompt_to_interface
            if ide_name and project_name:
                if not is_project_window_visible(ide_name, project_name, auto_focus=True):
                    print(f"WARNING: Could not make {ide_name} window for project '{project_name}' visible, continuing with full screen screenshot")
            
            # Always take a full screen screenshot for coordinate detection
            # This ensures coordinates are relative to the entire screen for accurate clicking
            base64_image_data = take_screenshot(self.target_width, self.target_height, encode_base64=True)
            self.last_screenshot_metadata = ScreenshotMetadata(ScreenshotType.FULL_SCREEN)
            
            # Convert base64 string to BytesIO for llm_client
            image_data = base64.b64decode(base64_image_data)
            image_buffer = io.BytesIO(image_data)
            
            # Enhance the prompt with window title context if IDE parameters are provided
            enhanced_prompt = prompt
            if ide_name and project_name:
                window_title = get_ide_window_title_for_project(ide_name, project_name)
                if window_title:
                    enhanced_prompt = f"{prompt}. Focus on the window titled '{window_title}' if multiple {ide_name} windows are visible."
                else:
                    enhanced_prompt = f"{prompt}. Focus on the {ide_name} window for project '{project_name}' if multiple {ide_name} windows are visible."
            
            # Create the system prompt
            system_prompt = """You are a UI Element Detection AI. Analyze the attached screenshot to locate UI elements.

IMPORTANT: If there is more than one element that matches the prompt, choose the one that is more prominent, for example, the one that is more visible, or the one in the focused and front window.

Use "click" for buttons/links and "type" for text inputs."""

            if support_non_existing_elements:
                system_prompt += """ If the requested UI element is not found in the screenshot, you may indicate this in your response."""
            
            # Use llm_client with structured response
            result = llm_client.analyze_image_with_structured_response(
                image_input=image_buffer,
                prompt=enhanced_prompt,
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
            
            # Scale coordinates using full screen metadata (no window offset needed)
            real_x, real_y = self.scale_coordinates(ScalingSource.API, x, y, self.last_screenshot_metadata)
            
            return ComputerUseAction(
                action_type=action_type,
                coordinates=Coordinates(real_x, real_y)
            )
                
        except Exception as e:
            print(f"Error getting coordinates from LLM: {e}")
            return None


def get_ide_window_title_for_project(ide_name: str, project_name: str) -> Optional[str]:
    """
    Get the specific window title for an IDE project.
    This helps distinguish between multiple IDE windows when providing context to vision models.
    
    Args:
        ide_name: Name of the IDE (cursor, windsurf, etc.)
        project_name: Name of the project to find in window titles
        
    Returns:
        The specific window title if found, None otherwise
    """
    try:
        ide_context = IDEContext.create(ide_name)
        
        # Get window titles for the process
        success, window_titles = AppleScriptRunner.get_process_window_titles(ide_context.process_name)
        
        if not success:
            return None
        
        # Find the matching window title
        matching_window = WindowMatcher.find_window_with_project(window_titles, project_name)
        return matching_window
        
    except Exception as e:
        return None

def get_window_bounds(ide_name: str, project_name: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Get the bounds of a specific IDE window by first finding the correct window title for the project,
    then getting the exact bounds for that window.
    Returns (x, y, width, height) or None if not found.
    """
    ide_context = IDEContext.create(ide_name)
    
    # First, get all window titles for the process
    success, window_titles = AppleScriptRunner.get_process_window_titles(ide_context.process_name)
    if not success:
        return None
    
    # Find the matching window title using WindowMatcher logic
    matching_window_title = WindowMatcher.find_window_with_project(window_titles, project_name)
    if not matching_window_title:
        return None
    
    # Now get the bounds for the exact window title
    applescript = f'''
    tell application "System Events"
        tell process "{ide_context.process_name}"
            set windowList to every window
            repeat with w in windowList
                try
                    if name of w is "{matching_window_title}" then
                        set windowPosition to position of w
                        set windowSize to size of w
                        set x to item 1 of windowPosition
                        set y to item 2 of windowPosition
                        set width to item 1 of windowSize
                        set height to item 2 of windowSize
                        return (x as string) & "," & (y as string) & "," & (width as string) & "," & (height as string)
                    end if
                end try
            end repeat
        end tell
    end tell
    return ""
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            check=True
        )
        bounds = result.stdout.strip()
        if bounds:
            x, y, width, height = map(int, bounds.split(','))
            return (x, y, width, height)
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error getting window bounds: {e.stderr}")
        return None

@darwin_only("Window focusing")
def bring_to_front_window(app_name: str, project_name: str) -> bool:
    """Bring the appropriate IDE window to front above all other applications"""
    try:
        ide_context = IDEContext.create(app_name)
        
        # Validate IDE is running with project
        if not is_ide_open_with_project(ide_context.app_name, project_name, verbose=False):
            print(f"{ide_context.display_name} is not open with project '{project_name}'")
            return False
        
        # Use the more reliable activation method as the primary approach
        comprehensive_script = f'''
        try
            -- Primary method: Use application activation first (more reliable when IDE not visible)
            tell application "{ide_context.display_name if ide_context.process_name == "Electron" else ide_context.process_name}" to activate
            delay 0.5
            
            tell application "System Events"
                tell process "{ide_context.process_name}"
                    set windowList to every window
                    set windowFound to false
                    repeat with w in windowList
                        try
                            if name of w contains "{project_name}" then
                                perform action "AXRaise" of w
                                set windowFound to true
                                exit repeat
                            end if
                        end try
                    end repeat
                    
                    -- Verify the process is frontmost and return result
                    delay 0.2
                    set frontProcess to name of first application process whose frontmost is true
                    if frontProcess is "{ide_context.process_name}" and windowFound then
                        return "success"
                    else if not windowFound then
                        return "window_not_found"
                    else
                        return "not_frontmost:" & frontProcess
                    end if
                end tell
            end tell
        on error errorMessage
            -- If the primary method fails, try the old System Events approach as fallback
            try
                tell application "System Events"
                    tell process "{ide_context.process_name}"
                        set frontmost to true
                        delay 0.3
                        
                        set windowList to every window
                        repeat with w in windowList
                            try
                                if name of w contains "{project_name}" then
                                    perform action "AXRaise" of w
                                    return "success_fallback"
                                end if
                            end try
                        end repeat
                    end tell
                end tell
                return "fallback_window_not_found"
            on error fallbackError
                return "error:" & errorMessage & " | " & fallbackError
            end try
        end try
        '''

        success, output = AppleScriptRunner.run(comprehensive_script)
        
        if not success:
            print(f"Failed to execute window focusing script: {output}")
            return False
        
        result = output.strip()
        
        # Parse the result and provide appropriate feedback
        if result == "success":
            return True
        elif result == "success_fallback":
            return True
        elif result == "window_not_found" or result == "fallback_window_not_found":
            print(f"Could not find window containing '{project_name}' in {ide_context.display_name}")
            return False
        elif result.startswith("not_frontmost:"):
            current_frontmost = result.split(":", 1)[1]
            print(f"WARNING: Expected {ide_context.process_name} to be frontmost, but {current_frontmost} is frontmost")
            return False
        elif result.startswith("error:"):
            error_msg = result.split(":", 1)[1]
            print(f"Error in window focusing: {error_msg}")
            return False
        else:
            print(f"Unexpected result from window focusing: {result}")
            return False
        
    except Exception as e:
        print(f"Error bringing window to front: {e}")
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
        if not is_ide_open_with_project(ide_context.app_name, project_name, verbose=False):
            print(f"{ide_context.display_name} is not open with project '{project_name}'")
            return True  # Nothing to close
        
        # Discover the project window
        success, window_titles = AppleScriptRunner.get_process_window_titles(ide_context.process_name)
        if not success:
            print(f"Could not get window titles for {ide_context.display_name}")
            return True  # Nothing to close
        
        matching_window = WindowMatcher.find_window_with_project(window_titles, project_name)
        if not matching_window:
            print(f"No window found containing project '{project_name}'")
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
    """
    Capture screenshot using mss library with multi-monitor support.
    
    NOTE: This function should be used for coordinate detection operations (e.g., finding input boxes, buttons)
    since it captures the full screen and coordinates are relative to the entire screen for accurate clicking.
    For IDE state monitoring, consider using take_ide_window_screenshot() instead.
    """
    with mss() as sct:
        if monitor_number < 0 or monitor_number >= len(sct.monitors):
            raise ValueError(f"Invalid monitor number. Available monitors: 0-{len(sct.monitors)-1}")
        # Capture specific monitor (add 1 since monitors[0] is the virtual screen)
        screenshot = sct.grab(sct.monitors[monitor_number + 1])
        
        # Convert to PIL Image for resizing
        screenshot = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
        
        return ImageProcessor.process_image_to_buffer(screenshot, target_width, target_height, encode_base64)


@darwin_only("IDE window screenshot")
def take_ide_window_screenshot(ide_name: str, project_name: str, target_width: int = None, target_height: int = None, 
                              encode_base64: bool = False, verbose: bool = False, 
                              return_metadata: bool = False) -> Optional[Union[Union[str, io.BytesIO], Tuple[Union[str, io.BytesIO], ScreenshotMetadata]]]:
    """
    Capture a screenshot of the specific IDE window that contains the project name.
    
    NOTE: This function should ONLY be used for IDE state monitoring (e.g., checking if IDE is done processing).
    For coordinate detection (e.g., finding input boxes, buttons), use take_screenshot() with full screen
    since coordinates need to be relative to the entire screen for accurate clicking.
    
    Args:
        ide_name: Name of the IDE (cursor, windsurf, etc.)
        project_name: Name of the project to find in window titles
        target_width: Target width for the processed image (defaults to LLM standard width)
        target_height: Target height for the processed image (defaults to calculated based on screen aspect ratio)
        encode_base64: Whether to return base64 encoded string instead of BytesIO
        verbose: Whether to print detailed error messages
        return_metadata: Whether to return metadata along with the image
        
    Returns:
        If return_metadata=False: Image data as string (base64) or BytesIO
        If return_metadata=True: Tuple of (image_data, ScreenshotMetadata)
        None if screenshot failed
    """
    try:
        # Calculate target dimensions using the same logic as LLMComputerUse class
        if target_width is None or target_height is None:
            calculated_width, calculated_height = get_llm_target_dimensions()
            if target_width is None:
                target_width = calculated_width
            if target_height is None:
                target_height = calculated_height
        
        ide_context = IDEContext.create(ide_name)
        
        # Validate IDE is running with project
        if not is_ide_open_with_project(ide_context.app_name, project_name, verbose=False):
            if verbose:
                print(f"{ide_context.display_name} is not open with project '{project_name}'")
            return None
        
        # Check if the window is already visible/accessible before attempting to focus
        bounds = get_window_bounds(ide_name, project_name)
        
        # If bounds is None, it means we couldn't find the window, so return None
        if not bounds:
            if verbose:
                print(f"Could not get bounds for window with project '{project_name}' in {ide_name}")
            return None
        
        x, y, width, height = bounds
        
        # Create a temporary file for the screenshot
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        # Take screenshot using screencapture with window bounds
        cmd = [
            'screencapture',
            '-x',  # suppress sound
            '-R', f'{x},{y},{width},{height}',
            path
        ]
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            if verbose:
                print(f"Error taking screenshot: {e}")
            os.unlink(path)
            return None
        
        # Open and process the image
        image = Image.open(path)
        original_width, original_height = image.size
        
        # Create metadata
        metadata = ScreenshotMetadata(
            screenshot_type=ScreenshotType.WINDOW_SPECIFIC,
            window_x=x,
            window_y=y,
            original_width=original_width,
            original_height=original_height
        )
        
        # Delete the temporary file
        os.unlink(path)
        
        # Process the image using the calculated target dimensions
        processed_image = ImageProcessor.process_image_to_buffer(image, target_width, target_height, encode_base64)
        
        if verbose:
            print(f"Successfully captured screenshot: {original_width}x{original_height} -> {target_width}x{target_height}")
        
        # Return based on whether metadata is requested
        if return_metadata:
            return processed_image, metadata
        else:
            return processed_image
            
    except Exception as e:
        if verbose:
            print(f"Error taking IDE window screenshot: {e}")
        return None

@darwin_only("Project window visibility checking")
def is_project_window_visible(agent_name: str, project_name: str, auto_focus: bool = True) -> bool:
    """Returns True if there is a visible window for the given agent and project (focus not required)"""
    try:
        ide_context = IDEContext.create(agent_name)
        
        # First check if the IDE is running with the project
        if not is_ide_open_with_project(ide_context.app_name, project_name, verbose=False):
            return False
        
        # Check if the window is accessible (visible)
        bounds = get_window_bounds(agent_name, project_name)
        if bounds:
            # Window is already visible and accessible
            return True
        
        # If auto_focus is disabled, don't try to make it visible
        if not auto_focus:
            return False
        
        # Window is not visible - try to bring it to front (without stealing focus)
        focus_success = bring_to_front_window(agent_name, project_name)
        if focus_success:
            # Wait a moment for the window to become visible
            time.sleep(0.5)
            
            # Check again if the window is now visible/accessible
            bounds = get_window_bounds(agent_name, project_name)
            if bounds:
                return True
            else:
                print(f"WARNING: Could not make {ide_context.display_name} window for project '{project_name}' visible")
                return False
        else:
            print(f"ERROR: Failed to bring {ide_context.display_name} window for project '{project_name}' to front")
            return False
            
    except Exception as e:
        print(f"Error checking if {agent_name} project window is visible: {e}")
        return False

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

def get_llm_target_dimensions() -> Tuple[int, int]:
    """
    Calculate the standard target dimensions used by LLM for screenshots.
    This ensures consistency across all screenshot operations.
    
    Returns:
        Tuple of (target_width, target_height)
    """
    screen_width, screen_height = pyautogui.size()
    target_width = 1280  # LLM's standard max screenshot width
    target_height = int(screen_height * (target_width / screen_width))
    return target_width, target_height