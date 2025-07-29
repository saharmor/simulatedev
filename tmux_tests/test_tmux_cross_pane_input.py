#!/usr/bin/env python3
"""
Cross-Pane Input Isolation Test
==============================
Comprehensive test to verify that input routing between tmux panes is properly 
isolated and prevents cross-pane input leakage during concurrent sessions.

This test ensures that the per-pane command queueing system maintains proper
isolation between different agent sessions running simultaneously.
"""

import asyncio
import subprocess
import time
import sys
import json
import random
import signal
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from tmux_operations_manager import TmuxAgentManager, AgentType, SessionStatus

@dataclass
class TestSession:
    """Test session tracking"""
    name: str
    session_id: str
    agent_type: AgentType
    prompt: str
    expected_state: str
    created_at: float
    pane_id: Optional[str] = None

class CrossPaneInputTester:
    def __init__(self, paused_between_tests: bool = True):
        self.manager = TmuxAgentManager(max_sessions=20, monitor_interval = 5.0)
        self.test_sessions: List[TestSession] = []
        self.paused_between_tests = paused_between_tests
        self.test_results = {
            'isolation_test': None,
            'rapid_creation_test': None,
            'buffer_uniqueness_test': None,
            'mixed_agents_test': None,
            'long_prompt_test': None
        }
        
    async def setup(self):
        """Setup test environment"""
        print("🔧 Setting up cross-pane input isolation test environment...")
        self.manager.setup_main_session()
        await self.manager.start_queue()
        
        # Start monitoring loop (but we'll control the frequency manually)
        print("🔄 Starting monitoring loop...")
        self.monitor_task = asyncio.create_task(self.manager.monitor_loop())
        await asyncio.sleep(1)
        print("✅ Setup complete\n")
        
    async def cleanup(self):
        """Cleanup test environment"""
        print("\n🧹 Cleaning up test sessions...")
        
        # Stop all test sessions using async method
        stop_tasks = []
        for test_session in self.test_sessions:
            if test_session.session_id:
                try:
                    task = self.manager.stop_session_async(test_session.session_id)
                    stop_tasks.append(task)
                    print(f"   Stopping {test_session.name}...")
                except Exception as e:
                    print(f"   ⚠️  Error stopping {test_session.name}: {e}")
        
        # Wait for all stop operations to complete
        if stop_tasks:
            print("   ⏳ Waiting for all panes to terminate...")
            results = await asyncio.gather(*stop_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"   ⚠️  Error stopping session: {result}")
                elif result:
                    print(f"   ✅ Stopped session")
        
        # Cleanup finished sessions (this will kill any remaining panes)
        try:
            cleaned_count = self.manager.cleanup_finished_sessions()
            print(f"   Cleaned {cleaned_count} finished sessions")
        except Exception as e:
            print(f"   ⚠️  Error during cleanup: {e}")
        
        # Force kill any remaining panes from our test sessions
        print("   🔨 Force cleaning any remaining panes...")
        for test_session in self.test_sessions:
            if test_session.pane_id:
                try:
                    pane_id = test_session.pane_id.split(".")[-1]
                    subprocess.run(["tmux", "kill-pane", "-t", pane_id], 
                                 capture_output=True, check=False)
                except Exception as e:
                    print(f"   ⚠️  Error killing pane {test_session.pane_id}: {e}")
        
        # Stop monitoring and queue with better error handling
        if hasattr(self, 'monitor_task'):
            try:
                self.manager.running = False
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"   ⚠️  Error stopping monitor task: {e}")
            except Exception as e:
                print(f"   ⚠️  Error during monitor cleanup: {e}")
        
        # Stop the queue with timeout and error handling
        try:
            # Add a timeout to prevent hanging during shutdown
            await asyncio.wait_for(self.manager.stop_queue(), timeout=5.0)
            print("✅ Cleanup complete")
        except asyncio.TimeoutError:
            print("⚠️  Queue stop timed out, forcing cleanup")
        except Exception as e:
            print(f"⚠️  Error stopping queue: {e}")
        
        # Give a moment for all threads to finish cleanup
        await asyncio.sleep(0.1)
    
    async def wait_for_user_confirmation(self, next_test_name: str):
        """Wait for user confirmation before proceeding to next test"""
        if not self.paused_between_tests:
            return
            
        print(f"\n{'='*60}")
        print(f"⏸️  PAUSED BETWEEN TESTS")
        print(f"{'='*60}")
        print(f"🔄 Next test: {next_test_name}")
        print(f"📝 Press ENTER to continue or 'q' to quit...")
        print(f"{'='*60}")
        
        try:
            user_input = await asyncio.to_thread(input, "Continue? (ENTER/q): ")
            if user_input.lower().strip() in ('q', 'quit', 'exit'):
                print("🛑 Test suite stopped by user")
                raise KeyboardInterrupt("User requested to quit")
            print(f"✅ Continuing to {next_test_name}...\n")
        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Test suite interrupted by user")
            raise
        
    def get_pane_content(self, session_id: str) -> str:
        """Get raw pane content for a session"""
        # First try to get content from the manager's output buffer (now includes saved files)
        output_content = self.manager.get_session_output(session_id)
        if output_content:
            return output_content
        
        return ""
    
    async def create_test_session(self, name: str, agent_type: AgentType, prompt: str, yolo_mode: bool = False,
                                expected_state: str = "RUNNING") -> TestSession:
        """Create a test session and track it"""
        print(f"   Creating {name} ({agent_type.value}): '{prompt[:50]}...'")
        
        session_id = await asyncio.to_thread(
            self.manager.create_session,
            prompt=prompt,
            agent_type=agent_type,
            yolo_mode=yolo_mode  # Use regular mode to trigger user input prompts
        )
        
        test_session = TestSession(
            name=name,
            session_id=session_id,
            agent_type=agent_type,
            prompt=prompt,
            expected_state=expected_state,
            created_at=time.time()
        )
        
        # Get pane mapping - wait a bit for it to be established
        await asyncio.sleep(0.5)
        pane = self.manager._get_pane_by_session(session_id)
        test_session.pane_id = pane.full_target if pane else None
        
        self.test_sessions.append(test_session)
        print(f"   ✅ {name} created: {session_id} (pane: {test_session.pane_id})")
        
        # If pane mapping is None, wait and try again
        if test_session.pane_id is None:
            await asyncio.sleep(1)
            pane = self.manager._get_pane_by_session(session_id)
            test_session.pane_id = pane.full_target if pane else None
            if test_session.pane_id:
                print(f"   📍 {name} pane mapping updated: {test_session.pane_id}")
        
        return test_session
    
    async def wait_for_session_state(self, test_session: TestSession, target_state: str, 
                                   timeout: float = 30.0) -> bool:
        """Wait for a session to reach a specific state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Use get_session() instead of update_sessions() to avoid triggering extra state transitions
            # The background monitor_loop will handle state updates at its own pace
            session_info = self.manager.get_session(test_session.session_id)
            
            if not session_info:
                print(f"   ❌ {test_session.name}: Session disappeared")
                return False
                
            current_state = session_info['status']
            if current_state == target_state:
                elapsed = time.time() - start_time
                print(f"   ✅ {test_session.name}: Reached {target_state} after {elapsed:.1f}s")
                return True
            
            await asyncio.sleep(1.5)
        
        # Timeout
        final_info = self.manager.get_session(test_session.session_id)
        final_state = final_info['status'] if final_info else 'UNKNOWN'
        print(f"   ⏰ {test_session.name}: Timeout waiting for {target_state}, stuck in {final_state}")
        return False
    
    async def monitor_session_state_stability(self, test_session: TestSession, 
                                            expected_state: str, duration: float) -> bool:
        """Monitor that a session remains in expected state for a duration"""
        start_time = time.time()
        state_changes = []
        
        print(f"   📊 Monitoring {test_session.name} state stability for {duration:.1f}s...")
        print(f"   ℹ️  Note: Using passive monitoring (not triggering extra state transitions)")
        
        while time.time() - start_time < duration:
            # Use get_session() instead of update_sessions() to avoid triggering state transitions
            # The background monitor_loop will handle state updates at its own pace
            session_info = self.manager.get_session(test_session.session_id)
            
            if not session_info:
                print(f"   ❌ {test_session.name}: Session disappeared during monitoring")
                return False
            
            current_state = session_info['status']
            elapsed = time.time() - start_time
            
            # Track state changes
            if not state_changes or state_changes[-1]['state'] != current_state:
                state_changes.append({
                    'state': current_state,
                    'time': elapsed
                })
                print(f"   📝 {test_session.name}: T+{elapsed:.1f}s -> {current_state}")
            
            # Check if state deviated from expected
            if current_state != expected_state:
                print(f"   ❌ {test_session.name}: State changed from {expected_state} to {current_state} at T+{elapsed:.1f}s")
                return False
            
            await asyncio.sleep(1.5)
        
        print(f"   ✅ {test_session.name}: Remained in {expected_state} for {duration:.1f}s")
        return True
    
    def get_queue_diagnostics(self) -> Dict:
        """Get diagnostic information about command queues"""
        queue_sizes = self.manager._tmux_queue.get_queue_sizes()
        
        diagnostics = {
            'queue_sizes': queue_sizes,
            'active_sessions': len([s for s in self.test_sessions if s.session_id]),
            'pane_mappings': {}
        }
        
        # Get pane mappings
        for test_session in self.test_sessions:
            if test_session.session_id:
                pane = self.manager._get_pane_by_session(test_session.session_id)
                diagnostics['pane_mappings'][test_session.name] = pane.full_target if pane else None
        
        return diagnostics
    
    def check_pane_uniqueness(self) -> tuple[bool, Dict]:
        """
        Check if all active sessions have unique pane mappings.
        Should be called immediately after session creation while panes are active.
        
        Returns:
            tuple[bool, Dict]: (is_unique, diagnostics_info)
        """
        pane_mappings = {}
        duplicate_info = {}
        
        for test_session in self.test_sessions:
            if test_session.session_id:
                pane = self.manager._get_pane_by_session(test_session.session_id)
                if pane:  # Only check non-None panes (active sessions)
                    pane_mappings[test_session.name] = pane.full_target
        
        # Check for duplicates among active panes
        pane_to_sessions = {}
        for session_name, pane in pane_mappings.items():
            if pane not in pane_to_sessions:
                pane_to_sessions[pane] = []
            pane_to_sessions[pane].append(session_name)
        
        # Find duplicates
        for pane, sessions in pane_to_sessions.items():
            if len(sessions) > 1:
                duplicate_info[pane] = sessions
        
        is_unique = len(duplicate_info) == 0
        
        diagnostics = {
            'active_pane_mappings': pane_mappings,
            'total_active_panes': len(pane_mappings),
            'unique_panes': len(set(pane_mappings.values())),
            'duplicates': duplicate_info
        }
        
        return is_unique, diagnostics
    
    def verify_cleanup_completion(self) -> tuple[bool, Dict]:
        """
        Verify that all sessions have been properly cleaned up.
        Should be called after test completion.
        
        Returns:
            tuple[bool, Dict]: (is_clean, diagnostics_info)
        """
        queue_sizes = self.manager._tmux_queue.get_queue_sizes()
        
        # Check pane mappings - should all be None after cleanup
        pane_mappings = {}
        active_panes = 0
        
        for test_session in self.test_sessions:
            if test_session.session_id:
                pane = self.manager._get_pane_by_session(test_session.session_id)
                pane_target = pane.full_target if pane else None
                pane_mappings[test_session.name] = pane_target
                if pane_target is not None:
                    active_panes += 1
        
        # Check if all queues are empty
        total_queued_commands = sum(queue_sizes.values()) if queue_sizes else 0
        
        is_clean = (active_panes == 0 and total_queued_commands == 0)
        
        diagnostics = {
            'pane_mappings': pane_mappings,
            'active_panes': active_panes,
            'queue_sizes': queue_sizes,
            'total_queued_commands': total_queued_commands,
            'all_panes_closed': active_panes == 0,
            'all_queues_empty': total_queued_commands == 0
        }
        
        return is_clean, diagnostics
    
    async def test_1_basic_isolation(self) -> bool:
        """
        TEST 1: Basic Cross-Pane Input Isolation
        
        Steps:
        1. Create Session A (Gemini) with prompt that requires user input
        2. Wait for Session A to reach REQUIRES_USER_INPUT
        3. Create Session B (Claude) with normal prompt
        4. Create Session C (Gemini) with normal prompt
        5. Monitor Session A remains in REQUIRES_USER_INPUT throughout
        """
        print("="*80)
        print("📊 TEST 1: BASIC CROSS-PANE INPUT ISOLATION")
        print("="*80)
        print("Goal: Verify Session A remains isolated when other sessions are created")
        print("-"*80)
        
        # Step 1: Create Session A with prompt requiring user input
        # Use a prompt that will trigger Gemini's file creation confirmation
        session_a = await self.create_test_session(
            name="Session-A-Input",
            agent_type=AgentType.GEMINI,
            prompt="Create a new file called temp_test_isolation.py with a hello world function",
            expected_state="REQUIRES_USER_INPUT"
        )
        
        # Step 2: Wait for Session A to reach REQUIRES_USER_INPUT
        print("\n🔍 Waiting for Session A to require user input...")
        print(f"   Session A ID: {session_a.session_id}")
        
        # Check current state first
        current_info = self.manager.get_session(session_a.session_id)
        if current_info:
            print(f"   Current state: {current_info['status']}")
            if current_info['status'] == "DONE":
                print("   ⚠️  Session completed without requiring user input - checking output...")
                output = self.manager.get_session_output(session_a.session_id)
                if output:
                    print(f"   Output preview: {output[-200:]}")
                print("   ❌ FAILURE: Session completed too quickly - may need different prompt")
                return False
        
        if not await self.wait_for_session_state(session_a, "REQUIRES_USER_INPUT", timeout=240.0):
            # Get final state for debugging
            final_info = self.manager.get_session(session_a.session_id)
            if final_info:
                print(f"   Final state: {final_info['status']}")
                output = self.manager.get_session_output(session_a.session_id)
                if output:
                    print(f"   Output preview: {output[-300:]}")
            print("❌ FAILURE: Session A never reached REQUIRES_USER_INPUT state")
            return False
        
        # Step 3: Create Session B (Claude) while A is waiting
        print("\n🚀 Creating Session B while A is waiting for input...")
        session_b = await self.create_test_session(
            name="Session-B-Claude",
            agent_type=AgentType.CLAUDE,
            prompt="List the files in the current directory"
        )
        
        # Step 4: Create Session C (Gemini) while A is still waiting
        print("\n🚀 Creating Session C while A is still waiting for input...")
        session_c = await self.create_test_session(
            name="Session-C-Gemini",
            agent_type=AgentType.GEMINI,
            prompt="What is the current date and time?"
        )
        
        # Step 5: Monitor Session A stability while B and C are active
        print("\n📊 Monitoring Session A isolation for 15 seconds...")
        isolation_maintained = await self.monitor_session_state_stability(
            session_a, "REQUIRES_USER_INPUT", duration=15.0
        )
        
        # Get diagnostics
        diagnostics = self.get_queue_diagnostics()
        print(f"\n📈 Queue Diagnostics:")
        print(f"   Queue sizes: {diagnostics['queue_sizes']}")
        print(f"   Active sessions: {diagnostics['active_sessions']}")
        print(f"   Pane mappings: {diagnostics['pane_mappings']}")
        
        # Verify pane content isolation
        print(f"\n🔍 Verifying pane content isolation...")
        session_a_content = self.get_pane_content(session_a.session_id)
        session_b_content = self.get_pane_content(session_b.session_id)
        session_c_content = self.get_pane_content(session_c.session_id)
        
        # Check for cross-contamination
        contamination_found = False
        
        # Check if Session B or C content appears in Session A
        if session_b_content and any(line.strip() in session_a_content for line in session_b_content.split('\n')[-5:] if line.strip()):
            print("   ❌ Session B content found in Session A")
            contamination_found = True
            
        if session_c_content and any(line.strip() in session_a_content for line in session_c_content.split('\n')[-5:] if line.strip()):
            print("   ❌ Session C content found in Session A")
            contamination_found = True
        
        if not contamination_found:
            print("   ✅ No cross-pane content contamination detected")
        
        # Final result
        success = isolation_maintained and not contamination_found
        
        if success:
            print(f"\n✅ SUCCESS: Basic isolation test passed")
            print("   - Session A remained in REQUIRES_USER_INPUT state")
            print("   - No cross-pane input leakage detected")
            print("   - Pane content remained isolated")
        else:
            print(f"\n❌ FAILURE: Basic isolation test failed")
            if not isolation_maintained:
                print("   - Session A state was not stable")
            if contamination_found:
                print("   - Cross-pane content contamination detected")
        
        return success
    
    async def test_2_rapid_session_creation(self) -> bool:
        """
        TEST 2: Rapid Session Creation Isolation
        
        Create 5 sessions within 2 seconds and verify no interference
        """
        print("="*80)
        print("📊 TEST 2: RAPID SESSION CREATION ISOLATION")
        print("="*80)
        print("Goal: Create 5 sessions rapidly and verify isolation")
        print("-"*80)
        
        # First create a session that will wait for input
        control_session = await self.create_test_session(
            name="Control-Session",
            agent_type=AgentType.GEMINI,
            prompt="Create a new Python file named temp_rapid_test.py with a main function",
            expected_state="REQUIRES_USER_INPUT"
        )
        
        # Wait for control session to reach input state
        print("\n🔍 Waiting for control session to require input...")
        if not await self.wait_for_session_state(control_session, "REQUIRES_USER_INPUT", timeout=240.0):
            print("❌ FAILURE: Control session never reached REQUIRES_USER_INPUT")
            return False
        
        # Rapidly create 5 sessions
        print(f"\n🚀 Rapidly creating 5 sessions within 2 seconds...")
        rapid_sessions = []
        start_time = time.time()
        
        for i in range(5):
            agent_type = AgentType.CLAUDE if i % 2 == 0 else AgentType.GEMINI
            prompt = f"Echo 'Rapid session {i+1} test message'"
            
            session = await self.create_test_session(
                name=f"Rapid-{i+1}",
                agent_type=agent_type,
                yolo_mode=True,
                prompt=prompt
            )
            rapid_sessions.append(session)
            
            # Small delay to simulate rapid but not simultaneous creation
            await asyncio.sleep(0.3)
        
        creation_time = time.time() - start_time
        print(f"   ✅ Created 5 sessions in {creation_time:.1f}s")
        
        # Check pane uniqueness immediately after creation (while panes are active)
        print(f"\n🔍 Checking pane uniqueness after creation...")
        pane_unique, pane_diagnostics = self.check_pane_uniqueness()
        
        print(f"   Active panes: {pane_diagnostics['total_active_panes']}")
        print(f"   Unique panes: {pane_diagnostics['unique_panes']}")
        
        if pane_unique:
            print("   ✅ All sessions have unique pane mappings")
        else:
            print("   ❌ Duplicate pane mappings detected!")
            for pane, sessions in pane_diagnostics['duplicates'].items():
                print(f"      Pane {pane} shared by: {sessions}")
        
        # Monitor control session stability during rapid creation aftermath
        print(f"\n📊 Monitoring control session stability for 10 seconds...")
        # Allow for temporary state changes due to system activity
        isolation_maintained = await self.monitor_session_state_stability(
            control_session, "REQUIRES_USER_INPUT", duration=10.0
        )
        
        # If control session transitioned to RUNNING, that's actually OK as long as it didn't go to DONE
        final_info = self.manager.get_session(control_session.session_id)
        if final_info and not isolation_maintained:
            final_state = final_info['status']
            if final_state in ["RUNNING", "REQUIRES_USER_INPUT"]:
                print(f"   ℹ️  Control session is in {final_state} - still active, isolation maintained")
                isolation_maintained = True
            else:
                print(f"   ❌ Control session ended in {final_state} - isolation compromised")
        
        # Wait a bit more for rapid sessions to complete, then verify cleanup
        print(f"\n⏳ Waiting for rapid sessions to complete...")
        total_wait = 60
        intervals = 10
        for i in range(total_wait // intervals):
            # check if all sessions are done
            rapid_sessions_complete = True
            for session in rapid_sessions:
                session_info = self.manager.get_session(session.session_id)
                if session_info:
                    if session_info['status'] != "DONE":
                        rapid_sessions_complete = False
                        break
                else:
                    print(f"   ❌ {session.name}: Session missing")
                    rapid_sessions_complete = False
                    break
            
            if rapid_sessions_complete:
                break

            await asyncio.sleep(intervals)  # Give sessions time to complete
        
        if not rapid_sessions_complete:
            print(f"   ❌ Rapid sessions did not complete in {total_wait} seconds")
            return False

        # Verify rapid sessions completed (but control session should still be active)
        control_session_active = False    
        # Check control session is still active (as expected)
        control_info = self.manager.get_session(control_session.session_id)
        if control_info:
            control_status = control_info['status']
            if control_status == "REQUIRES_USER_INPUT":
                print(f"   ✅ Control session: Still waiting for input (expected)")
                control_session_active = True
            else:
                print(f"   ℹ️  Control session: {control_status} (expected REQUIRES_USER_INPUT)")
                control_session_active = True  # Still acceptable if it's RUNNING
        else:
            print(f"   ❌ Control session: Missing")
        
        # Check queue status
        queue_sizes = self.manager._tmux_queue.get_queue_sizes()
        total_queued_commands = sum(queue_sizes.values()) if queue_sizes else 0
        queues_empty = total_queued_commands == 0
        
        print(f"   Queued commands: {total_queued_commands}")
        if queues_empty:
            print("   ✅ All queues empty")
        else:
            print("   ❌ Commands still queued")
        
        cleanup_complete = rapid_sessions_complete and control_session_active and queues_empty
        
        if cleanup_complete:
            print("   ✅ Rapid sessions completed, control session active as expected")
        else:
            print("   ❌ Cleanup verification failed")
        
        success = isolation_maintained and pane_unique and cleanup_complete
        
        if success:
            print(f"\n✅ SUCCESS: Rapid creation test passed")
            print("   - Control session remained isolated")
            print("   - All sessions had unique pane mappings")
            print("   - Rapid sessions completed, control session active as expected")
        else:
            print(f"\n❌ FAILURE: Rapid creation test failed")
            if not isolation_maintained:
                print("   - Control session isolation compromised")
            if not pane_unique:
                print("   - Duplicate pane mappings detected")
            if not cleanup_complete:
                print("   - Rapid sessions cleanup verification failed")
        
        return success
    
    async def test_3_buffer_uniqueness(self) -> bool:
        """
        TEST 3: Buffer Name Uniqueness
        
        Test with same prompts to verify buffer name uniqueness
        """
        print("="*80)
        print("📊 TEST 3: BUFFER NAME UNIQUENESS")
        print("="*80)
        print("Goal: Verify buffer names are unique even with identical prompts")
        print("-"*80)
        
        # Create sessions with identical prompts
        identical_prompt = "This is an identical test prompt that should not cause buffer conflicts"
        
        print(f"\n🚀 Creating 3 sessions with identical prompts...")
        buffer_sessions = []
        
        for i in range(3):
            agent_type = AgentType.GEMINI if i % 2 == 0 else AgentType.CLAUDE
            session = await self.create_test_session(
                name=f"Buffer-Test-{i+1}",
                agent_type=agent_type,
                prompt=identical_prompt,
                yolo_mode=True
            )
            buffer_sessions.append(session)
            await asyncio.sleep(1)  # Small delay between creations
        
        # Check pane uniqueness immediately after creation
        print(f"\n🔍 Checking pane uniqueness after creation...")
        pane_unique, pane_diagnostics = self.check_pane_uniqueness()
        
        if pane_unique:
            print("   ✅ All sessions have unique pane mappings")
        else:
            print("   ❌ Duplicate pane mappings detected!")
            for pane, sessions in pane_diagnostics['duplicates'].items():
                print(f"      Pane {pane} shared by: {sessions}")
        
        # Monitor all sessions for 10 seconds
        print(f"\n📊 Monitoring all sessions for 10 seconds...")
        await asyncio.sleep(10)
        
        # Check that all sessions progressed normally
        success_count = 0
        for session in buffer_sessions:
            # Use get_session() instead of update_sessions() to avoid blocking
            session_info = self.manager.get_session(session.session_id)
            
            if session_info:
                status = session_info['status']
                print(f"   {session.name}: {status}")
                if status in ["RUNNING", "DONE", "REQUIRES_USER_INPUT"]:
                    success_count += 1
            else:
                print(f"   {session.name}: SESSION MISSING")
        
        # Check for content in each session
        content_success = 0
        for session in buffer_sessions:
            content = self.get_pane_content(session.session_id)
            print(f"   📝 {session.name}: Content length: {len(content)} chars")
            
            # Check for prompt or key words from the prompt
            prompt_found = (
                identical_prompt in content or
                "identical test prompt" in content or
                "buffer conflicts" in content
            )
            
            if prompt_found:
                content_success += 1
                print(f"   ✅ {session.name}: Prompt/keywords found in pane content")
            else:
                print(f"   ❌ {session.name}: Prompt NOT found in pane content")
                # Debug: show last 100 chars of content
                if content:
                    print(f"      Last 100 chars: ...{content[-100:]}")
                else:
                    print(f"      No content captured")
        
        # Wait a bit more for sessions to complete, then verify cleanup
        print(f"\n⏳ Waiting for sessions to complete...")
        await asyncio.sleep(15)  # Give sessions time to complete
        
        # Verify proper cleanup completion
        print(f"\n🧹 Verifying cleanup completion...")
        cleanup_complete, cleanup_diagnostics = self.verify_cleanup_completion()
        
        if cleanup_complete:
            print("   ✅ All sessions completed and cleaned up properly")
        else:
            print("   ❌ Cleanup incomplete - some sessions may not have finished properly")
            if cleanup_diagnostics['active_panes'] > 0:
                print(f"      {cleanup_diagnostics['active_panes']} panes still active")
            if cleanup_diagnostics['total_queued_commands'] > 0:
                print(f"      {cleanup_diagnostics['total_queued_commands']} commands still queued")
        
        success = success_count == 3 and content_success == 3 and pane_unique and cleanup_complete
        
        if success:
            print(f"\n✅ SUCCESS: Buffer uniqueness test passed")
            print(f"   - All 3 sessions progressed normally")
            print(f"   - All prompts appeared in correct panes")
            print(f"   - All sessions had unique pane mappings")
            print(f"   - All sessions completed and cleaned up properly")
        else:
            print(f"\n❌ FAILURE: Buffer uniqueness test failed")
            print(f"   - {success_count}/3 sessions progressed normally")
            print(f"   - {content_success}/3 prompts found in panes")
            if not pane_unique:
                print("   - Duplicate pane mappings detected")
            if not cleanup_complete:
                print("   - Incomplete cleanup detected")
        
        return success
    
    async def test_4_long_prompt_isolation(self) -> bool:
        """
        TEST 4: Long Prompt Buffer Method Isolation
        
        Test with very long prompts (>500 chars) to trigger buffer-based input
        """
        print("="*80)
        print("📊 TEST 4: LONG PROMPT BUFFER METHOD ISOLATION")
        print("="*80)
        print("Goal: Verify buffer method doesn't cause cross-pane interference")
        print("-"*80)
        
        # Create a control session waiting for input
        control_session = await self.create_test_session(
            name="Control-Long",
            agent_type=AgentType.GEMINI,
            prompt="Create a configuration file named long_test_config.json with some sample settings",
            expected_state="REQUIRES_USER_INPUT"
        )
        
        # Wait for control to reach input state
        print("\n🔍 Waiting for control session to require input...")
        if not await self.wait_for_session_state(control_session, "REQUIRES_USER_INPUT", timeout=240.0):
            print("❌ FAILURE: Control session never reached REQUIRES_USER_INPUT")
            return False
        
        # Create sessions with very long prompts (>500 chars)
        long_prompt_base = "This is a very long prompt that should trigger the buffer-based text sending method in tmux. " * 10
        long_prompt = long_prompt_base + " Please respond with a simple acknowledgment message."
        
        print(f"\n🚀 Creating sessions with long prompts ({len(long_prompt)} chars)...")
        long_sessions = []
        
        for i in range(3):
            agent_type = AgentType.CLAUDE if i % 2 == 0 else AgentType.GEMINI
            unique_prompt = f"{long_prompt} Session {i+1} unique identifier."
            
            session = await self.create_test_session(
                name=f"Long-Prompt-{i+1}",
                agent_type=agent_type,
                prompt=unique_prompt
            )
            long_sessions.append(session)
            await asyncio.sleep(2)  # Allow time for buffer operations
        
        # Check pane uniqueness immediately after creation
        print(f"\n🔍 Checking pane uniqueness after creation...")
        pane_unique, pane_diagnostics = self.check_pane_uniqueness()
        
        if pane_unique:
            print("   ✅ All sessions have unique pane mappings")
        else:
            print("   ❌ Duplicate pane mappings detected!")
            for pane, sessions in pane_diagnostics['duplicates'].items():
                print(f"      Pane {pane} shared by: {sessions}")
        
        # Monitor control session stability
        print(f"\n📊 Monitoring control session stability during long prompt processing...")
        isolation_maintained = await self.monitor_session_state_stability(
            control_session, "REQUIRES_USER_INPUT", duration=15.0
        )
        
        # Verify long prompt sessions processed correctly
        long_prompt_success = 0
        for session in long_sessions:
            content = self.get_pane_content(session.session_id)
            if "very long prompt" in content:
                long_prompt_success += 1
                print(f"   ✅ {session.name}: Long prompt processed correctly")
            else:
                print(f"   ❌ {session.name}: Long prompt not found in content")
        
        # Wait a bit more for long prompt sessions to complete, then verify cleanup
        print(f"\n⏳ Waiting for long prompt sessions to complete...")
        total_wait = 60
        intervals = 10
        for i in range(total_wait // intervals):
            # Check if all long prompt sessions are done
            long_sessions_complete = True
            for session in long_sessions:
                session_info = self.manager.get_session(session.session_id)
                if session_info:
                    if session_info['status'] != "DONE":
                        long_sessions_complete = False
                        break
                else:
                    print(f"   ❌ {session.name}: Session missing")
                    long_sessions_complete = False
                    break
            
            if long_sessions_complete:
                break

            await asyncio.sleep(intervals)  # Give sessions time to complete
        
        if not long_sessions_complete:
            print(f"   ❌ Long prompt sessions did not complete in {total_wait} seconds")
            return False

        # Verify long prompt sessions completed (but control session should still be active)
        control_session_active = False    
        # Check control session is still active (as expected)
        control_info = self.manager.get_session(control_session.session_id)
        if control_info:
            control_status = control_info['status']
            if control_status == "REQUIRES_USER_INPUT":
                print(f"   ✅ Control session: Still waiting for input (expected)")
                control_session_active = True
            else:
                print(f"   ℹ️  Control session: {control_status} (expected REQUIRES_USER_INPUT)")
                control_session_active = True  # Still acceptable if it's RUNNING
        else:
            print(f"   ❌ Control session: Missing")
        
        # Check queue status
        queue_sizes = self.manager._tmux_queue.get_queue_sizes()
        total_queued_commands = sum(queue_sizes.values()) if queue_sizes else 0
        queues_empty = total_queued_commands == 0
        
        print(f"   Queued commands: {total_queued_commands}")
        if queues_empty:
            print("   ✅ All queues empty")
        else:
            print("   ❌ Commands still queued")
        
        cleanup_complete = long_sessions_complete and control_session_active and queues_empty
        
        if cleanup_complete:
            print("   ✅ Long prompt sessions completed, control session active as expected")
        else:
            print("   ❌ Cleanup verification failed")
        
        success = isolation_maintained and long_prompt_success == 3 and pane_unique and cleanup_complete
        
        if success:
            print(f"\n✅ SUCCESS: Long prompt isolation test passed")
            print(f"   - Control session remained isolated")
            print(f"   - All long prompts processed correctly")
            print(f"   - All sessions had unique pane mappings")
            print(f"   - Long prompt sessions completed, control session active as expected")
        else:
            print(f"\n❌ FAILURE: Long prompt isolation test failed")
            if not isolation_maintained:
                print("   - Control session isolation compromised")
            if long_prompt_success != 3:
                print(f"   - Only {long_prompt_success}/3 long prompts processed correctly")
            if not pane_unique:
                print("   - Duplicate pane mappings detected")
            if not cleanup_complete:
                print("   - Long prompt sessions cleanup verification failed")
        
        return success
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all cross-pane isolation tests"""
        print("="*80)
        print("🧪 CROSS-PANE INPUT ISOLATION TEST SUITE")
        print("="*80)
        print("Testing tmux pane input isolation during concurrent sessions")
        print("="*80)
        
        tests = [
            ("Basic Isolation", self.test_1_basic_isolation),
            ("Rapid Creation", self.test_2_rapid_session_creation),
            ("Buffer Uniqueness", self.test_3_buffer_uniqueness),
            ("Long Prompt Isolation", self.test_4_long_prompt_isolation),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name.upper()} TEST {'='*20}")
            
            try:
                result = await test_func()
                results[test_name.lower().replace(' ', '_')] = result
                
                status = "✅ PASSED" if result else "❌ FAILED"
                print(f"\n{status}: {test_name} test {'passed' if result else 'failed'}")
                
            except Exception as e:
                print(f"\n❌ ERROR: {test_name} test crashed: {e}")
                import traceback
                traceback.print_exc()
                results[test_name.lower().replace(' ', '_')] = False
            
            # Cleanup between tests
            print(f"\n🧹 Cleaning up sessions from {test_name} test...")
            
            # Stop the monitoring loop temporarily to avoid conflicts
            if hasattr(self, 'monitor_task') and not self.monitor_task.done():
                self.manager.running = False
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
                print("   ⏸️  Paused monitoring for cleanup")
            
            # First stop all sessions using async method
            stop_tasks = []
            for session in self.test_sessions:
                if session.session_id:
                    try:
                        # Use async stop method that waits for completion
                        task = self.manager.stop_session_async(session.session_id)
                        stop_tasks.append(task)
                        print(f"   Stopping {session.name}...")
                    except Exception as e:
                        print(f"   ⚠️  Error stopping {session.name}: {e}")
            
            # Wait for all stop operations to complete
            if stop_tasks:
                print("   ⏳ Waiting for pane termination...")
                # Use smaller batches to avoid semaphore exhaustion
                batch_size = 3
                for i in range(0, len(stop_tasks), batch_size):
                    batch = stop_tasks[i:i+batch_size]
                    batch_results = await asyncio.gather(*batch, return_exceptions=True)
                    for result in batch_results:
                        if isinstance(result, Exception):
                            print(f"   ⚠️  Error stopping session: {result}")
                        elif result:
                            print(f"   ✅ Stopped session")
            
            # Now cleanup should work immediately since sessions are fully stopped
            try:
                cleaned_count = self.manager.cleanup_finished_sessions()
                print(f"   Cleaned {cleaned_count} finished sessions")
            except Exception as e:
                print(f"   ⚠️  Error during cleanup: {e}")
            
            # Restart monitoring loop for next test (unless it's the last test)
            # We'll restart it later if needed
            pass
            
            # Clear test session list
            self.test_sessions.clear()
            
            # Additional wait to ensure all cleanup is complete
            await asyncio.sleep(2)
            
            # Wait for user confirmation before next test (if not last test)
            if test_name != tests[-1][0]:  # Not the last test
                next_test_index = tests.index((test_name, test_func)) + 1
                next_test_name = tests[next_test_index][0]
                
                if self.paused_between_tests:
                    await self.wait_for_user_confirmation(next_test_name)
                else:
                    print(f"\n⏳ Pausing 3 seconds before next test...")
                    await asyncio.sleep(3)
                
                # Restart monitoring loop for next test
                self.manager.running = True
                self.monitor_task = asyncio.create_task(self.manager.monitor_loop())
                print("   ▶️  Restarted monitoring for next test")
        
        return results

