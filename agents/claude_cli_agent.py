#!/usr/bin/env python3
"""
Claude CLI Agent Implementation
===============================
CLI-based Claude agent that runs in tmux sessions through the backend.
"""

from typing import Optional
from .base import CLIAgent, CLIAgentConfig, AgentResponse
from tmux_operations_manager import ReadyIndicatorMode


class ClaudeCliAgent(CLIAgent):
    """Claude CLI coding agent implementation using tmux backend service"""
    
    @classmethod
    def get_config(cls) -> CLIAgentConfig:
        """Get Claude CLI configuration"""
        return CLIAgentConfig(
            command=["claude", "--permission-mode", "acceptEdits", "2>&1"],
            supports_yolo=True,
            pre_commands=[], 
            ready_indicators=["esc to interrupt"],  # Claude shows this when NOT ready
            ready_indicator_mode=ReadyIndicatorMode.EXCLUSIVE  # Ready when indicators are NOT present
        )
    
    @property
    def window_name(self) -> str:
        return "Claude CLI"
    
    async def open_coding_interface(self) -> bool:
        """Start Claude CLI with acceptEdits mode (YOLO equivalent)"""
        # First check if the session is already created
        if not await super().open_coding_interface():
            return False
        
        # Claude CLI starts with --permission-mode acceptEdits which is similar to YOLO mode
        # No additional setup needed beyond the pre-configured command
        print(f"SUCCESS: {self.agent_name} started with acceptEdits mode (auto-approval)")
        return True
    
    async def is_coding_agent_open_with_project(self) -> bool:
        """Check if Claude CLI is running with correct project"""
        if not await self.is_coding_agent_open():
            return False
        
        # For CLI agents, we check if the session has the right working directory
        if not self._current_project_name:
            return True  # If no specific project set, consider it ready
        
        try:
            # Capture current session output
            if self._tmux_service and self._session_id:
                output = await self._tmux_service.capture_session_output(self._session_id)
                
                # For Claude, we use exclusive mode for ready indicators
                # Claude is ready when "esc to interrupt" is NOT present
                config = self.get_config()
                has_busy_indicators = any(indicator in output for indicator in config.ready_indicators)
                is_ready = not has_busy_indicators  # Ready when busy indicators are absent
                
                has_project_context = self._current_project_name in output
                return is_ready and has_project_context
        except Exception as e:
            print(f"Error checking project context for {self.agent_name}: {e}")
            
        return False
    
    async def _wait_for_completion(self, timeout_seconds: int = None):
        """Wait for Claude CLI to complete via output monitoring"""
        # Claude-specific completion detection based on ready indicators
        import asyncio
        from common.config import config
        
        if not timeout_seconds:
            timeout_seconds = config.agent_timeout_seconds
        
        start_time = asyncio.get_event_loop().time()
        check_interval = 5  # Reduced frequency to minimize console spam
        
        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            try:
                if self._tmux_service and self._session_id:
                    output = await self._tmux_service.capture_session_output(self._session_id)
                    
                    # Claude is done when "esc to interrupt" is NOT present (exclusive mode)
                    agent_config = self.get_config()
                    has_busy_indicators = any(indicator in output for indicator in agent_config.ready_indicators)
                    
                    if not has_busy_indicators:  # Ready when busy indicators are absent
                        print(f"{self.agent_name} appears to have completed")
                        return
                        
            except Exception as e:
                print(f"Error monitoring {self.agent_name} completion: {e}")
            
            await asyncio.sleep(check_interval)
        
        print(f"Warning: {self.agent_name} completion monitoring timed out after {timeout_seconds} seconds")
    
    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute prompt and return response from Claude CLI"""
        try:
            # Send the prompt
            await self._send_prompt_to_interface(prompt)
            
            # Wait for completion with Claude-specific logic
            await self._wait_for_completion()
            
            # Get the output
            output = await self._read_output_file()
            
            return AgentResponse(
                content=output,
                success=True
            )
            
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"Failed to execute prompt: {str(e)}"
            ) 