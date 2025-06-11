#!/usr/bin/env python3
"""
Comprehensive Test Suite for Enhanced IDE Project Checking Functionality

This script tests the enhanced IDE checking functionality that verifies not only if a coding IDE 
is running, but also that it's open with the specific project we care about by checking window titles.

Test Scenarios:
- A: Check if IDE is open with a specific project
- B: Open IDE and prevent unnecessary reopening  
- C: Switch from different project to target project
- Debug: Utility functions for debugging IDE state
"""

import asyncio
import os
import sys
import argparse
import shutil
import subprocess
from pathlib import Path
from utils.computer_use_utils import is_ide_open_with_project, ClaudeComputerUse
from agents.factory import AgentFactory
from agents.base import CodingAgentIdeType

class IDETester:
    """Comprehensive IDE testing class"""
    
    def __init__(self, ide_type="windsurf", delete_existing=False):
        self.ide_type = ide_type.lower()
        self.delete_existing = delete_existing
        self.claude = ClaudeComputerUse()
        self.test_project = "gemini-multimodal-playground"
        self.test_repo_url = "https://github.com/saharmor/gemini-multimodal-playground.git"
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_repos")
        self.project_path = os.path.join(self.base_dir, self.test_project)
        
        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Set IDE-specific properties
        if self.ide_type == "windsurf":
            self.agent_type = CodingAgentIdeType.WINDSURF
            self.ide_display_name = "Windsurf"
        elif self.ide_type == "cursor":
            self.agent_type = CodingAgentIdeType.CURSOR
            self.ide_display_name = "Cursor"
        elif self.ide_type == "claude_code":
            self.agent_type = CodingAgentIdeType.CLAUDE_CODE
            self.ide_display_name = "Claude Code"
        else:
            raise ValueError(f"Unsupported IDE type: {ide_type}")
    
    def print_separator(self, title):
        """Print a nice separator for test sections"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    def clone_or_prepare_repo(self):
        """Clone the test repository or prepare it"""
        if self.delete_existing and os.path.exists(self.project_path):
            print(f"🗑️  Deleting existing repository at {self.project_path}")
            shutil.rmtree(self.project_path)
        
        if not os.path.exists(self.project_path):
            print(f"📥 Cloning repository to {self.project_path}")
            try:
                subprocess.run(["git", "clone", self.test_repo_url, self.project_path], check=True)
                print(f"✅ Repository cloned successfully")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to clone repository: {e}")
                return False
        else:
            print(f"📁 Repository already exists at {self.project_path}")
        
        return True
    
    def is_headless_ide(self):
        """Check if this is a headless IDE (like Claude Code)"""
        return self.ide_type == "claude_code"
    
    # =============================================================================
    # DEBUG UTILITIES
    # =============================================================================
    
    def debug_ide_windows(self):
        """Debug what windows the IDE currently has open"""
        print(f"🔍 Debugging {self.ide_display_name} windows...")
        
        if self.is_headless_ide():
            # For headless IDEs, show current directory and project info
            current_dir = os.getcwd()
            project_name = os.path.basename(current_dir)
            print(f"📊 Headless IDE - Current working directory:")
            print(f"   Directory: {current_dir}")
            print(f"   Project: {project_name}")
            
            # Check if target project directory exists
            if os.path.exists(self.project_path):
                print(f"   Target project directory exists: {self.project_path}")
            else:
                print(f"   Target project directory missing: {self.project_path}")
            
            # Check if we're in the target project
            if self.test_project in project_name.lower():
                print(f"      ✅ Currently in target project '{self.test_project}'")
            else:
                print(f"      ⚠️  Not in target project (current: '{project_name}', target: '{self.test_project}')")
            
            return [project_name]
        
        if self.ide_type == "windsurf":
            # Windsurf runs as Electron
            script = '''
            tell application "System Events"
                tell process "Electron"
                    set windowTitles to name of every window
                end tell
            end tell
            return windowTitles
            '''
            process_name = "Electron"
        elif self.ide_type == "cursor":
            # Cursor runs as its own process
            script = '''
            tell application "System Events"
                tell process "Cursor"
                    set windowTitles to name of every window
                end tell
            end tell
            return windowTitles
            '''
            process_name = "Cursor"
        
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            window_titles = result.stdout.strip().split(",")
            
            print(f"📊 Found {len(window_titles)} {self.ide_display_name} windows:")
            for i, title in enumerate(window_titles, 1):
                title = title.strip()
                print(f"   {i}. '{title}'")
                
                # Check if it contains our target project
                if self.test_project in title.lower():
                    print(f"      ✅ Contains '{self.test_project}'")
                if "simulatedev" in title.lower():
                    print(f"      ✅ Contains 'simulatedev'")
            
            return window_titles
            
        except subprocess.CalledProcessError as e:
            print(f"❌ {self.ide_display_name} ({process_name}) is not running or error occurred: {e}")
            return []
    
    def close_ide_window(self, window_name):
        """Close a specific IDE window by name"""
        if self.is_headless_ide():
            print(f"⚠️  Cannot close windows for headless IDE {self.ide_display_name}")
            print(f"   Headless IDEs don't have GUI windows to close")
            return
        
        print(f"🗑️  Attempting to close {self.ide_display_name} window: '{window_name}'")
        
        if self.ide_type == "windsurf":
            process_name = "Electron"
        elif self.ide_type == "cursor":
            process_name = "Cursor"
        
        script = f'''
        tell application "System Events"
            tell process "{process_name}"
                repeat with w in windows
                    if name of w contains "{window_name}" then
                        click button 1 of w
                        exit repeat
                    end if
                end repeat
            end tell
        end tell
        '''
        
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            print(f"✅ Attempted to close window containing '{window_name}'")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error closing window: {e}")
    
    def open_ide_with_different_project(self):
        """Open IDE with the current directory (simulatedev project)"""
        current_dir = os.getcwd()
        project_name = os.path.basename(current_dir)
        
        if self.is_headless_ide():
            print(f"📁 For headless IDE {self.ide_display_name}:")
            print(f"   Current directory: {current_dir}")
            print(f"   Current project: {project_name}")
            print(f"   Note: Headless IDEs use the current working directory as the project")
            print(f"   To 'open' a different project, change to that directory before running commands")
            return
        
        print(f"🚀 Opening {self.ide_display_name} with project: {project_name}")
        print(f"📁 Project path: {current_dir}")
        
        try:
            # Open IDE with current directory
            subprocess.run(["open", "-a", self.ide_display_name, current_dir])
            print(f"⏳ Waiting 5 seconds for {self.ide_display_name} to open...")
            import time
            time.sleep(5)
            
            # Activate IDE
            activate_script = f'''
            tell application "{self.ide_display_name}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", activate_script], check=True)
            print(f"✅ {self.ide_display_name} should now be open with the {project_name} project")
            
        except Exception as e:
            print(f"❌ Error opening {self.ide_display_name}: {e}")
    
    # =============================================================================
    # TEST SCENARIOS
    # =============================================================================
    
    async def scenario_a_check_ide_with_project(self):
        """Scenario A: Check if IDE is open with the given project"""
        self.print_separator(f"SCENARIO A: Check if {self.ide_display_name} is open with project")
        
        print(f"🔍 Checking if {self.ide_display_name} is open with project '{self.test_project}'...")
        
        # Test the utility function directly (only for GUI IDEs)
        if not self.is_headless_ide():
            result = is_ide_open_with_project(self.ide_display_name, self.test_project)
            print(f"📊 Direct utility function result: {result}")
        else:
            result = None
            print(f"📊 Direct utility function: N/A (headless IDE)")
        
        # Test with agent
        agent = AgentFactory.create_agent(self.agent_type, self.claude)
        agent.set_current_project(self.project_path)
        
        agent_result = agent.is_ide_open_with_correct_project()
        print(f"🤖 Agent project checking result: {agent_result}")
        
        # Test combined method
        combined_result = await agent.is_coding_agent_open_with_project()
        print(f"🔗 Combined agent checking result: {combined_result}")
        
        return result, agent_result, combined_result
    
    async def scenario_b_open_ide_and_prevent_reopening(self):
        """Scenario B: Open IDE for project and verify it doesn't reopen if already open"""
        self.print_separator(f"SCENARIO B: Open {self.ide_display_name} and prevent unnecessary reopening")
        
        # Ensure we have the repository
        if not self.clone_or_prepare_repo():
            print("❌ Cannot proceed without repository")
            return False
        
        print(f"🚀 Opening {self.ide_display_name} with project '{self.test_project}'...")
        
        # Create agent and set project
        agent = AgentFactory.create_agent(self.agent_type, self.claude)
        
        # Change to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(self.project_path)
            agent.set_current_project(self.project_path)
            
            # First opening
            print(f"📂 First attempt to open {self.ide_display_name} interface...")
            first_open_result = await agent.open_coding_interface()
            print(f"✅ First open result: {first_open_result}")
            
            if first_open_result:
                print("⏳ Waiting 3 seconds before second attempt...")
                await asyncio.sleep(3)
                
                # Second opening attempt - should detect it's already open
                print(f"📂 Second attempt to open {self.ide_display_name} interface (should detect already open)...")
                second_open_result = await agent.open_coding_interface()
                print(f"✅ Second open result: {second_open_result}")
                
                # Verify it's still open with correct project
                still_open = await agent.is_coding_agent_open_with_project()
                print(f"🔍 Still open with correct project: {still_open}")
                
                return first_open_result and second_open_result and still_open
            else:
                print(f"❌ Failed to open {self.ide_display_name} initially")
                return False
                
        finally:
            os.chdir(original_cwd)
    
    async def scenario_c_switch_projects(self):
        """Scenario C: Test switching from one project to another"""
        self.print_separator(f"SCENARIO C: Switch from different project to target project")
        
        if self.is_headless_ide():
            print("📋 For headless IDEs, this scenario tests directory switching:")
            print(f"   1. Ensure you're NOT in the '{self.test_project}' directory")
            print("   2. Press Enter when ready to continue...")
        else:
            print("📋 This scenario requires manual setup:")
            print(f"   1. Open {self.ide_display_name} with a DIFFERENT project (not '{self.test_project}')")
            print("   2. Press Enter when ready to continue...")
        
        input("Press Enter to continue...")
        
        # Check what project IDE currently has open
        print(f"🔍 Checking current {self.ide_display_name} state...")
        
        if self.is_headless_ide():
            # For headless IDEs, check current directory
            current_dir = os.getcwd()
            current_project = os.path.basename(current_dir)
            current_state = self.test_project.lower() in current_project.lower()
            print(f"📊 Current directory: {current_dir}")
            print(f"📊 Is in '{self.test_project}' directory? {current_state}")
        else:
            # For GUI IDEs, check window titles
            current_state = is_ide_open_with_project(self.ide_display_name, self.test_project)
            print(f"📊 Is {self.ide_display_name} open with '{self.test_project}'? {current_state}")
        
        if current_state:
            if self.is_headless_ide():
                print(f"⚠️  Already in '{self.test_project}' directory. Please change to a different directory first.")
            else:
                print(f"⚠️  {self.ide_display_name} is already open with '{self.test_project}'. Please open it with a different project first.")
            return False
        
        # Now try to open with our target project
        if not self.clone_or_prepare_repo():
            print("❌ Cannot proceed without repository")
            return False
        
        print(f"🔄 Now attempting to open {self.ide_display_name} with '{self.test_project}'...")
        
        agent = AgentFactory.create_agent(self.agent_type, self.claude)
        
        original_cwd = os.getcwd()
        try:
            # For headless IDEs, change to the project directory
            if self.is_headless_ide():
                print(f"📁 Changing to project directory: {self.project_path}")
                os.chdir(self.project_path)
            
            agent.set_current_project(self.project_path)
            
            # This should detect that IDE is open but with wrong project (or wrong directory for headless)
            print("🔍 Checking if open with correct project...")
            correct_project = await agent.is_coding_agent_open_with_project()
            print(f"📊 Open with correct project: {correct_project}")
            
            if not correct_project:
                print(f"🚀 Opening {self.ide_display_name} with correct project...")
                open_result = await agent.open_coding_interface()
                print(f"✅ Open result: {open_result}")
                
                if open_result:
                    print("⏳ Waiting 3 seconds for stabilization...")
                    await asyncio.sleep(3)
                    
                    # Verify it's now open with correct project
                    final_check = await agent.is_coding_agent_open_with_project()
                    print(f"🎯 Final check - open with correct project: {final_check}")
                    
                    return final_check
                else:
                    print(f"❌ Failed to open {self.ide_display_name} with correct project")
                    return False
            else:
                print("✅ Already open with correct project")
                return True
                
        finally:
            # Always restore original directory for headless IDEs
            if self.is_headless_ide():
                os.chdir(original_cwd)
    
    # =============================================================================
    # MAIN TEST RUNNER
    # =============================================================================
    
    async def run_all_scenarios(self):
        """Run all test scenarios"""
        print(f"🧪 Starting {self.ide_display_name} IDE Project Checking Tests")
        print(f"🎯 Target project: {self.test_project}")
        print(f"📁 Project path: {self.project_path}")
        print(f"🗑️  Delete existing: {self.delete_existing}")
        
        results = {}
        
        try:
            # Scenario A
            results['scenario_a'] = await self.scenario_a_check_ide_with_project()
            
            # Scenario B
            results['scenario_b'] = await self.scenario_b_open_ide_and_prevent_reopening()
            
            # Scenario C
            results['scenario_c'] = await self.scenario_c_switch_projects()
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
        
        # Print summary
        self.print_separator("TEST SUMMARY")
        print("📊 Results:")
        print(f"   Scenario A (Check if open): {results.get('scenario_a', 'Failed')}")
        print(f"   Scenario B (Prevent reopening): {results.get('scenario_b', 'Failed')}")
        print(f"   Scenario C (Switch projects): {results.get('scenario_c', 'Failed')}")
        
        return results
    
    async def run_single_scenario(self, scenario):
        """Run a single test scenario"""
        if scenario == 'a':
            return await self.scenario_a_check_ide_with_project()
        elif scenario == 'b':
            return await self.scenario_b_open_ide_and_prevent_reopening()
        elif scenario == 'c':
            return await self.scenario_c_switch_projects()
        else:
            print(f"❌ Unknown scenario: {scenario}")
            return False
    
    def run_debug_command(self, debug_cmd):
        """Run debug commands"""
        if debug_cmd == "windows":
            return self.debug_ide_windows()
        elif debug_cmd == "setup-different":
            return self.open_ide_with_different_project()
        elif debug_cmd.startswith("close:"):
            window_name = debug_cmd.split(":", 1)[1]
            return self.close_ide_window(window_name)
        else:
            print(f"❌ Unknown debug command: {debug_cmd}")
            print("Available debug commands:")
            print("  windows           - Show current IDE windows")
            print("  setup-different   - Open IDE with simulatedev project")
            print("  close:<name>      - Close window containing <name>")
            return False

async def main():
    parser = argparse.ArgumentParser(description="Test IDE project checking functionality")
    parser.add_argument("--ide", choices=['windsurf', 'cursor', 'claude_code'], default='windsurf',
                       help="Which IDE to test (default: windsurf)")
    parser.add_argument("--delete-existing", action="store_true", 
                       help="Delete existing local repository before testing")
    parser.add_argument("--scenario", choices=['a', 'b', 'c', 'all'], default='all',
                       help="Which scenario to run (default: all)")
    parser.add_argument("--debug", 
                       help="Run debug command (windows, setup-different, close:<name>)")
    
    args = parser.parse_args()
    
    tester = IDETester(ide_type=args.ide, delete_existing=args.delete_existing)
    
    if args.debug:
        tester.run_debug_command(args.debug)
    elif args.scenario == 'all':
        await tester.run_all_scenarios()
    else:
        await tester.run_single_scenario(args.scenario)

if __name__ == "__main__":
    print("🧪 Enhanced IDE Project Checking Test Suite")
    print("=" * 50)
    asyncio.run(main()) 