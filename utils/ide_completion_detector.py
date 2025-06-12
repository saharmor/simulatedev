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
import google.generativeai as genai
from dotenv import load_dotenv

from utils.computer_use_utils import take_screenshot, ClaudeComputerUse
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
            set frontApp to name of first application process whose frontmost is true
            set frontAppWindow to "None"
            
            set targetWindow to window "{title}" of process "{window['app_name']}"
            if exists targetWindow then
                set frontAppWindow to name of window 1 of process frontApp
                set position of targetWindow to {0, 0}
                set frontmost of process "{window['app_name']}" to true
            end if
            
            delay 0.5
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

def initialize_gemini_client():
    """
    Initialize the Google Gemini API.
    
    Returns:
        bool: True if initialization is successful, False otherwise.
    """
    try:
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Get API key from environment variables
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            print("Error: GOOGLE_API_KEY environment variable not set.")
            print("Please create a .env file with the line: GOOGLE_API_KEY=your_api_key_here")
            return False
        
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return False

def analyze_ide_state(image_input, interface_state_analysis_prompt):
    """
    Analyze a screenshot to determine if the IDE has finished processing.
    
    Args:
        image_input: Either a path to screenshot image (str) or a BytesIO buffer from take_screenshot.
        interface_state_analysis_prompt (str): Prompt for IDE state analysis.
        
    Returns:
        tuple: (bool, str, str) - (Whether the IDE is done, State, Reasoning)
    """
    try:
        # Load and prepare the image
        if isinstance(image_input, str):
            # It's a file path
            img = Image.open(image_input)
        else:
            # It's a BytesIO buffer
            img = Image.open(image_input)
        
        # Ensure image is in RGB format for compatibility
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Get Gemini model
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        
        # Get response from Gemini
        response = model.generate_content([interface_state_analysis_prompt, img])
        response_text = response.text.strip()
        
        # Extract JSON from response text
        try:
            # Look for JSON content between triple backticks if present
            if "```json" in response_text and "```" in response_text.split("```json", 1)[1]:
                json_content = response_text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in response_text and "```" in response_text.split("```", 1)[1]:
                json_content = response_text.split("```", 1)[1].split("```", 1)[0].strip()
            else:
                json_content = response_text
            
            # Parse the JSON
            analysis = json.loads(json_content)
            
            state = analysis["interface_state"].lower()
            reasoning = analysis["reasoning"]
            
            # Determine if IDE is done
            is_done = state == "done"
            return is_done, state, reasoning                
        except json.JSONDecodeError:
            return False, "processing", "JSON parsing failed"  # Default to processing if JSON parsing fails
            
    except Exception as e:
        print(f"Error analyzing IDE state: {e}")
        return False, f"error: {str(e)}", str(e)

