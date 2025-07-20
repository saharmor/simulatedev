#!/usr/bin/env python3
"""
Cross-Platform Utilities for SimulateDev

This module provides platform-specific implementations for GUI automation,
window management, and system operations across Windows, Linux, and macOS.
"""

import os
import platform
import subprocess
import time
import psutil
import pyautogui
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
from dataclasses import dataclass


class PlatformType(Enum):
    WINDOWS = "Windows"
    LINUX = "Linux"
    MACOS = "Darwin"
    UNKNOWN = "Unknown"


@dataclass
class WindowInfo:
    """Information about a window"""
    title: str
    pid: int
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class PlatformDetector:
    """Detects and provides information about the current platform"""
    
    @staticmethod
    def get_platform() -> PlatformType:
        """Get the current platform type"""
        system = platform.system()
        if system == "Windows":
            return PlatformType.WINDOWS
        elif system == "Linux":
            return PlatformType.LINUX
        elif system == "Darwin":
            return PlatformType.MACOS
        else:
            return PlatformType.UNKNOWN
    
    @staticmethod
    def is_windows() -> bool:
        return PlatformDetector.get_platform() == PlatformType.WINDOWS
    
    @staticmethod
    def is_linux() -> bool:
        return PlatformDetector.get_platform() == PlatformType.LINUX
    
    @staticmethod
    def is_macos() -> bool:
        return PlatformDetector.get_platform() == PlatformType.MACOS
    
    @staticmethod
    def get_platform_name() -> str:
        return PlatformDetector.get_platform().value


