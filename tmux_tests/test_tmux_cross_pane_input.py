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
    def __init__(self):
        self.manager = TmuxAgentManager(max_sessions=20)
        self.test_sessions: List[TestSession] = []
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
        
        # Start monitoring loop
        print("🔄 Starting monitoring loop...")
        self.monitor_task = asyncio.create_task(self.manager.monitor_loop())
        await asyncio.sleep(1)
        print("✅ Setup complete\n")
        
    async def cleanup(self):
        """Cleanup test environment"""
        print("\n🧹 Cleaning up test sessions...")
        
        # Stop all test sessions
        for test_session in self.test_sessions:
            if test_session.session_id:
                self.manager.stop_session(test_session.session_id)
                print(f"   Stopped {test_session.name}")
        
        # Cleanup finished sessions
        cleaned_count = self.manager.cleanup_finished_sessions()
        print(f"   Cleaned {cleaned_count} finished sessions")
        
        # Stop monitoring and queue
        if hasattr(self, 'monitor_task'):
            self.manager.running = False
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        await self.manager.stop_queue()
        print("✅ Cleanup complete")
        
    def get_pane_content(self, session_id: str) -> str:
        """Get raw pane content for a session"""
        with self.manager._state_lock:
            pane = self.manager._pane_mapping.get(session_id)
        
        if not pane:
            return ""
            
        result = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", pane, "-e"],
            capture_output=True,
            text=True
        )
        
        return result.stdout if result.returncode == 0 else ""
    
    async def create_test_session(self, name: str, agent_type: AgentType, prompt: str, 
                                expected_state: str = "RUNNING") -> TestSession:
        """Create a test session and track it"""
        print(f"   Creating {name} ({agent_type.value}): '{prompt[:50]}...'")
        
        session_id = await asyncio.to_thread(
            self.manager.create_session,
            prompt=prompt,
            agent_type=agent_type,
            yolo_mode=False  # Use regular mode to trigger user input prompts
        )
        
        test_session = TestSession(
            name=name,
            session_id=session_id,
            agent_type=agent_type,
            prompt=prompt,
            expected_state=expected_state,
            created_at=time.time()
        )
        
        # Get pane mapping
        with self.manager._state_lock:
            test_session.pane_id = self.manager._pane_mapping.get(session_id)
        
        self.test_sessions.append(test_session)
        print(f"   ✅ {name} created: {session_id} (pane: {test_session.pane_id})")
        return test_session
    
    async def wait_for_session_state(self, test_session: TestSession, target_state: str, 
                                   timeout: float = 30.0) -> bool:
        """Wait for a session to reach a specific state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            await self.manager.update_sessions()
            session_info = self.manager.get_session(test_session.session_id)
            
            if not session_info:
                print(f"   ❌ {test_session.name}: Session disappeared")
                return False
                
            current_state = session_info['status']
            if current_state == target_state:
                elapsed = time.time() - start_time
                print(f"   ✅ {test_session.name}: Reached {target_state} after {elapsed:.1f}s")
                return True
            
            await asyncio.sleep(0.5)
        
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
        
        while time.time() - start_time < duration:
            await self.manager.update_sessions()
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
            
            await asyncio.sleep(0.5)
        
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
        with self.manager._state_lock:
            for test_session in self.test_sessions:
                if test_session.session_id:
                    pane = self.manager._pane_mapping.get(test_session.session_id)
                    diagnostics['pane_mappings'][test_session.name] = pane
        
        return diagnostics
    
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
        session_a = await self.create_test_session(
            name="Session-A-Input",
            agent_type=AgentType.GEMINI,
            prompt="Create a file called test_isolation.py with a simple hello world function",
            expected_state="REQUIRES_USER_INPUT"
        )
        
        # Step 2: Wait for Session A to reach REQUIRES_USER_INPUT
        print("\n🔍 Waiting for Session A to require user input...")
        if not await self.wait_for_session_state(session_a, "REQUIRES_USER_INPUT", timeout=45.0):
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
            prompt="Create a new Python file named rapid_test.py with a main function",
            expected_state="REQUIRES_USER_INPUT"
        )
        
        # Wait for control session to reach input state
        print("\n🔍 Waiting for control session to require input...")
        if not await self.wait_for_session_state(control_session, "REQUIRES_USER_INPUT", timeout=45.0):
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
                prompt=prompt
            )
            rapid_sessions.append(session)
            
            # Small delay to simulate rapid but not simultaneous creation
            await asyncio.sleep(0.3)
        
        creation_time = time.time() - start_time
        print(f"   ✅ Created 5 sessions in {creation_time:.1f}s")
        
        # Monitor control session stability during rapid creation aftermath
        print(f"\n📊 Monitoring control session stability for 10 seconds...")
        isolation_maintained = await self.monitor_session_state_stability(
            control_session, "REQUIRES_USER_INPUT", duration=10.0
        )
        
        # Check queue diagnostics
        diagnostics = self.get_queue_diagnostics()
        print(f"\n📈 Queue Diagnostics after rapid creation:")
        print(f"   Queue sizes: {diagnostics['queue_sizes']}")
        print(f"   Total sessions: {diagnostics['active_sessions']}")
        
        # Verify all sessions have unique pane mappings
        pane_mappings = diagnostics['pane_mappings']
        unique_panes = set(pane_mappings.values())
        mapping_unique = len(pane_mappings) == len(unique_panes)
        
        if mapping_unique:
            print("   ✅ All sessions have unique pane mappings")
        else:
            print("   ❌ Duplicate pane mappings detected!")
            for name, pane in pane_mappings.items():
                duplicates = [n for n, p in pane_mappings.items() if p == pane and n != name]
                if duplicates:
                    print(f"      {name} shares pane {pane} with {duplicates}")
        
        success = isolation_maintained and mapping_unique
        
        if success:
            print(f"\n✅ SUCCESS: Rapid creation test passed")
        else:
            print(f"\n❌ FAILURE: Rapid creation test failed")
        
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
                prompt=identical_prompt
            )
            buffer_sessions.append(session)
            await asyncio.sleep(1)  # Small delay between creations
        
        # Monitor all sessions for 10 seconds
        print(f"\n📊 Monitoring all sessions for 10 seconds...")
        await asyncio.sleep(10)
        
        # Check that all sessions progressed normally
        success_count = 0
        for session in buffer_sessions:
            await self.manager.update_sessions()
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
            if identical_prompt in content:
                content_success += 1
                print(f"   ✅ {session.name}: Prompt found in pane content")
            else:
                print(f"   ❌ {session.name}: Prompt NOT found in pane content")
        
        success = success_count == 3 and content_success == 3
        
        if success:
            print(f"\n✅ SUCCESS: Buffer uniqueness test passed")
            print(f"   - All 3 sessions progressed normally")
            print(f"   - All prompts appeared in correct panes")
        else:
            print(f"\n❌ FAILURE: Buffer uniqueness test failed")
            print(f"   - {success_count}/3 sessions progressed normally")
            print(f"   - {content_success}/3 prompts found in panes")
        
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
        if not await self.wait_for_session_state(control_session, "REQUIRES_USER_INPUT", timeout=45.0):
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
        
        success = isolation_maintained and long_prompt_success == 3
        
        if success:
            print(f"\n✅ SUCCESS: Long prompt isolation test passed")
            print(f"   - Control session remained isolated")
            print(f"   - All long prompts processed correctly")
        else:
            print(f"\n❌ FAILURE: Long prompt isolation test failed")
            if not isolation_maintained:
                print("   - Control session isolation compromised")
            if long_prompt_success != 3:
                print(f"   - Only {long_prompt_success}/3 long prompts processed correctly")
        
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
            for session in self.test_sessions:
                if session.session_id:
                    self.manager.stop_session(session.session_id)
            self.test_sessions.clear()
            
            # Wait for cleanup
            await asyncio.sleep(2)
            self.manager.cleanup_finished_sessions()
            
            if test_name != tests[-1][0]:  # Not the last test
                print(f"\n⏳ Pausing 3 seconds before next test...")
                await asyncio.sleep(3)
        
        return results

async def main():
    """Main test runner"""
    tester = CrossPaneInputTester()
    
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

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 