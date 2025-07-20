#!/usr/bin/env python3
"""
Cross-Platform Functionality Tests for SimulateDev

Tests the cross-platform utilities and ensures they work correctly
across different operating systems.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.platform_utils import (
    PlatformDetector, PlatformType, CrossPlatformWindowManager,
    CrossPlatformAppLauncher, CrossPlatformKeyboardShortcuts,
    CrossPlatformSystemUtils
)


class TestPlatformDetector(unittest.TestCase):
    """Test platform detection functionality"""
    
    def test_platform_detection(self):
        """Test that platform detection works"""
        platform_type = PlatformDetector.get_platform()
        self.assertIn(platform_type, [PlatformType.WINDOWS, PlatformType.LINUX, PlatformType.MACOS, PlatformType.UNKNOWN])
        
        # Test boolean methods
        if platform_type == PlatformType.WINDOWS:
            self.assertTrue(PlatformDetector.is_windows())
            self.assertFalse(PlatformDetector.is_linux())
            self.assertFalse(PlatformDetector.is_macos())
        elif platform_type == PlatformType.LINUX:
            self.assertFalse(PlatformDetector.is_windows())
            self.assertTrue(PlatformDetector.is_linux())
            self.assertFalse(PlatformDetector.is_macos())
        elif platform_type == PlatformType.MACOS:
            self.assertFalse(PlatformDetector.is_windows())
            self.assertFalse(PlatformDetector.is_linux())
            self.assertTrue(PlatformDetector.is_macos())
    
    def test_platform_name(self):
        """Test platform name retrieval"""
        name = PlatformDetector.get_platform_name()
        self.assertIsInstance(name, str)
        self.assertIn(name, ["Windows", "Linux", "Darwin", "Unknown"])


class TestCrossPlatformWindowManager(unittest.TestCase):
    """Test cross-platform window management"""
    
    def setUp(self):
        self.wm = CrossPlatformWindowManager()
    
    def test_initialization(self):
        """Test window manager initialization"""
        self.assertIsNotNone(self.wm.platform)
        self.assertIn(self.wm.platform, [PlatformType.WINDOWS, PlatformType.LINUX, PlatformType.MACOS, PlatformType.UNKNOWN])
    
    @patch('subprocess.run')
    def test_get_windows_macos(self, mock_run):
        """Test macOS window enumeration"""
        if not PlatformDetector.is_macos():
            self.skipTest("Not running on macOS")
        
        # Mock AppleScript output
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Cursor|Project Window\nWindsurf|Another Window"
        
        windows = self.wm.get_window_list()
        self.assertIsInstance(windows, list)
    
    def test_get_windows_current_platform(self):
        """Test window enumeration on current platform"""
        # This should not raise an exception
        windows = self.wm.get_window_list()
        self.assertIsInstance(windows, list)
    
    def test_bring_window_to_front(self):
        """Test bringing window to front"""
        # This should not raise an exception, even if it returns False
        result = self.wm.bring_window_to_front("NonexistentWindow", "NonexistentProcess")
        self.assertIsInstance(result, bool)


class TestCrossPlatformAppLauncher(unittest.TestCase):
    """Test cross-platform application launching"""
    
    def setUp(self):
        self.launcher = CrossPlatformAppLauncher()
    
    def test_initialization(self):
        """Test app launcher initialization"""
        self.assertIsNotNone(self.launcher.platform)
    
    @patch('subprocess.Popen')
    @patch('os.path.exists')
    def test_open_application_windows(self, mock_exists, mock_popen):
        """Test Windows application launching"""
        if not PlatformDetector.is_windows():
            self.skipTest("Not running on Windows")
        
        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()
        
        result = self.launcher.open_application("cursor", "/test/path")
        self.assertIsInstance(result, bool)
    
    @patch('subprocess.run')
    @patch('subprocess.Popen')
    def test_open_application_linux(self, mock_popen, mock_run):
        """Test Linux application launching"""
        if not PlatformDetector.is_linux():
            self.skipTest("Not running on Linux")
        
        # Mock 'which' command success
        mock_run.return_value.returncode = 0
        mock_popen.return_value = MagicMock()
        
        result = self.launcher.open_application("cursor", "/test/path")
        self.assertIsInstance(result, bool)
    
    @patch('subprocess.run')
    def test_open_application_macos(self, mock_run):
        """Test macOS application launching"""
        if not PlatformDetector.is_macos():
            self.skipTest("Not running on macOS")
        
        mock_run.return_value.returncode = 0
        
        result = self.launcher.open_application("Cursor", "/test/path")
        self.assertIsInstance(result, bool)


class TestCrossPlatformKeyboardShortcuts(unittest.TestCase):
    """Test cross-platform keyboard shortcuts"""
    
    def setUp(self):
        self.shortcuts = CrossPlatformKeyboardShortcuts()
    
    def test_initialization(self):
        """Test keyboard shortcuts initialization"""
        self.assertIsNotNone(self.shortcuts.platform)
    
    def test_get_shortcut_keys(self):
        """Test shortcut key retrieval"""
        cursor_keys = self.shortcuts.get_shortcut_keys('cursor_chat')
        self.assertIsInstance(cursor_keys, list)
        
        if PlatformDetector.is_macos():
            self.assertIn('command', cursor_keys)
        else:
            self.assertIn('ctrl', cursor_keys)
    
    def test_get_common_shortcuts(self):
        """Test common shortcut retrieval"""
        shortcuts_to_test = ['copy', 'paste', 'select_all']
        
        for shortcut in shortcuts_to_test:
            keys = self.shortcuts.get_shortcut_keys(shortcut)
            self.assertIsInstance(keys, list)
            self.assertGreater(len(keys), 0)
    
    @patch('pyautogui.hotkey')
    def test_execute_shortcut(self, mock_hotkey):
        """Test shortcut execution"""
        mock_hotkey.return_value = None
        
        result = self.shortcuts.execute_shortcut('copy')
        self.assertIsInstance(result, bool)
        
        if result:  # If shortcut was found and executed
            mock_hotkey.assert_called()


class TestCrossPlatformSystemUtils(unittest.TestCase):
    """Test cross-platform system utilities"""
    
    def test_get_screen_resolution(self):
        """Test screen resolution retrieval"""
        width, height = CrossPlatformSystemUtils.get_screen_resolution()
        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
    
    @patch('subprocess.run')
    def test_play_system_sound_macos(self, mock_run):
        """Test macOS system sound"""
        if not PlatformDetector.is_macos():
            self.skipTest("Not running on macOS")
        
        mock_run.return_value = None
        result = CrossPlatformSystemUtils.play_system_sound()
        self.assertIsInstance(result, bool)
    
    @patch('winsound.MessageBeep')
    def test_play_system_sound_windows(self, mock_beep):
        """Test Windows system sound"""
        if not PlatformDetector.is_windows():
            self.skipTest("Not running on Windows")
        
        mock_beep.return_value = None
        result = CrossPlatformSystemUtils.play_system_sound()
        self.assertIsInstance(result, bool)
    
    @patch('subprocess.run')
    def test_play_system_sound_linux(self, mock_run):
        """Test Linux system sound"""
        if not PlatformDetector.is_linux():
            self.skipTest("Not running on Linux")
        
        mock_run.return_value = None
        result = CrossPlatformSystemUtils.play_system_sound()
        self.assertIsInstance(result, bool)
    
    @patch('pyautogui.screenshot')
    def test_take_screenshot(self, mock_screenshot):
        """Test screenshot functionality"""
        mock_image = MagicMock()
        mock_image.save = MagicMock()
        mock_screenshot.return_value = mock_image
        
        result = CrossPlatformSystemUtils.take_screenshot()
        self.assertIsInstance(result, (str, type(None)))


class TestPlatformIntegration(unittest.TestCase):
    """Test integration between platform components"""
    
    def test_all_components_initialize(self):
        """Test that all cross-platform components can be initialized"""
        components = [
            CrossPlatformWindowManager(),
            CrossPlatformAppLauncher(),
            CrossPlatformKeyboardShortcuts(),
            CrossPlatformSystemUtils()
        ]
        
        for component in components:
            self.assertIsNotNone(component)
    
    def test_platform_consistency(self):
        """Test that all components report the same platform"""
        wm = CrossPlatformWindowManager()
        launcher = CrossPlatformAppLauncher()
        shortcuts = CrossPlatformKeyboardShortcuts()
        
        # All should detect the same platform
        self.assertEqual(wm.platform, launcher.platform)
        self.assertEqual(launcher.platform, shortcuts.platform)
    
    def test_error_handling(self):
        """Test that components handle errors gracefully"""
        wm = CrossPlatformWindowManager()
        launcher = CrossPlatformAppLauncher()
        shortcuts = CrossPlatformKeyboardShortcuts()
        
        # These should not raise exceptions
        wm.get_window_list("NonexistentProcess")
        launcher.open_application("NonexistentApp")
        shortcuts.get_shortcut_keys("nonexistent_shortcut")


if __name__ == '__main__':
    print(f"Running cross-platform tests on: {PlatformDetector.get_platform_name()}")
    unittest.main(verbosity=2)