#!/usr/bin/env python3
"""
Isolated tests for tmux session management to debug specific issues.
Each test focuses on one aspect and exits early once success/failure is determined.
"""

import asyncio
import subprocess
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tmux_operations_manager import TmuxAgentManager, AgentType

class IsolatedTmuxTester:
    def __init__(self):
        self.manager = TmuxAgentManager(max_sessions=5)
        
    async def setup(self):
        """Setup test environment"""
        print("🔧 Setting up test environment...")
        self.manager.setup_main_session()
        await self.manager.start_queue()
        
        # Start the monitoring loop in the background
        print("🔄 Starting monitoring loop...")
        self.monitor_task = asyncio.create_task(self.manager.monitor_loop())
        await asyncio.sleep(1)
        print("✅ Setup complete\n")
        
    async def cleanup(self):
        """Cleanup test environment"""
        if hasattr(self, 'monitor_task'):
            self.manager.running = False
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        await self.manager.stop_queue()
        
    def get_pane_content(self, session_id: str) -> str:
        """Get raw pane content for a session"""
        pane = self.manager._pane_mapping.get(session_id)
        if not pane:
            return ""
            
        result = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", pane, "-e"],
            capture_output=True,
            text=True
        )
        
        return result.stdout if result.returncode == 0 else ""
        
    async def test_1_prompt_sending(self):
        """
        TEST 1: Verify a prompt is being sent to the pane
        SUCCESS: Prompt text appears in pane content within reasonable time
        FAILURE: Prompt text never appears OR appears multiple times (duplication bug)
        """
        print("="*80)
        print("📊 TEST 1: PROMPT SENDING")
        print("="*80)
        print("Goal: Verify prompt text appears in pane exactly once")
        print("Agent: Gemini (YOLO mode)")
        print("Prompt: 'Hello test prompt'")
        print("-"*80)
        
        test_prompt = "Hello test prompt"
        
        # Create session
        print("🚀 Creating session...")
        session_id = self.manager.create_session(
            prompt=test_prompt,
            agent_type=AgentType.GEMINI,
            yolo_mode=True
        )
        
        if not session_id:
            print("❌ FAILURE: Failed to create session")
            return False
            
        print(f"✅ Session created: {session_id}")
        
        # Monitor pane content for up to 10 seconds
        print("\n🔍 Monitoring pane content...")
        start_time = time.time()
        max_wait = 10.0
        
        prompt_appearances = 0
        last_content = ""
        
        while time.time() - start_time < max_wait:
            content = self.get_pane_content(session_id)
            
            # Count occurrences of our prompt
            current_appearances = content.count(test_prompt)
            
            if current_appearances != prompt_appearances:
                elapsed = time.time() - start_time
                print(f"  T+{elapsed:.1f}s: Prompt appeared {current_appearances} time(s)")
                prompt_appearances = current_appearances
                
                # Show relevant part of content
                lines = content.split('\n')
                relevant_lines = [line for line in lines if test_prompt in line]
                for line in relevant_lines:
                    print(f"    Content: '{line.strip()}'")
                
                # Early success: prompt appears exactly once
                if prompt_appearances == 1:
                    print(f"\n✅ SUCCESS: Prompt sent successfully")
                    print(f"   - Appeared exactly once after {elapsed:.1f}s")
                    print(f"   - No duplication detected")
                    
                    # Cleanup and exit
                    self.manager.stop_session(session_id)
                    return True
                    
                # Early failure: prompt appears multiple times
                elif prompt_appearances > 1:
                    print(f"\n❌ FAILURE: Prompt duplication detected!")
                    print(f"   - Prompt appeared {prompt_appearances} times")
                    print(f"   - This indicates a race condition in text sending")
                    
                    # Show full content for debugging
                    print(f"\n📄 Full pane content:")
                    for i, line in enumerate(lines, 1):
                        print(f"   {i:2d}: {line}")
                    
                    # Cleanup and exit
                    self.manager.stop_session(session_id)
                    return False
            
            await asyncio.sleep(0.5)
        
        # Timeout - prompt never appeared
        final_content = self.get_pane_content(session_id)
        print(f"\n❌ FAILURE: Prompt never appeared within {max_wait}s")
        print(f"📄 Final pane content:")
        for i, line in enumerate(final_content.split('\n'), 1):
            print(f"   {i:2d}: {line}")
            
        # Cleanup and exit
        self.manager.stop_session(session_id)
        return False
        
    async def test_2_prompt_submission(self):
        """
        TEST 2: Verify a prompt is properly submitted (Enter key sent)
        SUCCESS: After prompt appears, ready indicators disappear (indicating Enter was pressed)
        FAILURE: Prompt appears but ready indicators remain (Enter not pressed)
        """
        print("="*80)
        print("📊 TEST 2: PROMPT SUBMISSION")
        print("="*80)
        print("Goal: Verify Enter key is sent after prompt text")
        print("Agent: Gemini (YOLO mode)")
        print("Prompt: 'What is 2+2?'")
        print("-"*80)
        
        test_prompt = "What is 2+2?"
        
        # Create session
        print("🚀 Creating session...")
        session_id = self.manager.create_session(
            prompt=test_prompt,
            agent_type=AgentType.GEMINI,
            yolo_mode=True
        )
        
        if not session_id:
            print("❌ FAILURE: Failed to create session")
            return False
            
        print(f"✅ Session created: {session_id}")
        
        # Get ready indicators for Gemini
        agent_config = self.manager.agent_configs[AgentType.GEMINI]
        ready_indicators = agent_config.ready_indicators
        print(f"📋 Ready indicators to watch: {ready_indicators}")
        
        # Monitor for prompt appearance and submission
        print("\n🔍 Monitoring for prompt sending and submission...")
        start_time = time.time()
        max_wait = 15.0
        
        prompt_seen = False
        prompt_submitted = False
        
        while time.time() - start_time < max_wait:
            content = self.get_pane_content(session_id)
            elapsed = time.time() - start_time
            
            # Check if prompt appeared
            if not prompt_seen and test_prompt in content:
                prompt_seen = True
                print(f"  T+{elapsed:.1f}s: ✅ Prompt appeared in pane")
                
            # If prompt is seen, check for submission (ready indicators gone)
            if prompt_seen and not prompt_submitted:
                ready_indicator_present = any(indicator in content for indicator in ready_indicators)
                
                if not ready_indicator_present:
                    prompt_submitted = True
                    print(f"  T+{elapsed:.1f}s: ✅ Ready indicators gone - prompt submitted!")
                    print(f"\n✅ SUCCESS: Prompt submitted successfully")
                    print(f"   - Prompt appeared at some point")
                    print(f"   - Ready indicators disappeared (Enter was pressed)")
                    
                    # Show evidence
                    print(f"\n📄 Current pane content (last 5 lines):")
                    lines = content.split('\n')
                    for line in lines[-5:]:
                        if line.strip():
                            print(f"   '{line}'")
                    
                    # Cleanup and exit
                    self.manager.stop_session(session_id)
                    return True
                    
                elif elapsed > 5.0:  # Give it some time after prompt appears
                    print(f"  T+{elapsed:.1f}s: ⚠️  Ready indicators still present after prompt")
                    
            await asyncio.sleep(0.5)
        
        # Analyze failure
        final_content = self.get_pane_content(session_id)
        ready_indicator_present = any(indicator in final_content for indicator in ready_indicators)
        
        print(f"\n❌ FAILURE: Prompt submission issue")
        
        if not prompt_seen:
            print(f"   - Prompt never appeared in pane")
        elif ready_indicator_present:
            print(f"   - Prompt appeared but Enter was not pressed")
            print(f"   - Ready indicators still present: {[ind for ind in ready_indicators if ind in final_content]}")
        else:
            print(f"   - Ambiguous state - timeout reached")
            
        print(f"\n📄 Final pane content:")
        for i, line in enumerate(final_content.split('\n'), 1):
            print(f"   {i:2d}: {line}")
            
        # Cleanup and exit
        self.manager.stop_session(session_id)
        return False
        
    async def test_3_session_completion_detection(self):
        """
        TEST 3: Verify we correctly detect when a session is done
        SUCCESS: Session status transitions from RUNNING to DONE when agent finishes
        FAILURE: Session remains in RUNNING state despite agent being done
        """
        print("="*80)
        print("📊 TEST 3: SESSION COMPLETION DETECTION")
        print("="*80)
        print("Goal: Verify session status transitions to DONE when agent finishes")
        print("Agent: Gemini (YOLO mode)")
        print("Prompt: 'Say just the word COMPLETE' (should finish quickly)")
        print("-"*80)
        
        test_prompt = "Say just the word COMPLETE"
        
        # Create session
        print("🚀 Creating session...")
        session_id = self.manager.create_session(
            prompt=test_prompt,
            agent_type=AgentType.GEMINI,
            yolo_mode=True
        )
        
        if not session_id:
            print("❌ FAILURE: Failed to create session")
            return False
            
        print(f"✅ Session created: {session_id}")
        
        # Get ready indicators for completion detection
        agent_config = self.manager.agent_configs[AgentType.GEMINI]
        ready_indicators = agent_config.ready_indicators
        
        # Monitor session status and content
        print("\n🔍 Monitoring session status and completion...")
        start_time = time.time()
        max_wait = 30.0
        
        states_seen = set()
        
        while time.time() - start_time < max_wait:
            # Update sessions to get latest status
            await self.manager.update_sessions()
            session_info = self.manager.get_session(session_id)
            
            if not session_info:
                print("❌ FAILURE: Session disappeared")
                return False
                
            status = session_info['status']
            elapsed = time.time() - start_time
            
            # Track state changes
            if status not in states_seen:
                states_seen.add(status)
                print(f"  T+{elapsed:.1f}s: Status changed to {status}")
                
            # Check if we've reached DONE state
            if status == "DONE":
                print(f"\n✅ SUCCESS: Session completion detected!")
                print(f"   - Status transitioned to DONE after {elapsed:.1f}s")
                print(f"   - States seen: {' -> '.join(states_seen)}")
                
                # Show final content as evidence
                final_content = self.get_pane_content(session_id)
                print(f"\n📄 Final pane content (last 3 lines):")
                lines = [line for line in final_content.split('\n') if line.strip()]
                for line in lines[-3:]:
                    print(f"   '{line}'")
                
                # Cleanup and exit
                self.manager.stop_session(session_id)
                return True
                
            # Check if agent has actually finished but we haven't detected it
            if status == "RUNNING" and elapsed > 10.0:
                content = self.get_pane_content(session_id)
                ready_indicator_present = any(indicator in content for indicator in ready_indicators)
                
                if ready_indicator_present:
                    # Agent is ready again - likely finished
                    print(f"  T+{elapsed:.1f}s: ⚠️  Agent appears ready but status still RUNNING")
                    
                    # Check if response contains what we asked for
                    if "COMPLETE" in content:
                        print(f"  T+{elapsed:.1f}s: ⚠️  Agent provided response but status not updated")
                        
                        # Wait a bit more to see if status updates
                        await asyncio.sleep(3.0)
                        await self.manager.update_sessions()
                        session_info = self.manager.get_session(session_id)
                        
                        if session_info and session_info['status'] == "DONE":
                            elapsed = time.time() - start_time
                            print(f"  T+{elapsed:.1f}s: ✅ Status finally updated to DONE")
                            print(f"\n✅ SUCCESS: Session completion detected (with delay)")
                            print(f"   - Agent finished around T+{elapsed-3:.1f}s")
                            print(f"   - Status updated to DONE at T+{elapsed:.1f}s")
                            
                            # Cleanup and exit
                            self.manager.stop_session(session_id)
                            return True
                        else:
                            print(f"\n❌ FAILURE: Session completion detection broken")
                            print(f"   - Agent finished (ready indicators present, response given)")
                            print(f"   - But status remains: {session_info['status'] if session_info else 'UNKNOWN'}")
                            
                            print(f"\n📄 Pane content showing agent is ready:")
                            for i, line in enumerate(content.split('\n'), 1):
                                print(f"   {i:2d}: {line}")
                            
                            # Cleanup and exit
                            self.manager.stop_session(session_id)
                            return False
            
            await asyncio.sleep(1.0)
        
        # Timeout failure
        final_content = self.get_pane_content(session_id)
        await self.manager.update_sessions()
        session_info = self.manager.get_session(session_id)
        final_status = session_info['status'] if session_info else 'UNKNOWN'
        
        print(f"\n❌ FAILURE: Timeout after {max_wait}s")
        print(f"   - Final status: {final_status}")
        print(f"   - States seen: {' -> '.join(states_seen)}")
        
        print(f"\n📄 Final pane content:")
        for i, line in enumerate(final_content.split('\n'), 1):
            print(f"   {i:2d}: {line}")
            
        # Cleanup and exit
        self.manager.stop_session(session_id)
        return False

