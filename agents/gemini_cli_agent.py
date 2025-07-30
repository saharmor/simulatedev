#!/usr/bin/env python3
"""
Gemini CLI Agent Implementation
==============================
CLI-based Gemini agent that runs in tmux sessions through the backend.
"""

from typing import Optional
from .base import CLIAgent, CLIAgentConfig, AgentResponse
from common.tmux_types import ReadyIndicatorMode


class GeminiCliAgent(CLIAgent):
    """Gemini CLI coding agent implementation using tmux backend service"""
    
    @classmethod
    def get_config(cls) -> CLIAgentConfig:
        """Get Gemini CLI configuration"""
        return CLIAgentConfig(
            command=["gemini", "2>&1"],
            supports_yolo=True,
            pre_commands=[
                "export GEMINI_API_KEY=\"${GEMINI_API_KEY}\"",
            ],
            ready_indicators=["Type your message or @path/to/file"],
            ready_indicator_mode=ReadyIndicatorMode.INCLUSIVE  # Ready when indicators ARE present
        )
    
    @property
    def window_name(self) -> str:
        return "Gemini CLI"
    
    async def open_coding_interface(self) -> bool:
        """Start Gemini CLI with YOLO mode"""
        # First check if the session is already created
        if not await super().open_coding_interface():
            return False
        
        # Enable YOLO mode by sending Ctrl+Y after agent starts
        try:
            import asyncio
            await asyncio.sleep(2)  # Wait for agent to fully initialize
            
            # Send Ctrl+Y for YOLO mode
            if self._tmux_service and self._session_id:
                # Use tmux send-keys with the C-y (Ctrl+Y) key combination
                pane = self._tmux_service._panes.get(self._session_id)
                if pane:
                    cmd = ["tmux", "send-keys", "-t", pane.full_target, "C-y"]
                    await self._tmux_service._tmux_queue.execute(cmd)
                    print(f"SUCCESS: {self.agent_name} started with YOLO mode enabled")
            
            return True
            
        except Exception as e:
            print(f"Warning: Could not enable YOLO mode for {self.agent_name}: {e}")
            return True  # Still return True as basic interface is working
    
    async def is_coding_agent_open_with_project(self) -> bool:
        """Check if Gemini CLI is running with correct project"""
        if not await self.is_coding_agent_open():
            return False
        
        # For CLI agents, we check if the session has the right working directory
        if not self._current_project_name:
            return True  # If no specific project set, consider it ready
        
        try:
            # Capture current session output
            if self._tmux_service and self._session_id:
                output = await self._tmux_service.capture_session_output(self._session_id)
                # Check if the ready indicator is present and project path appears
                config = self.get_config()
                has_ready_indicator = any(indicator in output for indicator in config.ready_indicators)
                has_project_context = self._current_project_name in output
                return has_ready_indicator and has_project_context
        except Exception as e:
            print(f"Error checking project context for {self.agent_name}: {e}")
            
        return False
    
    async def _wait_for_completion(self, timeout_seconds: int = None):
        """Wait for Gemini CLI to complete using callback mechanism to reduce polling"""
        import asyncio
        from common.config import config
        
        if timeout_seconds is None:
            timeout_seconds = config.agent_timeout_seconds
        
        # Use callback mechanism instead of polling to reduce console spam
        completion_event = asyncio.Event()
        completion_status = None
        
        def completion_callback(session_id: str, status):
            nonlocal completion_status
            completion_status = status
            completion_event.set()
            print(f"{self.agent_name} completed with status: {status}")
        
        # Register callback with tmux service
        if self._tmux_service and self._session_id:
            self._tmux_service.register_completion_callback(self._session_id, completion_callback)
            
            try:
                # Wait for completion or timeout
                await asyncio.wait_for(completion_event.wait(), timeout=timeout_seconds)
                print(f"{self.agent_name} completion detected via callback")
            except asyncio.TimeoutError:
                print(f"Warning: {self.agent_name} completion monitoring timed out after {timeout_seconds} seconds")
                # Fall back to heuristic completion after timeout
                pass
        else:
            print(f"Warning: No tmux service available for {self.agent_name}, using fallback delay")
            await asyncio.sleep(10)  # Fallback delay
 