"""
SimulateDev Utilities Module

This package contains utility functions and helper scripts
for the SimulateDev AI coding assistant.
"""

from .clone_repo import clone_repository, parse_repo_name
from .computer_use_utils import ClaudeComputerUse, take_screenshot, take_ide_window_screenshot, bring_to_front_window, is_project_window_visible, play_beep_sound
from .ide_completion_detector import (
    get_window_list, find_window_by_title, capture_screen, 
    capture_window_by_title, initialize_claude_client, 
    analyze_ide_state, wait_until_ide_finishes
)

__all__ = [
    'clone_repository',
    'parse_repo_name',
    'ClaudeComputerUse',
    'take_screenshot', 
    'take_ide_window_screenshot',
    'bring_to_front_window',
    'is_project_window_visible',
    'play_beep_sound',
    'get_window_list',
    'find_window_by_title',
    'capture_screen',
    'capture_window_by_title',
    'initialize_claude_client',
    'analyze_ide_state',
    'wait_until_ide_finishes'
] 