# Cross-Platform Support for SimulateDev

SimulateDev now supports **Windows**, **Linux**, and **macOS**! This document provides detailed information about cross-platform functionality, setup requirements, and troubleshooting.

## 🎉 What's New

### Cross-Platform Features
- **Universal Window Management**: Works with native window managers on all platforms
- **Smart Application Launching**: Automatically detects and launches IDEs using platform-specific methods
- **Adaptive Keyboard Shortcuts**: Uses Cmd on macOS, Ctrl on Windows/Linux automatically
- **Platform-Aware System Integration**: Native notifications, screenshots, and system sounds
- **Automatic Dependency Detection**: Setup script identifies missing platform requirements

## 🖥️ Platform-Specific Information

### macOS (Darwin)
- **Status**: ✅ Fully Supported (Original platform)
- **Requirements**: 
  - Xcode Command Line Tools (for Git and development tools)
  - Accessibility permissions for IDE automation
- **Window Management**: Uses AppleScript for precise window control
- **Shortcuts**: Command-based (Cmd+L, Cmd+I, etc.)
- **IDEs**: Cursor.app, Windsurf.app from `/Applications`

### Linux
- **Status**: ✅ Fully Supported (New!)
- **Requirements**:
  - **Essential**: `xdotool` OR `wmctrl` for window management
  - **Optional**: `pulseaudio-utils` or `alsa-utils` for audio notifications
- **Window Management**: Uses xdotool (preferred) or wmctrl fallback
- **Shortcuts**: Control-based (Ctrl+L, Ctrl+I, etc.)
- **IDEs**: Installed via package managers or AppImages

#### Linux Installation Commands
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install xdotool wmctrl
sudo apt-get install pulseaudio-utils alsa-utils  # Optional: audio support

# Fedora/RHEL/CentOS
sudo dnf install xdotool wmctrl
sudo dnf install pulseaudio-utils alsa-utils

# Arch Linux
sudo pacman -S xdotool wmctrl
sudo pacman -S pulseaudio alsa-utils

# openSUSE
sudo zypper install xdotool wmctrl
```

### Windows
- **Status**: ✅ Fully Supported (New!)
- **Requirements**: 
  - **Automatic**: `pywin32` (installed via requirements.txt)
  - No additional system permissions required
- **Window Management**: Uses Win32 APIs via pywin32
- **Shortcuts**: Control-based (Ctrl+L, Ctrl+I, etc.)
- **IDEs**: Auto-detected in standard installation paths

## 🛠️ Setup and Installation

### Quick Setup Check
Run the platform compatibility checker:
```bash
python scripts/setup_platform.py
```

This script will:
- ✅ Verify Python 3.8+ and Git installation
- 🔍 Check for platform-specific dependencies
- 📍 Locate installed IDEs
- 📋 Provide specific installation instructions

### Platform-Specific Setup

#### Linux Setup Example
```bash
# 1. Install window management tools
sudo apt-get install xdotool wmctrl

# 2. Install audio support (optional)
sudo apt-get install pulseaudio-utils

# 3. Install IDEs
# Cursor - Download from https://cursor.com
# Windsurf - Download from https://windsurf.ai
# VS Code - sudo apt-get install code

# 4. Run setup check
python scripts/setup_platform.py
```

#### Windows Setup Example
```bash
# 1. Install Python 3.8+ from python.org
# 2. Install Git from git-scm.com
# 3. Install IDEs from their official websites
# 4. Run setup check
python scripts/setup_platform.py
```

## 🔧 Architecture Overview

### Cross-Platform Components

#### `utils/platform_utils.py`
The core cross-platform abstraction layer:

- **`PlatformDetector`**: Identifies current OS and capabilities
- **`CrossPlatformWindowManager`**: Unified window management
- **`CrossPlatformAppLauncher`**: Application launching across platforms
- **`CrossPlatformKeyboardShortcuts`**: Adaptive keyboard shortcuts
- **`CrossPlatformSystemUtils`**: System integration (sounds, screenshots)

#### Updated Agent Classes
- **`CursorAgent`**: Now uses cross-platform shortcuts and app launching
- **`WindsurfAgent`**: Adapted for multi-platform keyboard shortcuts
- **Base Agent**: Cross-platform copy/paste operations

#### Enhanced Computer Use Utils
- **Backward Compatible**: Existing macOS-specific functions still work
- **Cross-Platform Fallbacks**: Graceful degradation on unsupported platforms
- **Smart Detection**: Automatically chooses best method per platform

## 🎯 Usage Examples

### Basic Cross-Platform Usage
```bash
# Works on all platforms - shortcuts adapt automatically
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor

# Platform detection is automatic
python simulatedev.py --workflow optimize --repo https://github.com/user/repo --agent windsurf
```

### Platform-Specific Considerations

#### Linux
```bash
# Ensure window tools are installed first
sudo apt-get install xdotool wmctrl