async def click_ide_resume_button(resume_button_prompt):
    """
    Find and click the resume button using the provided prompt.
    
    Args:
        resume_button_prompt (str): Prompt for finding the resume button.
        
    Returns:
        bool: True if button was found and clicked, False otherwise.
    """
    try:
        # Initialize Claude Computer Use for finding the button
        claude = ClaudeComputerUse()
        
        # Look for the Resume button
        result = await claude.get_coordinates_from_claude(
            resume_button_prompt,
            support_non_existing_elements=True
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

async def wait_until_ide_finishes(ide_name, interface_state_analysis_prompt, timeout_in_seconds, resume_button_prompt=None, require_two_subsequent_done_states=False):
    """
    Wait until the specified IDE finishes processing.
    
    Args:
        ide_name (str): Name of the IDE to monitor.
        interface_state_analysis_prompt (str): Prompt for analyzing IDE state.
        timeout_in_seconds (int): Maximum time to wait in seconds for THIS execution.
        resume_button_prompt (str, optional): Prompt for finding the resume button.
    """
    try:
        # Create a temporary directory for screenshots
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # Initialize Gemini API
        if not initialize_gemini_client():
            print(f"Failed to initialize Gemini API. Cannot monitor {ide_name} state.")
            return False
            
        print("-" * 30)
        print(f"Starting to monitor {ide_name} state...")
        print(f"Will wait up to {timeout_in_seconds} seconds for completion")
        
        # Reset for this execution
        start_time = time.time()
        check_interval = 40.0  # Start with 40 seconds
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
            
            # Print that we're checking (every iteration)
            print(f"Checking {ide_name} state... (check #{screenshot_count}, {int(remaining)}s remaining)")
            
            # Capture screenshot
            # TODO FIX and get size correctly
            image = take_screenshot(1280, 720)
            
            # Analyze screenshot
            is_done, state, reasoning = analyze_ide_state(image, interface_state_analysis_prompt)
            
            # Report state change
            if state != last_state:
                print(f"{ide_name} state: {state}, reasoning: {reasoning}")
                last_state = state
                
            # If IDE is done, return success
            if is_done:
                if require_two_subsequent_done_states:
                    print(f"Checking again if {ide_name} completed its task to make sure it was not a false positive")
                    is_done, state, reasoning = analyze_ide_state(image, interface_state_analysis_prompt)
                    if state == "done":
                        print(f"SUCCESS: {ide_name} has completed its task! Reasoning: {reasoning}")
                        return True
                    else:
                        print(f"WARNING: {ide_name} didn't acutally finish its task. Continue waiting. Reasoning: {reasoning}")
                else:
                    print(f"SUCCESS: {ide_name} has completed its task!")
                    return True
            
            # Handle paused state for both Cursor and Windsurf
            if state == "paused_and_wanting_to_resume":
                print(f"Detected {ide_name} is paused and wanting to resume. Attempting to resume...")
                if resume_button_prompt:
                    resume_success = await click_ide_resume_button(resume_button_prompt)
                    if resume_success:
                        print(f"Successfully resumed {ide_name}. Continuing to monitor...")
                        # Continue monitoring - don't reset the timeout, just continue
                        continue
                    else:
                        raise Exception(f"Failed to click the resume button in {ide_name}. The IDE will be stuck waiting for user interaction and cannot proceed automatically.")
                else:
                    print(f"Warning: {ide_name} is paused but no resume button prompt provided. Cannot auto-resume.")
                    raise Exception(f"{ide_name} is paused and waiting for user action, but no resume button prompt was provided for automatic resumption.")
            
            # Recalculate remaining time for sleep decision
            elapsed_after_analysis = time.time() - start_time
            remaining_after_analysis = timeout_in_seconds - elapsed_after_analysis
            
            # Determine how long to actually sleep (don't sleep longer than remaining time)
            actual_sleep_time = min(check_interval, remaining_after_analysis)
            
            if actual_sleep_time <= 0:
                print(f"No time remaining for sleep, checking timeout...")
                break
                
            if screenshot_count % 5 == 0 or remaining_after_analysis < 30:
                print(f"Still executing... {int(remaining_after_analysis)} seconds remaining (next check in {int(actual_sleep_time)} seconds)")
            else:
                print(f"Sleeping for {int(actual_sleep_time)} seconds before next check...")
            
            # Wait before next check (but don't sleep longer than remaining time)
            time.sleep(actual_sleep_time)
            
            # Update check interval: decrease by 2 seconds, minimum 10 seconds
            check_interval = max(10.0, check_interval - 2.0)
            
        # If we get here, we timed out
        final_elapsed = time.time() - start_time
        print(f"TIMEOUT: {ide_name} did not finish within {timeout_in_seconds} seconds (actual elapsed: {int(final_elapsed)}s)")
        print("-" * 30)
        return False
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
        return False
    except Exception as e:
        print(f"Error while waiting for IDE to finish: {e}")
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
    
    args = parser.parse_args()
    
    result = asyncio.run(wait_until_ide_finishes(args.ide, args.interface_state_analysis_prompt, args.timeout, args.resume_button_prompt))
    sys.exit(0 if result else 1)
