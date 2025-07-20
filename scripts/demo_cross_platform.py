#!/usr/bin/env python3
"""
Cross-Platform Demo for SimulateDev

This script demonstrates the cross-platform capabilities of SimulateDev
by showing platform detection, window management, and system integration.
"""

import sys
import os
import time

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.platform_utils import (
        PlatformDetector, window_manager, app_launcher,
        keyboard_shortcuts, system_utils
    )
except ImportError as e:
    print(f"❌ Error importing platform utilities: {e}")
    print("💡 Make sure to install dependencies: pip install -r requirements.txt")
    sys.exit(1)


def demo_platform_detection():
    """Demonstrate platform detection capabilities"""
    print("🔍 Platform Detection Demo")
    print("-" * 30)
    
    platform = PlatformDetector.get_platform()
    print(f"Platform Type: {platform}")
    print(f"Platform Name: {PlatformDetector.get_platform_name()}")
    print(f"Is Windows: {PlatformDetector.is_windows()}")
    print(f"Is Linux: {PlatformDetector.is_linux()}")
    print(f"Is macOS: {PlatformDetector.is_macos()}")
    print()


def demo_keyboard_shortcuts():
    """Demonstrate adaptive keyboard shortcuts"""
    print("⌨️  Keyboard Shortcuts Demo")
    print("-" * 30)
    
    shortcuts_to_demo = [
        ('cursor_chat', 'Cursor Chat'),
        ('windsurf_cascade', 'Windsurf Cascade'),
        ('copy', 'Copy'),
        ('paste', 'Paste'),
        ('select_all', 'Select All')
    ]
    
    for shortcut_key, description in shortcuts_to_demo:
        keys = keyboard_shortcuts.get_shortcut_keys(shortcut_key)
        if keys:
            print(f"{description}: {' + '.join(keys)}")
        else:
            print(f"{description}: Not defined")
    print()


def demo_window_management():
    """Demonstrate window management capabilities"""
    print("🪟 Window Management Demo")
    print("-" * 30)
    
    # Get list of all windows
    print("Scanning for windows...")
    all_windows = window_manager.get_window_list()
    
    if all_windows:
        print(f"Found {len(all_windows)} windows:")
        for i, window in enumerate(all_windows[:5]):  # Show first 5
            print(f"  {i+1}. {window.title} (PID: {window.pid})")
        if len(all_windows) > 5:
            print(f"  ... and {len(all_windows) - 5} more")
    else:
        print("No windows found (this might be expected in some environments)")
    print()


def demo_system_integration():
    """Demonstrate system integration features"""
    print("🔧 System Integration Demo")
    print("-" * 30)
    
    # Screen resolution
    width, height = system_utils.get_screen_resolution()
    print(f"Screen Resolution: {width}x{height}")
    
    # System sound (with user permission)
    print("\n🔊 System Sound Test")
    user_input = input("Play system sound? (y/n): ").lower().strip()
    if user_input == 'y':
        success = system_utils.play_system_sound()
        if success:
            print("✅ System sound played successfully!")
        else:
            print("❌ Could not play system sound")
    else:
        print("⏭️  Skipped system sound test")
    
    print()


def demo_app_launcher():
    """Demonstrate application launcher (dry run)"""
    print("🚀 Application Launcher Demo (Dry Run)")
    print("-" * 30)
    
    apps_to_check = ['cursor', 'windsurf', 'code', 'notepad']
    
    for app in apps_to_check:
        print(f"Checking launcher support for: {app}")
        # Note: We don't actually launch to avoid opening unwanted applications
        print(f"  Platform: {PlatformDetector.get_platform_name()}")
        print(f"  Would attempt to launch: {app}")
    
    print("\n💡 To actually launch applications, use:")
    print("   app_launcher.open_application('cursor', '/path/to/project')")
    print()


def main():
    """Main demo function"""
    print("🎉 SimulateDev Cross-Platform Demo")
    print("=" * 50)
    print()
    
    try:
        # Run all demos
        demo_platform_detection()
        demo_keyboard_shortcuts()
        demo_window_management()
        demo_system_integration()
        demo_app_launcher()
        
        print("✅ Demo completed successfully!")
        print("\n🚀 Ready to use SimulateDev on your platform!")
        print("\nNext steps:")
        print("1. Run: python scripts/setup_platform.py")
        print("2. Install any missing dependencies")
        print("3. Try: python simulatedev.py --help")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("2. Check platform-specific requirements in docs/CROSS_PLATFORM.md")
        print("3. Run setup check: python scripts/setup_platform.py")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)