class CrossPlatformWindowManager:
    """Cross-platform window management operations"""
    
    def __init__(self):
        self.platform = PlatformDetector.get_platform()
        
        # Import platform-specific dependencies
        if self.platform == PlatformType.WINDOWS:
            try:
                import win32gui
                import win32con
                import win32process
                self.win32gui = win32gui
                self.win32con = win32con
                self.win32process = win32process
            except ImportError:
                print("WARNING: pywin32 not installed. Windows-specific features will be limited.")
                self.win32gui = None
                
        elif self.platform == PlatformType.LINUX:
            # Check for available Linux window managers
            self.wm_type = self._detect_linux_wm()
            
    def _detect_linux_wm(self) -> str:
        """Detect the Linux window manager/desktop environment"""
        # Check for common desktop environments
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if desktop:
            return desktop
            
        # Check for window manager
        wm = os.environ.get('WINDOW_MANAGER', '').lower()
        if wm:
            return wm
            
        # Try to detect based on running processes
        try:
            processes = [p.name() for p in psutil.process_iter(['name'])]
            if any('gnome' in p for p in processes):
                return 'gnome'
            elif any('kde' in p for p in processes):
                return 'kde'
            elif any('xfce' in p for p in processes):
                return 'xfce'
            elif any('i3' in p for p in processes):
                return 'i3'
        except Exception:
            pass
            
        return 'unknown'
    
    def get_window_list(self, process_name: Optional[str] = None) -> List[WindowInfo]:
        """Get list of all windows, optionally filtered by process name"""
        if self.platform == PlatformType.MACOS:
            return self._get_windows_macos(process_name)
        elif self.platform == PlatformType.WINDOWS:
            return self._get_windows_windows(process_name)
        elif self.platform == PlatformType.LINUX:
            return self._get_windows_linux(process_name)
        else:
            return []
    
    def _get_windows_macos(self, process_name: Optional[str] = None) -> List[WindowInfo]:
        """Get windows on macOS using AppleScript"""
        script = '''
        tell application "System Events"
            set windowList to {}
            repeat with proc in (every application process whose visible is true)
                set procName to name of proc
                repeat with win in (every window of proc)
                    set windowTitle to name of win
                    set windowList to windowList & {procName & "|" & windowTitle}
                end repeat
            end repeat
        end tell
        return windowList
        '''
        
        try:
            result = subprocess.run(["osascript", "-e", script], 
                                  capture_output=True, text=True, check=True)
            windows = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    proc, title = line.split('|', 1)
                    if not process_name or proc.lower() == process_name.lower():
                        windows.append(WindowInfo(title=title.strip(), pid=0))
            return windows
        except Exception as e:
            print(f"Error getting macOS windows: {e}")
            return []
    
    def _get_windows_windows(self, process_name: Optional[str] = None) -> List[WindowInfo]:
        """Get windows on Windows using win32gui"""
        if not self.win32gui:
            return []
            
        windows = []
        
        def enum_windows_callback(hwnd, data):
            if self.win32gui.IsWindowVisible(hwnd):
                title = self.win32gui.GetWindowText(hwnd)
                if title:
                    try:
                        _, pid = self.win32process.GetWindowThreadProcessId(hwnd)
                        if process_name:
                            try:
                                proc = psutil.Process(pid)
                                if proc.name().lower() != process_name.lower():
                                    return True  # Continue enumeration
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                return True
                        
                        rect = self.win32gui.GetWindowRect(hwnd)
                        windows.append(WindowInfo(
                            title=title,
                            pid=pid,
                            x=rect[0],
                            y=rect[1],
                            width=rect[2] - rect[0],
                            height=rect[3] - rect[1]
                        ))
                    except Exception:
                        pass
            return True
        
        try:
            self.win32gui.EnumWindows(enum_windows_callback, None)
        except Exception as e:
            print(f"Error enumerating Windows windows: {e}")
            
        return windows
    
    def _get_windows_linux(self, process_name: Optional[str] = None) -> List[WindowInfo]:
        """Get windows on Linux using various methods"""
        windows = []
        
        # Try xdotool first (most reliable)
        try:
            result = subprocess.run(['xdotool', 'search', '--name', '.*'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                window_ids = result.stdout.strip().split('\n')
                for wid in window_ids:
                    if wid:
                        try:
                            # Get window title
                            title_result = subprocess.run(['xdotool', 'getwindowname', wid],
                                                        capture_output=True, text=True)
                            if title_result.returncode == 0:
                                title = title_result.stdout.strip()
                                
                                # Get window PID
                                pid_result = subprocess.run(['xdotool', 'getwindowpid', wid],
                                                          capture_output=True, text=True)
                                pid = 0
                                if pid_result.returncode == 0:
                                    try:
                                        pid = int(pid_result.stdout.strip())
                                        if process_name:
                                            try:
                                                proc = psutil.Process(pid)
                                                if proc.name().lower() != process_name.lower():
                                                    continue
                                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                                continue
                                    except ValueError:
                                        pass
                                
                                windows.append(WindowInfo(title=title, pid=pid))
                        except Exception:
                            continue
        except FileNotFoundError:
            # xdotool not available, try wmctrl
            try:
                result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            title = parts[3]
                            windows.append(WindowInfo(title=title, pid=0))
            except FileNotFoundError:
                print("WARNING: Neither xdotool nor wmctrl found. Window management will be limited.")
        
        return windows
    
    def bring_window_to_front(self, window_title: str, process_name: Optional[str] = None) -> bool:
        """Bring a window to front by title"""
        if self.platform == PlatformType.MACOS:
            return self._bring_to_front_macos(window_title, process_name)
        elif self.platform == PlatformType.WINDOWS:
            return self._bring_to_front_windows(window_title, process_name)
        elif self.platform == PlatformType.LINUX:
            return self._bring_to_front_linux(window_title, process_name)
        return False
    
    def _bring_to_front_macos(self, window_title: str, process_name: Optional[str] = None) -> bool:
        """Bring window to front on macOS"""
        if process_name:
            script = f'''
            tell application "System Events"
                tell process "{process_name}"
                    set frontmost to true
                    perform action "AXRaise" of window "{window_title}"
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                tell frontApp
                    perform action "AXRaise" of window "{window_title}"
                end tell
            end tell
            '''
        
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def _bring_to_front_windows(self, window_title: str, process_name: Optional[str] = None) -> bool:
        """Bring window to front on Windows"""
        if not self.win32gui:
            return False
            
        def find_window(hwnd, data):
            if self.win32gui.IsWindowVisible(hwnd):
                title = self.win32gui.GetWindowText(hwnd)
                if window_title.lower() in title.lower():
                    try:
                        self.win32gui.SetForegroundWindow(hwnd)
                        return False  # Stop enumeration
                    except Exception:
                        pass
            return True
        
        try:
            self.win32gui.EnumWindows(find_window, None)
            return True
        except Exception:
            return False
    
    def _bring_to_front_linux(self, window_title: str, process_name: Optional[str] = None) -> bool:
        """Bring window to front on Linux"""
        try:
            # Try xdotool first
            result = subprocess.run(['xdotool', 'search', '--name', window_title],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                window_ids = result.stdout.strip().split('\n')
                if window_ids and window_ids[0]:
                    subprocess.run(['xdotool', 'windowactivate', window_ids[0]])
                    return True
        except FileNotFoundError:
            # Try wmctrl
            try:
                subprocess.run(['wmctrl', '-a', window_title])
                return True
            except FileNotFoundError:
                pass
        
        return False


class CrossPlatformAppLauncher:
    """Cross-platform application launching"""
    
    def __init__(self):
        self.platform = PlatformDetector.get_platform()
    
    def open_application(self, app_name: str, project_path: Optional[str] = None) -> bool:
        """Open an application, optionally with a project path"""
        if self.platform == PlatformType.MACOS:
            return self._open_app_macos(app_name, project_path)
        elif self.platform == PlatformType.WINDOWS:
            return self._open_app_windows(app_name, project_path)
        elif self.platform == PlatformType.LINUX:
            return self._open_app_linux(app_name, project_path)
        return False
    
    def _open_app_macos(self, app_name: str, project_path: Optional[str] = None) -> bool:
        """Open application on macOS"""
        try:
            if project_path:
                subprocess.run(["open", "-a", app_name, project_path])
            else:
                subprocess.run(["open", "-a", app_name])
            return True
        except Exception as e:
            print(f"Error opening {app_name} on macOS: {e}")
            return False
    
    def _open_app_windows(self, app_name: str, project_path: Optional[str] = None) -> bool:
        """Open application on Windows"""
        try:
            # Common Windows app paths
            app_paths = {
                'cursor': [
                    os.path.expandvars(r'%LOCALAPPDATA%\Programs\cursor\Cursor.exe'),
                    r'C:\Users\%USERNAME%\AppData\Local\Programs\cursor\Cursor.exe',
                ],
                'windsurf': [
                    os.path.expandvars(r'%LOCALAPPDATA%\Programs\Windsurf\Windsurf.exe'),
                    r'C:\Users\%USERNAME%\AppData\Local\Programs\Windsurf\Windsurf.exe',
                ],
                'code': [
                    os.path.expandvars(r'%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe'),
                    r'C:\Program Files\Microsoft VS Code\Code.exe',
                ]
            }
            
            app_key = app_name.lower()
            if app_key in app_paths:
                for path in app_paths[app_key]:
                    if os.path.exists(path):
                        cmd = [path]
                        if project_path:
                            cmd.append(project_path)
                        subprocess.Popen(cmd)
                        return True
            
            # Try to launch by name
            cmd = [app_name]
            if project_path:
                cmd.append(project_path)
            subprocess.Popen(cmd)
            return True
            
        except Exception as e:
            print(f"Error opening {app_name} on Windows: {e}")
            return False
    
    def _open_app_linux(self, app_name: str, project_path: Optional[str] = None) -> bool:
        """Open application on Linux"""
        try:
            # Common Linux app commands
            app_commands = {
                'cursor': ['cursor', 'cursor-bin'],
                'windsurf': ['windsurf', 'windsurf-bin'],
                'code': ['code', 'code-oss', 'codium'],
                'vscode': ['code', 'code-oss', 'codium']
            }
            
            app_key = app_name.lower()
            commands_to_try = app_commands.get(app_key, [app_name])
            
            for cmd in commands_to_try:
                try:
                    # Check if command exists
                    subprocess.run(['which', cmd], capture_output=True, check=True)
                    
                    # Launch the application
                    launch_cmd = [cmd]
                    if project_path:
                        launch_cmd.append(project_path)
                    
                    subprocess.Popen(launch_cmd)
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            return False
            
        except Exception as e:
            print(f"Error opening {app_name} on Linux: {e}")
            return False


class CrossPlatformKeyboardShortcuts:
    """Cross-platform keyboard shortcuts"""
    
    def __init__(self):
        self.platform = PlatformDetector.get_platform()
    
    def get_shortcut_keys(self, shortcut_name: str) -> List[str]:
        """Get platform-specific shortcut keys"""
        shortcuts = {
            'cursor_chat': {
                PlatformType.MACOS: ['command', 'l'],
                PlatformType.WINDOWS: ['ctrl', 'l'],
                PlatformType.LINUX: ['ctrl', 'l']
            },
            'windsurf_cascade': {
                PlatformType.MACOS: ['command', 'i'],
                PlatformType.WINDOWS: ['ctrl', 'i'],
                PlatformType.LINUX: ['ctrl', 'i']
            },
            'copy': {
                PlatformType.MACOS: ['command', 'c'],
                PlatformType.WINDOWS: ['ctrl', 'c'],
                PlatformType.LINUX: ['ctrl', 'c']
            },
            'paste': {
                PlatformType.MACOS: ['command', 'v'],
                PlatformType.WINDOWS: ['ctrl', 'v'],
                PlatformType.LINUX: ['ctrl', 'v']
            },
            'select_all': {
                PlatformType.MACOS: ['command', 'a'],
                PlatformType.WINDOWS: ['ctrl', 'a'],
                PlatformType.LINUX: ['ctrl', 'a']
            }
        }
        
        shortcut_map = shortcuts.get(shortcut_name, {})
        return shortcut_map.get(self.platform, [])
    
    def execute_shortcut(self, shortcut_name: str) -> bool:
        """Execute a platform-specific keyboard shortcut"""
        keys = self.get_shortcut_keys(shortcut_name)
        if keys:
            try:
                pyautogui.hotkey(*keys)
                return True
            except Exception as e:
                print(f"Error executing shortcut {shortcut_name}: {e}")
        return False


class CrossPlatformSystemUtils:
    """Cross-platform system utilities"""
    
    @staticmethod
    def play_system_sound() -> bool:
        """Play a system notification sound"""
        platform_type = PlatformDetector.get_platform()
        
        try:
            if platform_type == PlatformType.MACOS:
                subprocess.run(['afplay', '/System/Library/Sounds/Ping.aiff'])
            elif platform_type == PlatformType.WINDOWS:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif platform_type == PlatformType.LINUX:
                # Try multiple methods for Linux
                try:
                    subprocess.run(['paplay', '/usr/share/sounds/alsa/Front_Left.wav'])
                except FileNotFoundError:
                    try:
                        subprocess.run(['aplay', '/usr/share/sounds/alsa/Front_Left.wav'])
                    except FileNotFoundError:
                        try:
                            subprocess.run(['speaker-test', '-t', 'sine', '-f', '1000', '-l', '1'])
                        except FileNotFoundError:
                            print('\a')  # Terminal bell as fallback
            return True
        except Exception as e:
            print(f"Could not play system sound: {e}")
            return False
    
    @staticmethod
    def get_screen_resolution() -> Tuple[int, int]:
        """Get screen resolution"""
        return pyautogui.size()
    
    @staticmethod
    def take_screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> Optional[str]:
        """Take a screenshot and return the path"""
        try:
            timestamp = int(time.time())
            filename = f"screenshot_{timestamp}.png"
            
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            screenshot.save(filename)
            return filename
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None


# Global instances for easy access
window_manager = CrossPlatformWindowManager()
app_launcher = CrossPlatformAppLauncher()
keyboard_shortcuts = CrossPlatformKeyboardShortcuts()
system_utils = CrossPlatformSystemUtils()