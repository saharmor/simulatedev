import asyncio
from typing import List
from .base_cli_agent import BaseCliAgent
from .models import AgentConfig

class GeminiCliAgent(BaseCliAgent):
    """Gemini CLI agent implementation"""
    
    def parse_output(self, text: str) -> str:
        """Gemini outputs plain text, just clean it"""
        return self.clean_terminal_output(text)
    
    def get_yolo_command_modification(self, base_command: List[str]) -> List[str]:
        """Gemini doesn't modify command for YOLO, uses Ctrl+Y after startup"""
        return base_command
    
    async def apply_yolo_mode(self, pane: str, run_command_func) -> bool:
        """Send Ctrl+Y to enable YOLO mode in Gemini"""
        try:
            self.logger.info(f"Applying YOLO mode to Gemini in pane {pane}")
            run_command_func(["tmux", "send-keys", "-t", pane, "C-y"])
            await asyncio.sleep(1.5)  # Wait for YOLO toggle
            return True
        except Exception as e:
            self.logger.error(f"Failed to apply YOLO mode: {e}")
            return False 