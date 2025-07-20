#!/usr/bin/env python3
"""
Platform-specific setup script for SimulateDev

This script helps users install platform-specific dependencies and configure
their system for optimal SimulateDev operation.
"""

import os
import platform
import subprocess
import sys
from typing import List, Tuple


class PlatformSetup:
    """Platform-specific setup and dependency management"""
    
    def __init__(self):
        self.platform = platform.system()
        self.distro = self._detect_linux_distro() if self.platform == "Linux" else None
    
    def _detect_linux_distro(self) -> str:
        """Detect Linux distribution"""
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                if 'ubuntu' in content or 'debian' in content:
                    return 'debian'
                elif 'fedora' in content or 'rhel' in content or 'centos' in content:
                    return 'redhat'
                elif 'arch' in content:
                    return 'arch'
                elif 'suse' in content:
                    return 'suse'
        except FileNotFoundError:
            pass
        return 'unknown'
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            print(f"✅ Python {version.major}.{version.minor}.{version.micro} meets requirements (3.8+)")
            return True
        else:
            print(f"❌ Python {version.major}.{version.minor}.{version.micro} is too old. Please upgrade to Python 3.8+")
            return False
    
    def check_git(self) -> bool:
        """Check if Git is installed"""
        try:
            result = subprocess.run(['git', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Git is installed: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        print("❌ Git is not installed or not in PATH")
        return False
    
    def install_platform_dependencies(self) -> List[str]:
        """Install platform-specific dependencies"""
        instructions = []
        
        if self.platform == "Linux":
            instructions.extend(self._setup_linux())
        elif self.platform == "Windows":
            instructions.extend(self._setup_windows())
        elif self.platform == "Darwin":
            instructions.extend(self._setup_macos())
        else:
            instructions.append(f"⚠️  Unknown platform: {self.platform}")
        
        return instructions
    
    def _setup_linux(self) -> List[str]:
        """Setup Linux-specific dependencies"""
        instructions = []
        missing_tools = []
        
        # Check for window management tools
        tools_to_check = ['xdotool', 'wmctrl']
        available_tools = []
        
        for tool in tools_to_check:
            try:
                subprocess.run(['which', tool], capture_output=True, check=True)
                available_tools.append(tool)
                print(f"✅ {tool} is installed")
            except subprocess.CalledProcessError:
                missing_tools.append(tool)
        
        if not available_tools:
            instructions.append("❌ Window management tools missing. Install one of the following:")
            
            if self.distro == 'debian':
                instructions.append("   sudo apt-get update && sudo apt-get install xdotool wmctrl")
            elif self.distro == 'redhat':
                instructions.append("   sudo dnf install xdotool wmctrl")
                instructions.append("   # or: sudo yum install xdotool wmctrl")
            elif self.distro == 'arch':
                instructions.append("   sudo pacman -S xdotool wmctrl")
            elif self.distro == 'suse':
                instructions.append("   sudo zypper install xdotool wmctrl")
            else:
                instructions.append("   Install xdotool and/or wmctrl using your package manager")
        else:
            print(f"✅ Window management available: {', '.join(available_tools)}")
        
        # Check for audio tools (optional)
        audio_tools = ['paplay', 'aplay']
        has_audio = False
        for tool in audio_tools:
            try:
                subprocess.run(['which', tool], capture_output=True, check=True)
                has_audio = True
                print(f"✅ Audio support available: {tool}")
                break
            except subprocess.CalledProcessError:
                continue
        
        if not has_audio:
            instructions.append("⚠️  Audio notification support not found (optional)")
            if self.distro == 'debian':
                instructions.append("   Install with: sudo apt-get install pulseaudio-utils alsa-utils")
            else:
                instructions.append("   Install pulseaudio-utils or alsa-utils for audio notifications")
        
        return instructions
    
    def _setup_windows(self) -> List[str]:
        """Setup Windows-specific dependencies"""
        instructions = []
        
        # Check if pywin32 is installed
        try:
            import win32gui
            print("✅ pywin32 is available")
        except ImportError:
            instructions.append("❌ pywin32 not installed")
            instructions.append("   This will be installed automatically with: pip install -r requirements.txt")
        
        # Check for common IDE locations
        ide_paths = {
            'Cursor': [
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\cursor\Cursor.exe'),
                r'C:\Users\%USERNAME%\AppData\Local\Programs\cursor\Cursor.exe',
            ],
            'Windsurf': [
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\Windsurf\Windsurf.exe'),
                r'C:\Users\%USERNAME%\AppData\Local\Programs\Windsurf\Windsurf.exe',
            ]
        }
        
        for ide, paths in ide_paths.items():
            found = False
            for path in paths:
                if os.path.exists(path):
                    print(f"✅ {ide} found at: {path}")
                    found = True
                    break
            if not found:
                instructions.append(f"⚠️  {ide} not found in standard locations")
        
        return instructions
    
    def _setup_macos(self) -> List[str]:
        """Setup macOS-specific dependencies"""
        instructions = []
        
        # Check for Xcode Command Line Tools
        try:
            subprocess.run(['xcode-select', '--version'], capture_output=True, check=True)
            print("✅ Xcode Command Line Tools are installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            instructions.append("❌ Xcode Command Line Tools not found")
            instructions.append("   Install with: xcode-select --install")
        
        # Check for common IDE locations
        ide_apps = ['Cursor.app', 'Windsurf.app']
        apps_dir = '/Applications'
        
        for ide in ide_apps:
            ide_path = os.path.join(apps_dir, ide)
            if os.path.exists(ide_path):
                print(f"✅ {ide} found in Applications")
            else:
                instructions.append(f"⚠️  {ide} not found in /Applications")
        
        return instructions
    
    def check_ide_installations(self) -> List[str]:
        """Check for IDE installations"""
        instructions = []
        
        print("\n🔍 Checking for supported IDEs...")
        
        if self.platform == "Darwin":
            # macOS - check Applications folder
            apps_to_check = {
                'Cursor': '/Applications/Cursor.app',
                'Windsurf': '/Applications/Windsurf.app'
            }
            
            for ide, path in apps_to_check.items():
                if os.path.exists(path):
                    print(f"✅ {ide} is installed")
                else:
                    instructions.append(f"⚠️  {ide} not found. Download from official website")
        
        elif self.platform == "Linux":
            # Linux - check common installation paths and PATH
            ides_to_check = ['cursor', 'windsurf', 'code']
            
            for ide in ides_to_check:
                try:
                    subprocess.run(['which', ide], capture_output=True, check=True)
                    print(f"✅ {ide} is in PATH")
                except subprocess.CalledProcessError:
                    instructions.append(f"⚠️  {ide} not found in PATH")
        
        elif self.platform == "Windows":
            # Windows - check common installation directories
            # This is handled in _setup_windows()
            pass
        
        return instructions
    
    def run_full_check(self):
        """Run complete platform setup check"""
        print("🚀 SimulateDev Platform Setup Check")
        print("=" * 40)
        
        all_instructions = []
        
        # Basic checks
        print("\n📋 Basic Requirements:")
        if not self.check_python_version():
            all_instructions.append("❌ Upgrade Python to 3.8 or later")
        
        if not self.check_git():
            all_instructions.append("❌ Install Git")
        
        # Platform-specific checks
        print(f"\n🖥️  Platform-Specific Setup ({self.platform}):")
        platform_instructions = self.install_platform_dependencies()
        all_instructions.extend(platform_instructions)
        
        # IDE checks
        ide_instructions = self.check_ide_installations()
        all_instructions.extend(ide_instructions)
        
        # Summary
        print("\n" + "=" * 40)
        if all_instructions:
            print("❌ Setup Issues Found:")
            for instruction in all_instructions:
                print(f"   {instruction}")
            print("\n💡 Please address the issues above before running SimulateDev")
            return False
        else:
            print("✅ All checks passed! Your system is ready for SimulateDev")
            print("\n🎉 Next steps:")
            print("   1. Create a virtual environment: python -m venv venv")
            if self.platform == "Windows":
                print("   2. Activate it: venv\\Scripts\\activate.bat")
            else:
                print("   2. Activate it: source venv/bin/activate")
            print("   3. Install dependencies: pip install -r requirements.txt")
            print("   4. Copy .env.example to .env and add your API keys")
            print("   5. Run SimulateDev: python simulatedev.py --help")
            return True


def main():
    """Main setup function"""
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("SimulateDev Platform Setup")
        print("Usage: python scripts/setup_platform.py")
        print("\nThis script checks your system for SimulateDev compatibility")
        print("and provides instructions for installing missing dependencies.")
        return
    
    setup = PlatformSetup()
    setup.run_full_check()


if __name__ == "__main__":
    main()