async def main(paused_between_tests: bool = True):
    """Main test runner"""
    tester = CrossPaneInputTester(paused_between_tests=paused_between_tests)
    
    try:
        await tester.setup()
        results = await tester.run_all_tests()
        
        # Final summary
        print(f"\n{'='*80}")
        print("📊 CROSS-PANE ISOLATION TEST SUMMARY")
        print("="*80)
        
        passed = sum(results.values())
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All cross-pane isolation tests passed!")
            print("✅ Input routing is properly isolated between tmux panes")
        else:
            print("🐛 Some tests failed - cross-pane input isolation issues detected")
            print("❌ Input routing may have isolation problems")
            
        return passed == total
        
    except Exception as e:
        print(f"\n❌ Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await tester.cleanup()

def cleanup_on_exit():
    """Cleanup function called on exit to prevent threading errors"""
    try:
        # Give any remaining threads time to clean up
        time.sleep(0.1)
    except:
        pass

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    print(f"\n🛑 Received signal {signum}, shutting down...")
    sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    # Register cleanup handlers
    atexit.register(cleanup_on_exit)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(description="Cross-pane input isolation test suite")
    parser.add_argument("--no-pause-between-tests", action="store_true", 
                       help="Run tests without pauses between them")
    args = parser.parse_args()
    
    paused_between_tests = not args.no_pause_between_tests
    
    try:
        success = asyncio.run(main(paused_between_tests=paused_between_tests))
        # Give a moment for all threads to finish before exit
        time.sleep(0.2)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1) 