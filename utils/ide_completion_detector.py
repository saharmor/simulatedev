#!/usr/bin/env python3
"""
IDE Completion Detector

This utility monitors an IDE through screenshots and uses image analysis
to detect when the IDE has finished a task. It can be used to automate
workflows that depend on IDE operations completing.
"""
import os
import sys
import json
import time
import subprocess
from PIL import Image
from dotenv import load_dotenv

from utils.computer_use_utils import get_window_bounds, take_screenshot, LLMComputerUse, take_ide_window_screenshot
from utils.llm_client import analyze_ide_state_with_llm
import pyautogui

def get_window_list():
    """
    Get a list of all open windows using osascript (macOS only).
    
    Returns:
        list: A list of dictionaries containing window information.
    """
    try:
        # AppleScript to get windows
        script = '''
        set output to ""
        tell application "System Events"
            set allProcesses to processes whose background only is false
            repeat with theProcess in allProcesses
                set processName to name of theProcess
                set pid to unix id of theProcess
                if exists (windows of theProcess) then
                    repeat with theWindow in windows of theProcess
                        set windowName to name of theWindow
                        if windowName is not "" then
                            set output to output & processName & "###" & windowName & "###" & pid & "\n"
                        end if
                    end repeat
                end if
            end repeat
        end tell
        return output
        '''
        
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error getting window list: {result.stderr}")
            return []
        
        # Parse the output
        windows = []
        for line in result.stdout.strip().split("\n"):
            if line.strip() == "":
                continue
                
            parts = line.split("###")
            if len(parts) >= 3:
                window = {
                    'app_name': parts[0],
                    'window_title': parts[1],
                    'pid': int(parts[2]) if parts[2].isdigit() else 0
                }
                windows.append(window)
        
        return windows
        
    except Exception as e:
        print(f"Error getting window list: {e}")
        return []

def find_window_by_title(title_substring, app_name=None):
    """
    Find a window by its title (substring match) and optionally filter by app name.
    Non-interactive version.
    
    Args:
        title_substring (str): A substring of the window title to match.
        app_name (str, optional): Application name to filter by. Defaults to None.
        
    Returns:
        dict: Window information if found, None otherwise.
    """
    try:
        windows = get_window_list()
        matching_windows = []
        
        if not windows:
            print("No windows found")
            return None
        
        # Filter windows by title substring and optionally by app name
        for window in windows:
            if 'window_title' in window and 'app_name' in window:
                title_match = title_substring.lower() in window['window_title'].lower()
                app_match = app_name is None or (window['app_name'].lower() == app_name.lower())
                
                if title_match and app_match:
                    matching_windows.append(window)
        
        if not matching_windows:
            print(f"No windows found matching '{title_substring}'{f' in app {app_name}' if app_name else ''}")
            return None
        
        # Just take the first matching window in non-interactive mode
        return matching_windows[0]
            
    except Exception as e:
        print(f"Error finding window: {e}")
        return None

def capture_screen():
    """
    Capture the entire screen.
    
    Returns:
        PIL.Image: The captured screenshot as a PIL Image.
    """
    try:
        import tempfile
        
        # Create a temporary file for the screenshot
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        # Use screencapture command on macOS
        subprocess.run(["screencapture", "-x", path], check=True)
        
        # Open and return the image
        image = Image.open(path)
        
        # Delete the temporary file
        os.unlink(path)
        
        return image
    except Exception as e:
        print(f"Error capturing screen: {e}")
        return None

def capture_window_by_title(title_substring, app_name=None):
    """
    Capture a window by its title (substring match).
    
    Args:
        title_substring (str): A substring of the window title to match.
        app_name (str, optional): Application name to filter by. Defaults to None.
        
    Returns:
        tuple: (PIL.Image, window_info) if successful, (None, None) otherwise.
    """
    try:
        window = find_window_by_title(title_substring, app_name)
        
        if not window:
            return None, None
            
        import tempfile
        
        # Create a temporary file for the screenshot
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        
        # Use screencapture command with window name
        title = window['window_title']
        script = f'''
        tell application "System Events"
            tell process "{window['app_name']}"
                set targetWindow to window "{title}"
                if exists targetWindow then
                    perform action "AXRaise" of targetWindow
                    set position of targetWindow to {{0, 0}}
                    delay 0.5
                end if
                set frontmost to true
            end tell
        end tell
        '''
        
        # Run the AppleScript to bring window to front
        subprocess.run(["osascript", "-e", script], capture_output=True)
        
        # Capture the window by name
        cmd = ["screencapture", "-l"]
        
        # Find the window ID
        list_cmd = ["screencapture", "-C", "-L"]
        list_result = subprocess.run(list_cmd, capture_output=True, text=True)
        window_id = None
        
        for line in list_result.stdout.splitlines():
            if title in line:
                window_id = line.split(':')[0].strip()
                break
        
        if not window_id:
            # Fallback to full screen if window ID not found
            subprocess.run(["screencapture", "-x", path], check=True)
        else:
            subprocess.run(["screencapture", "-l", window_id, path], check=True)
        
        # Open the image
        image = Image.open(path)
        
        # Delete the temporary file
        os.unlink(path)
        
        return image, window
        
    except Exception as e:
        print(f"Error capturing window: {e}")
        return None, None