async def run_test(test_num: int):
    """Run a specific test"""
    tester = IsolatedTmuxTester()
    
    try:
        await tester.setup()
        
        if test_num == 1:
            print("Running Test 1: Prompt Sending\n")
            result = await tester.test_1_prompt_sending()
        elif test_num == 2:
            print("Running Test 2: Prompt Submission\n")
            result = await tester.test_2_prompt_submission()
        elif test_num == 3:
            print("Running Test 3: Session Completion Detection\n")
            result = await tester.test_3_session_completion_detection()
        else:
            print(f"Invalid test number: {test_num}")
            return False
            
        print(f"\n{'✅ PASS' if result else '❌ FAIL'}: Test {test_num} {'passed' if result else 'failed'}")
        return result
        
    except Exception as e:
        print(f"\n❌ ERROR: Test {test_num} crashed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await tester.cleanup()

async def run_all_tests():
    """Run all tests in sequence"""
    print("="*80)
    print("🧪 ISOLATED TMUX SESSION TESTS")
    print("="*80)
    print("Running focused tests to identify specific issues:")
    print("1. Prompt Sending - Does text appear in pane?")
    print("2. Prompt Submission - Is Enter key sent after text?")
    print("3. Session Completion - Do we detect when agent finishes?")
    print("="*80)
    
    results = []
    
    for test_num in [1, 2, 3]:
        print(f"\n{'='*20} TEST {test_num} {'='*20}")
        result = await run_test(test_num)
        results.append(result)
        
        # Small delay between tests
        if test_num < 3:
            print("\n⏳ Pausing 2 seconds before next test...")
            await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result else "❌ FAIL"
        test_names = ["Prompt Sending", "Prompt Submission", "Session Completion"]
        print(f"Test {i} ({test_names[i-1]}): {status}")
    
    passed = sum(results)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed - no issues detected!")
    else:
        print("🐛 Some tests failed - issues detected in tmux session management")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run isolated tmux session tests")
    parser.add_argument("test", nargs="?", type=int, choices=[1, 2, 3], 
                       help="Run specific test (1=sending, 2=submission, 3=completion)")
    args = parser.parse_args()
    
    if args.test:
        asyncio.run(run_test(args.test))
    else:
        asyncio.run(run_all_tests())

if __name__ == "__main__":
    main() 