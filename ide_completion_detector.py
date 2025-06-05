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

from computer_use_utils import take_screenshot, ClaudeComputerUse
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

def analyze_ide_state(image_path, interface_state_analysis_prompt):
    """
    Analyze a screenshot to determine if the IDE has finished processing.
    
    Args:
        image_path (str): Path to the screenshot image.
        interface_state_analysis_prompt (str): Prompt for IDE state analysis.
        
    Returns:
        tuple: (bool, str) - (Whether the IDE is done, State description)
    """
    try:
        # Load and prepare the image
        with Image.open(image_path) as img:
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
                
                # Determine if IDE is done
                is_done = state == "done"
                return is_done, state                
            except json.JSONDecodeError:
                return False, "processing"  # Default to processing if JSON parsing fails
                
    except Exception as e:
        print(f"Error analyzing IDE state: {e}")
        return False, f"error: {str(e)}"

def detect_cursor_resume_message(image_path):
    """
    Detect if Cursor shows the message about stopping after 25 tool calls.
    
    Args:
        image_path (str): Path to the screenshot image.
        
    Returns:
        bool: True if the resume message is detected, False otherwise.
    """
    try:
        # Load and prepare the image
        with Image.open(image_path) as img:
            # Ensure image is in RGB format for compatibility
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Get Gemini model
            model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
            
            # Prompt to detect the resume message
            prompt = """You are analyzing a screenshot of the Cursor IDE interface. Look for this exact message:

"Note: we default stop the agent after 25 tool calls. You can resume the conversation."

Respond with a JSON object containing:
{
    "resume_message_detected": true/false,
    "reasoning": "explanation of what you found"
}

If you see this message, return true. If not, return false."""
            
            # Get response from Gemini
            response = model.generate_content([prompt, img])
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
                return analysis.get("resume_message_detected", False)
                
            except json.JSONDecodeError:
                return False  # Default to False if JSON parsing fails
                
    except Exception as e:
        print(f"Error detecting cursor resume message: {e}")
        return False

async def click_cursor_resume_button():
    """
    Find and click the "Resume the Conversation" button in Cursor.
    
    Returns:
        bool: True if button was found and clicked, False otherwise.
    """
    try:
        # Initialize Claude Computer Use for finding the button
        claude = ClaudeComputerUse()
        
        # Look for the Resume button
        result = await claude.get_coordinates_from_claude(
            "Button/linked text that says 'resume the Conversation' related to continuing after 25 tool calls",
            support_non_existing_elements=True
        )
        
        if result and result.coordinates:
            print(f"Found Resume button at coordinates ({result.coordinates.x}, {result.coordinates.y})")
            
            # Click the resume button
            pyautogui.moveTo(result.coordinates.x, result.coordinates.y, duration=0.5)
            time.sleep(0.5)
            pyautogui.click(result.coordinates.x, result.coordinates.y)
            time.sleep(2.0)  # Wait a bit for the resume to take effect
            print("Successfully clicked Resume the Conversation button")
            return True
        else:
            print("Could not find Resume the Conversation button")
            return False
            
    except Exception as e:
        print(f"Error clicking resume button: {e}")
        return False

async def wait_until_ide_finishes(ide_name, interface_state_analysis_prompt, timeout_in_seconds):
    """
    Wait until the specified IDE finishes processing.
    
    Args:
        ide_name (str): Name of the IDE to monitor.
        interface_state_analysis_prompt (str): Prompt for analyzing IDE state.
        timeout_in_seconds (int): Maximum time to wait in seconds.
    """
    try:
        # Create a temporary directory for screenshots
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # Initialize Gemini API
        if not initialize_gemini_client():
            print(f"Failed to initialize Gemini API. Cannot monitor {ide_name} state.")
            return False
            
        print(f"Starting to monitor {ide_name} state...")
        print(f"Will wait up to {timeout_in_seconds} seconds for completion")
        
        start_time = time.time()
        check_interval = 20.0  # Start with 20 seconds
        screenshot_count = 0
        last_state = None
        
        while time.time() - start_time < timeout_in_seconds:
            screenshot_count += 1
            
            # Print that we're checking (every iteration)
            elapsed = time.time() - start_time
            remaining = timeout_in_seconds - elapsed
            print(f"Checking {ide_name} state... (check #{screenshot_count}, {int(remaining)}s remaining)")
            
            # Capture screenshot
            # TODO FIX and get size correctly
            image = take_screenshot(1280, 720, save_to_file=True)
            
            # Special handling for Cursor: Check for 25 tool call limit message
            if ide_name.lower() == "cursor":
                if detect_cursor_resume_message("screenshot.png"):
                    print("Detected Cursor 25 tool call limit message. Attempting to resume...")
                    resume_success = await click_cursor_resume_button()
                    if resume_success:
                        print("Successfully resumed Cursor conversation. Continuing to monitor...")
                        # Continue monitoring - don't reset the timeout, just continue
                        continue
                    else:
                        raise Exception("Failed to click the Resume button in Cursor. The IDE will be stuck waiting for user interaction and cannot proceed automatically.")
            
            # Analyze screenshot
            is_done, state = analyze_ide_state(image, interface_state_analysis_prompt)
            
            # Report state change
            if state != last_state:
                print(f"{ide_name} state: {state}")
                last_state = state
                
            # If IDE is done, return success
            if is_done:
                print(f"SUCCESS: {ide_name} has completed its task!")
                return True
            
            # Check elapsed time
            elapsed = time.time() - start_time
            remaining = timeout_in_seconds - elapsed
            
            if screenshot_count % 5 == 0 or remaining < 30:
                print(f"Still waiting... {int(remaining)} seconds remaining (next check in {check_interval} seconds)")
                
            print(f"Sleeping for {int(check_interval)} seconds before next check...")
            
            # Wait before next check
            time.sleep(check_interval)
            
            # Update check interval: decrease by 2 seconds, minimum 5 seconds
            check_interval = max(5.0, check_interval - 2.0)
            
        # If we get here, we timed out
        print(f"TIMEOUT: {ide_name} did not finish within {timeout_in_seconds} seconds")
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
    
    parser = argparse.ArgumentParser(description="Wait for an IDE to finish processing")
    parser.add_argument("--ide", required=True, help="Name of the IDE to monitor")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum time to wait in seconds")
    parser.add_argument("--interface_state_analysis_prompt", required=True, help="Prompt for IDE state analysis")
    
    args = parser.parse_args()
    
    result = wait_until_ide_finishes(args.ide, args.interface_state_analysis_prompt, args.timeout)
    sys.exit(0 if result else 1)