def initialize_llm_client():
    """
    Initialize the LLM client (supports both OpenAI and Anthropic providers).
    
    Returns:
        bool: True if initialization is successful, False otherwise.
    """
    try:
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Import the global LLM client
        from utils.llm_client import llm_client
        
        # Check if LLM client is available
        if not llm_client.is_available():
            provider = llm_client.provider
            if provider == "anthropic":
                print("Error: ANTHROPIC_API_KEY environment variable not set or unavailable.")
                print("Please create a .env file with the line: ANTHROPIC_API_KEY=your_api_key_here")
            elif provider == "openai":
                print("Error: OPENAI_API_KEY environment variable not set or unavailable.")
                print("Please create a .env file with the line: OPENAI_API_KEY=your_api_key_here")
            else:
                print(f"Error: Invalid LLM provider '{provider}'. Please set LLM_PROVIDER to 'anthropic' or 'openai'.")
            return False
        
        print(f"Successfully initialized LLM client using {llm_client.provider.upper()} provider")
        return True
    except Exception as e:
        print(f"Error initializing LLM client: {e}")
        return False

def analyze_ide_state(interface_state_analysis_prompt, ide_name=None, project_name=None, save_debug_screenshot=False, screenshot_count=None):
    """
    Analyze a screenshot to determine if the IDE has finished processing.
    This function handles screenshot capture internally and will try IDE window screenshot first,
    falling back to full screen if the IDE window is not available.
    
    Args:
        interface_state_analysis_prompt (str): Prompt for IDE state analysis.
        ide_name (str, optional): Name of the IDE for enhanced visibility detection.
        project_name (str, optional): Name of the project for enhanced visibility detection.
        save_debug_screenshot (bool, optional): Whether to save screenshot for debugging.
        screenshot_count (int, optional): Counter for debug screenshot naming.
        
    Returns:
        tuple: (bool, str, str) - (Whether the IDE is done, State, Reasoning)
    """
    try:
        # If we have IDE info, try to take an IDE window screenshot first
        image_input = None
        if ide_name and project_name:
            # Try to capture IDE window screenshot
            image_input = take_ide_window_screenshot(ide_name, project_name, verbose=False)
            
        # If IDE window screenshot failed or we don't have IDE info, use full screen
        if image_input is None:
            from utils.computer_use_utils import get_llm_target_dimensions
            target_width, target_height = get_llm_target_dimensions()
            image_input = take_screenshot(target_width, target_height)
            
            # If we tried IDE window but fell back to full screen, this likely means IDE is not visible
            if ide_name and project_name:
                print(f"Could not capture {ide_name} window screenshot, using full screen (IDE may not be visible)")
        
        # Save debug screenshot if requested
        if save_debug_screenshot and screenshot_count is not None and ide_name and project_name:
            save_image_to_file(image_input, ide_name, project_name, screenshot_count)
        
        # Use the shared Claude client for IDE state analysis
        return analyze_ide_state_with_llm(image_input, interface_state_analysis_prompt, ide_name, project_name)
    except Exception as e:
        print(f"Error analyzing IDE state: {e}")
        return False, f"error: {str(e)}", str(e)

async def click_ide_resume_button(resume_button_prompt, ide_name=None, project_name=None):
    """
    Find and click the resume button using the provided prompt.
    
    Args:
        resume_button_prompt (str): Prompt for finding the resume button.
        ide_name (str, optional): Name of the IDE (used for window context).
        project_name (str, optional): Name of the project (used for window context).
        
    Returns:
        bool: True if button was found and clicked, False otherwise.
    """
    try:
        # Initialize Claude Computer Use for finding the button
        computer_use_client = LLMComputerUse()
        
        # Look for the Resume button using full screen screenshot with window context
        # The ide_name and project_name help the vision model focus on the correct window
        # when multiple IDE instances are open
        result = await computer_use_client.get_coordinates_from_vision_model(
            resume_button_prompt,
            support_non_existing_elements=True,
            ide_name=ide_name,
            project_name=project_name
        )
        
        if result and result.coordinates:
            print(f"Found resume button at coordinates ({result.coordinates.x}, {result.coordinates.y})")
            
            # Click the resume button
            pyautogui.moveTo(result.coordinates.x, result.coordinates.y, duration=0.5)
            time.sleep(0.5)
            pyautogui.click(result.coordinates.x, result.coordinates.y)
            time.sleep(2.0)  # Wait a bit for the resume to take effect
            print("Successfully clicked resume button")
            return True
        else:
            print("Could not find resume button")
            return False
            
    except Exception as e:
        print(f"Error clicking resume button: {e}")
        return False