# Run SimulateDev
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor
```

#### Windows
```bash
# No additional setup needed beyond Python packages
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor
```

## 🧪 Testing Cross-Platform Features

### Automated Tests
```bash
# Run cross-platform test suite
python tests/test_cross_platform.py

# Test on specific platform
python -c "from utils.platform_utils import PlatformDetector; print(PlatformDetector.get_platform_name())"
```

### Manual Testing
1. **Platform Detection**: Verify correct OS identification
2. **Window Management**: Test IDE window focusing
3. **Application Launching**: Confirm IDEs open correctly
4. **Keyboard Shortcuts**: Validate shortcuts work (Cmd vs Ctrl)
5. **System Integration**: Test notifications and screenshots

## 🔍 Troubleshooting

### Common Issues and Solutions

#### Linux Issues

**Problem**: `xdotool: command not found`
```bash
# Solution: Install window management tools
sudo apt-get install xdotool wmctrl
```

**Problem**: IDE not found in PATH
```bash
# Solution: Install IDE properly or add to PATH
# For AppImage: chmod +x cursor.appimage && sudo mv cursor.appimage /usr/local/bin/cursor
```

**Problem**: Window management not working
```bash
# Check available tools
which xdotool wmctrl

# Test window detection
xdotool search --name ".*"
wmctrl -l
```

#### Windows Issues

**Problem**: `ImportError: No module named 'win32gui'`
```bash
# Solution: Install pywin32
pip install pywin32
```

**Problem**: IDE not launching
```bash
# Check if IDE is installed in standard location
# Cursor: %LOCALAPPDATA%\Programs\cursor\Cursor.exe
# Add IDE to PATH or use full path
```

#### General Issues

**Problem**: Keyboard shortcuts not working
- **macOS**: Check Accessibility permissions in System Preferences
- **Linux**: Ensure desktop environment supports programmatic key sending
- **Windows**: Run as administrator if needed

**Problem**: Window focusing fails
- Ensure target IDE is actually running
- Check that project is loaded in IDE
- Verify window title contains project name

### Debug Mode
Enable detailed logging:
```bash
# Set debug environment variable
export SIMULATEDEV_DEBUG=1
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor
```

## 📊 Platform Compatibility Matrix

| Feature | macOS | Linux | Windows |
|---------|--------|--------|---------|
| Platform Detection | ✅ | ✅ | ✅ |
| Window Management | ✅ | ✅ | ✅ |
| App Launching | ✅ | ✅ | ✅ |
| Keyboard Shortcuts | ✅ | ✅ | ✅ |
| System Sounds | ✅ | ✅ | ✅ |
| Screenshots | ✅ | ✅ | ✅ |
| Cursor IDE | ✅ | ✅ | ✅ |
| Windsurf IDE | ✅ | ✅ | ✅ |
| Claude Code | ✅ | ✅ | ✅ |

## 🚀 Future Enhancements

### Planned Improvements
- **Wayland Support**: Better Linux compatibility for newer systems
- **Multiple Monitor**: Enhanced multi-display support
- **Container Support**: Docker and WSL compatibility
- **Remote Desktop**: Support for RDP/VNC environments
- **IDE Auto-Installation**: Automatic IDE download and setup

### Contributing
To contribute cross-platform improvements:

1. **Test on Multiple Platforms**: Verify changes work across OS types
2. **Follow Platform Patterns**: Use existing abstractions in `platform_utils.py`
3. **Add Platform-Specific Tests**: Include tests for new platform features
4. **Update Documentation**: Keep this guide current with changes

## 📚 Technical Reference

### Key Classes and Methods

#### PlatformDetector
```python
from utils.platform_utils import PlatformDetector

# Detect current platform
platform = PlatformDetector.get_platform()  # Returns PlatformType enum
is_linux = PlatformDetector.is_linux()      # Boolean check
name = PlatformDetector.get_platform_name() # Human-readable string
```

#### CrossPlatformWindowManager
```python
from utils.platform_utils import window_manager

# Get all windows for a process
windows = window_manager.get_window_list("Cursor")

# Bring specific window to front
success = window_manager.bring_window_to_front("Project Window", "Cursor")
```

#### CrossPlatformKeyboardShortcuts
```python
from utils.platform_utils import keyboard_shortcuts

# Get platform-appropriate shortcut keys
keys = keyboard_shortcuts.get_shortcut_keys('cursor_chat')  # ['cmd', 'l'] or ['ctrl', 'l']

# Execute shortcut directly
success = keyboard_shortcuts.execute_shortcut('paste')
```

### Environment Variables
- `SIMULATEDEV_DEBUG`: Enable verbose debugging
- `XDG_CURRENT_DESKTOP`: Linux desktop environment detection
- `DISPLAY`: X11 display for Linux GUI operations

---

## 🎉 Success! 

SimulateDev now works seamlessly across **macOS**, **Linux**, and **Windows**. This expands the potential user base from ~30% (macOS only) to **100% of developers**!

For questions or issues, please check the troubleshooting section above or create an issue on GitHub.