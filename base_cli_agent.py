from abc import ABC, abstractmethod
from typing import List
import re
import logging
from .models import AgentConfig
from .enums import ReadyIndicatorMode

class BaseCliAgent(ABC):
    """Base class for CLI agents with common functionality"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    @abstractmethod
    def parse_output(self, text: str) -> str:
        """Parse agent-specific output format"""
        pass
    
    @abstractmethod
    def get_yolo_command_modification(self, base_command: List[str]) -> List[str]:
        """Modify command for YOLO mode if supported"""
        pass
    
    @abstractmethod
    async def apply_yolo_mode(self, pane: str, run_command_func) -> bool:
        """Apply YOLO mode after agent startup if needed"""
        pass
    
    def clean_terminal_output(self, text: str) -> str:
        """Clean terminal output by removing ANSI escape codes"""
        if not text:
            return ""
            
        # Comprehensive ANSI escape code removal
        ansi_escape = re.compile(r'''
            \x1B  # ESC
            (?:   # 7-bit C1 Fe
                [@-Z\\-_]
            |     # or [ for CSI
                \[
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        ''', re.VERBOSE)
        
        # Remove various terminal sequences
        text = ansi_escape.sub('', text)
        text = re.sub(r'\x1b\[[0-9;]*[mGKHJF]', '', text)
        text = re.sub(r'\x1b\[[\?0-9]*[hl]', '', text)
        text = re.sub(r'\x07|\r', '', text)
        
        # Keep only printable characters plus newline/tab
        text = ''.join(c for c in text if c.isprintable() or c in '\n\t' or ord(c) >= 0x2500)
        
        return text
    
    def check_ready_indicators(self, output: str) -> bool:
        """Check if agent is ready based on indicators and mode"""
        if self.config.ready_indicator_mode == ReadyIndicatorMode.INCLUSIVE:
            return any(indicator in output for indicator in self.config.ready_indicators)
        else:  # EXCLUSIVE
            return not any(indicator in output for indicator in self.config.ready_indicators)
    
    def check_input_required(self, output: str) -> bool:
        """Check if agent requires user input"""
        return any(indicator in output for indicator in self.config.input_indicators)
    
    def check_busy(self, output: str) -> bool:
        """Check if agent is still busy"""
        return any(indicator in output for indicator in self.config.busy_indicators) 