def save_image_to_file(image, ide_name, project_name, screenshot_count):
    """
    Save an image to a file.
    
    Args:
        image: The image to save (can be PIL Image or BytesIO object).
        ide_name (str): Name of the IDE.
        project_name (str): Name of the project.
        screenshot_count (int): The number of the screenshot.
    """
    try:
        import io
        from common.config import config
        
        # Create screenshots directory in execution output
        screenshots_dir = os.path.join(config.execution_output_path, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Save the image to the screenshots directory
        image_path = os.path.join(screenshots_dir, f"{ide_name}_{project_name}_{screenshot_count}.png")
        
        # Handle both PIL Image and BytesIO objects
        if isinstance(image, io.BytesIO):
            # If it's a BytesIO object, convert to PIL Image first
            image.seek(0)  # Reset position to beginning
            pil_image = Image.open(image)
            pil_image.save(image_path)
        else:
            # Assume it's already a PIL Image
            image.save(image_path)
            
        print(f"Debug screenshot saved to: {image_path}")
    except Exception as e:
        print(f"Error saving image to file: {e}")


async def wait_until_ide_finishes(ide_name, interface_state_analysis_prompt, timeout_in_seconds, resume_button_prompt=None, require_two_subsequent_done_states=False, project_name=None, save_screenshots_for_debug=False):
    """
    Wait until the specified IDE finishes processing.
    
    Args:
        ide_name (str): Name of the IDE to monitor.
        interface_state_analysis_prompt (str): Prompt for analyzing IDE state.
        timeout_in_seconds (int): Maximum time to wait in seconds for THIS execution.
        resume_button_prompt (str, optional): Prompt for finding the resume button.
        require_two_subsequent_done_states (bool): Whether to require two consecutive "done" states.
        project_name (str, optional): Name of the project to verify correct window is focused.
    """
    try:
        # Create a temporary directory for screenshots
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # Initialize LLM API
        if not initialize_llm_client():
            print(f"Failed to initialize LLM API. Cannot monitor {ide_name} state.")
            return False
            
        print("\n" + "=" * 60)
        print(f"STARTING IDE MONITORING")
        print(f"IDE: {ide_name}")
        print(f"Project: {project_name or 'N/A'}")
        print(f"Timeout: {timeout_in_seconds} seconds")
        print("=" * 60 + "\n")
        
        # Reset for this execution
        start_time = time.time()
        check_interval = 10.0  # Start with 40 seconds
        screenshot_count = 0
        last_state = None
        
        while True:
            # Calculate elapsed and remaining time
            elapsed = time.time() - start_time
            remaining = timeout_in_seconds - elapsed
            
            # Check if we've exceeded the timeout
            if remaining <= 0:
                break
                
            screenshot_count += 1
            
            # Print check header with clear separation
            print(f"\n" + "-" * 50)
            print(f"CHECK #{screenshot_count}")
            print(f"Time remaining: {int(remaining)}s")
            print(f"Analyzing {ide_name} state...")
            print("-" * 50)
            
            # Analyze IDE state (screenshot capture handled internally)
            is_done, state, reasoning = analyze_ide_state(interface_state_analysis_prompt, ide_name, project_name, save_screenshots_for_debug, screenshot_count)
            
            # Handle IDE not visible state
            if state == "ide_not_visible":
                print(f"\nIDE VISIBILITY ISSUE")
                print(f"   IDE {ide_name} with project '{project_name}' is not visible")
                print(f"   Attempting to bring window to focus...")
                from utils.computer_use_utils import bring_to_front_window
                
                focus_success = bring_to_front_window(ide_name, project_name)
                if focus_success:
                    print(f"   Successfully brought window to focus")
                    # Wait a moment for window to come to focus, then continue to next iteration
                    time.sleep(1.0)
                    continue
                else:
                    print(f"   ERROR: Could not bring {ide_name} window to focus")
                    from utils.computer_use_utils import play_beep_sound
                    play_beep_sound()
                    # Sleep for a shorter interval before checking again
                    time.sleep(min(10.0, actual_sleep_time if 'actual_sleep_time' in locals() else 10.0))
                    continue
            
            # Report state change with clear formatting
            if state != last_state:
                print(f"\nSTATE UPDATE")
                print(f"   Current state: {state}")
                print(f"   Reasoning: {reasoning}")
                last_state = state
            else:
                print(f"   State unchanged: {state}")
                
            # If IDE is done, return success
            if is_done:
                if require_two_subsequent_done_states:
                    print(f"\nVERIFICATION CHECK")
                    print(f"   Double-checking completion to avoid false positives...")
                    is_done, state, reasoning = analyze_ide_state(interface_state_analysis_prompt, ide_name, project_name, save_screenshots_for_debug, screenshot_count)
                    if state == "done":
                        print(f"\nSUCCESS: {ide_name} has completed its task!")
                        print(f"   Final reasoning: {reasoning}")
                        print("=" * 60)
                        return True
                    else:
                        print(f"\nFALSE POSITIVE DETECTED")
                        print(f"   {ide_name} didn't actually finish. Continuing to wait...")
                        print(f"   Reasoning: {reasoning}")
                else:
                    print(f"\nSUCCESS: {ide_name} has completed its task!")
                    print("=" * 60)
                    return True
            
            # Handle paused state for both Cursor and Windsurf
            if state == "paused_and_wanting_to_resume":
                print(f"\nPAUSED STATE DETECTED")
                print(f"   {ide_name} is paused and wanting to resume")
                print(f"   Attempting to click resume button...")
                if resume_button_prompt:
                    resume_success = await click_ide_resume_button(resume_button_prompt, ide_name, project_name)
                    if resume_success:
                        print(f"   Successfully resumed {ide_name}")
                        print(f"   Continuing to monitor...")
                        # Continue monitoring - don't reset the timeout, just continue
                        continue
                    else:
                        print(f"   Failed to click resume button")
                        raise Exception(f"Failed to click the resume button in {ide_name}. The IDE will be stuck waiting for user interaction and cannot proceed automatically.")
                else:
                    print(f"   No resume button prompt provided")
                    raise Exception(f"{ide_name} is paused and waiting for user action, but no resume button prompt was provided for automatic resumption.")
            
            # Recalculate remaining time for sleep decision
            elapsed_after_analysis = time.time() - start_time
            remaining_after_analysis = timeout_in_seconds - elapsed_after_analysis
            
            # Determine how long to actually sleep (don't sleep longer than remaining time)
            actual_sleep_time = min(check_interval, remaining_after_analysis)
            
            if actual_sleep_time <= 0:
                print(f"\nNo time remaining for sleep, checking timeout...")
                break
                
            # Sleep status with better formatting
            if screenshot_count % 5 == 0 or remaining_after_analysis < 30:
                print(f"\nWAITING")
                print(f"   Still executing... {int(remaining_after_analysis)}s remaining")
                print(f"   Next check in {int(actual_sleep_time)}s")
            else:
                print(f"\nSleeping for {int(actual_sleep_time)}s before next check...")
            
            print("." * 50 + " END CYCLE " + "." * 50)
            
            # Wait before next check (but don't sleep longer than remaining time)
            time.sleep(actual_sleep_time)
            
            # Update check interval: decrease by 2 seconds, minimum 10 seconds
            check_interval = max(10.0, check_interval - 2.0)
            
        # If we get here, we timed out
        final_elapsed = time.time() - start_time
        print(f"\nTIMEOUT REACHED")
        print(f"   {ide_name} did not finish within {timeout_in_seconds} seconds")
        print(f"   Actual elapsed time: {int(final_elapsed)}s")
        print("=" * 60)
        return False
    except KeyboardInterrupt:
        print(f"\nMONITORING INTERRUPTED")
        print(f"   Monitoring stopped by user")
        print("=" * 60)
        return False
    except Exception as e:
        print(f"\nERROR OCCURRED")
        print(f"   Error while waiting for IDE to finish: {e}")
        print("=" * 60)
        return False
    finally:
        # Clean up temporary files
        import shutil
        try:
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")

if __name__ == "__main__":    
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="Wait for an IDE to finish processing")
    parser.add_argument("--ide", required=True, help="Name of the IDE to monitor")
    parser.add_argument("--timeout", type=int, default=600, help="Maximum time to wait in seconds")
    parser.add_argument("--interface_state_analysis_prompt", required=True, help="Prompt for IDE state analysis")
    parser.add_argument("--resume_button_prompt", help="Prompt for finding the resume button (optional)")
    parser.add_argument("--project_name", help="Name of the project to verify correct window is focused (optional)")
    
    args = parser.parse_args()
    
    result = asyncio.run(wait_until_ide_finishes(
        args.ide, 
        args.interface_state_analysis_prompt, 
        args.timeout, 
        args.resume_button_prompt,
        require_two_subsequent_done_states=False,
        project_name=args.project_name,
        save_screenshots_for_debug=True
    ))
    sys.exit(0 if result else 1)
