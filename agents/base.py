#!/usr/bin/env python3
"""
Base classes and shared components for coding agents.
"""

import time
import pyautogui
import pyperclip
import os
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from common.config import config


class CodingAgentIdeType(Enum):
    """Enum for supported coding agents"""
    CURSOR = "cursor"
    WINDSURF = "windsurf"
    CLAUDE_CODE = "claude_code"
    TEST = "test"


class AgentRole(Enum):
    """Enum for agent roles in multi-agent workflows"""
    PLANNER = "Planner"
    CODER = "Coder"
    TESTER = "Tester"


class WorkflowType(Enum):
    """Enum for available workflow types"""
    CUSTOM_CODING = "custom_coding"
    BUG_HUNTING = "bug_hunting"
    CODE_OPTIMIZATION = "code_optimization"


@dataclass
class MultiAgentTask:
    """Definition of a task for multi-agent execution"""
    agents: List['AgentDefinition']
    repo_url: Optional[str] = None
    workflow: Optional[WorkflowType] = None
    coding_task_prompt: Optional[str] = None  # Required only for custom_coding workflow
    
    def __post_init__(self):
        """Validate the task after initialization"""
        self._validate_unique_roles()
        self._validate_workflow_requirements()
    
    def _validate_unique_roles(self):
        """Ensure each role appears only once"""
        used_roles = set()
        for i, agent in enumerate(self.agents):
            if agent.role in used_roles:
                raise ValueError(f"Duplicate role '{agent.role.value}' found at agent {i}. Each role can only be assigned to one agent.")
            used_roles.add(agent.role)
    
    def _validate_workflow_requirements(self):
        """Validate workflow-specific requirements"""
        # Only validate if workflow is set - it might be overridden by command-line args later
        if self.workflow == WorkflowType.CUSTOM_CODING and not self.coding_task_prompt:
            raise ValueError("'coding_task_prompt' field is required when using 'custom_coding' workflow")
        if self.workflow and self.workflow != WorkflowType.CUSTOM_CODING and self.coding_task_prompt:
            # This is just a warning case - allow it but note it's unusual
            pass
    
    def get_task_description(self) -> str:
        """Get the task description based on workflow type"""
        if self.workflow == WorkflowType.CUSTOM_CODING:
            return self.coding_task_prompt or "Custom coding task"
        elif self.workflow == WorkflowType.BUG_HUNTING:
            return "Find and fix security vulnerabilities and bugs"
        elif self.workflow == WorkflowType.CODE_OPTIMIZATION:
            return "Optimize performance and improve code quality"
        else:
            return "Multi-agent collaborative task"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "agents": [agent.to_dict() for agent in self.agents]
        }
        if self.repo_url:
            result["repo_url"] = self.repo_url
        if self.workflow:
            result["workflow"] = self.workflow.value
        if self.coding_task_prompt:
            result["coding_task_prompt"] = self.coding_task_prompt
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultiAgentTask':
        """Create from dictionary (JSON deserialization)"""
        agents = [AgentDefinition.from_dict(agent_data) for agent_data in data["agents"]]
        
        # repo_url and workflow are now optional in JSON
        repo_url = data.get("repo_url")
        workflow = data.get("workflow")
        
        # Convert workflow string to enum if provided
        if workflow:
            try:
                workflow = WorkflowType(workflow)
            except ValueError:
                raise ValueError(f"Invalid workflow type: {workflow}. Valid types: {[w.value for w in WorkflowType]}")
        
        # Handle backward compatibility with old 'task' and 'prompt' fields
        coding_task_prompt = data.get("coding_task_prompt")
        if not coding_task_prompt:
            # Check for old field names
            coding_task_prompt = data.get("prompt") or data.get("task")
        
        return cls(
            agents=agents,
            repo_url=repo_url,
            workflow=workflow,
            coding_task_prompt=coding_task_prompt
        )


@dataclass
class AgentDefinition:
    """Definition of an agent with its role and model"""
    coding_ide: str
    model: str
    role: AgentRole
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "coding_ide": self.coding_ide,
            "model": self.model,
            "role": self.role.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentDefinition':
        """Create from dictionary (JSON deserialization)"""
        # Support both old "name" and new "coding_ide" for backward compatibility
        coding_ide = data.get("coding_ide") or data.get("name")
        if not coding_ide:
            raise ValueError("Missing required field: 'coding_ide' (or legacy 'name')")
        
        return cls(
            coding_ide=coding_ide,
            model=data["model"],
            role=AgentRole(data["role"])
        )


@dataclass
class AgentContext:
    """Context passed between agents in multi-agent workflows"""
    task_description: str
    previous_outputs: List[Dict[str, Any]]
    current_step: int
    total_steps: int
    work_directory: str
    
    def add_agent_output(self, coding_ide: str, role: AgentRole, output: str, success: bool):
        """Add output from an agent to the context"""
        self.previous_outputs.append({
            "coding_ide": coding_ide,
            "role": role.value,
            "output": output,
            "success": success,
            "step": self.current_step
        })
    
    def get_outputs_by_role(self, role: AgentRole) -> List[Dict[str, Any]]:
        """Get all outputs from agents with a specific role"""
        return [output for output in self.previous_outputs if output["role"] == role.value]
    
    def get_latest_output_by_role(self, role: AgentRole) -> Optional[Dict[str, Any]]:
        """Get the most recent output from an agent with a specific role"""
        outputs = self.get_outputs_by_role(role)
        return outputs[-1] if outputs else None


@dataclass
class AgentResponse:
    """Response from an AI coding agent"""
    content: str
    success: bool
    error_message: Optional[str] = None


@dataclass
class MultiAgentResponse:
    """Response from multi-agent execution"""
    success: bool
    final_output: str
    execution_log: List[Dict[str, Any]]
    test_results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    pr_url: Optional[str] = None

class CodingAgent(ABC):
    """Abstract base class for AI coding agents"""
    
    def __init__(self, computer_use_client):
        self.computer_use_client = computer_use_client
        self.agent_name = self.__class__.__name__.lower().replace('agent', '')
        self.output_file = "agent_execution_output.md"
        self._current_project_name = None  # Track current project
    
    @property
    @abstractmethod
    def window_name(self) -> str:
        """The application window name for opening the IDE"""
        pass
    
    @property
    @abstractmethod
    def interface_state_prompt(self) -> str:
        """Prompt for analyzing the agent's interface state"""
        pass
    
    @property
    @abstractmethod
    def resume_button_prompt(self) -> str:
        """Prompt for finding the resume button coordinates"""
        pass
    
    @property
    @abstractmethod
    def input_field_prompt(self) -> str:
        """Prompt for finding the input field coordinates"""
        pass
    
    @property
    def keyboard_shortcut(self) -> Optional[str]:
        """Optional keyboard shortcut to open the agent interface"""
        return None
    
    def set_current_project(self, project_path: str):
        """Set the current project name for window title checking"""
        self._current_project_name = os.path.basename(project_path)
    
    def is_ide_open_with_correct_project(self) -> bool:
        """Check if the IDE is open with the correct project by checking window titles"""
        if not self._current_project_name:
            print(f"Warning: No project name set for {self.agent_name}, cannot verify project-specific window")
            return False
            
        from utils.computer_use_utils import is_ide_open_with_project
        return is_ide_open_with_project(self.window_name, self._current_project_name, verbose=False)
    
    async def is_coding_agent_open(self) -> bool:
        """Check if the agent is currently running and ready to accept commands
        
        Check if the agent is open and has the correct project loaded.
        
        Returns:
            bool: True if the agent is running and ready, False otherwise
        """
        try:
            if not self._current_project_name or not self.is_ide_open_with_correct_project():
                return False
            
            return True
        except Exception as e:
            print(f"INFO: Could not detect {self.agent_name} interface: {str(e)}")
            return False
    
    async def is_coding_agent_open_with_project(self) -> bool:
        """Check if the agent is open AND has the correct project loaded
        
        This combines interface checking with project verification.
        
        Returns:
            bool: True if the agent is running with the correct project, False otherwise
        """
        # First check if the basic interface is open
        if not await self.is_coding_agent_open():
            return False
            
        # Then check if it has the correct project
        if not self.is_ide_open_with_correct_project():
            print(f"{self.agent_name} interface is open but not with the correct project '{self._current_project_name}'")
            return False
            
        return True
    
    @abstractmethod
    async def open_coding_interface(self) -> bool:
        """Open the agent's coding interface and ensure it's ready to accept commands
        
        Each agent should implement its own logic for:
        1. Checking if already running (using is_agent_running())
        2. Opening the interface if not running
        3. Handling any setup popups or prompts
        4. Verifying the interface is ready
        
        Returns:
            bool: True if interface is open and ready, False otherwise
        """
        pass
    
    async def close_coding_interface(self) -> bool:
        """Close the agent's coding interface for the current project
        
        This default implementation handles GUI-based IDEs:
        1. Checks if the interface is open with the current project
        2. Closes only the interface/window for the current project
        3. Leaves other projects/windows untouched
        
        Subclasses can override this for different behavior (e.g., headless agents).
        
        Returns:
            bool: True if interface was closed successfully or wasn't open, False on error
        """
        try:
            if not self._current_project_name:
                print(f"WARNING: No project name set for {self.agent_name}, cannot close project-specific window")
                return True  # Return True since we can't identify what to close
            
            # Check if the IDE is open with our project
            if not self.is_ide_open_with_correct_project():
                return True # Nothing to close
            
            # Use utility function to close the specific IDE window
            from utils.computer_use_utils import close_ide_window_for_project
            close_success = close_ide_window_for_project(self.window_name, self._current_project_name)
            
            if close_success:
                # Wait a moment for the window to close
                time.sleep(1)
                
                # Verify the window was closed
                if not self.is_ide_open_with_correct_project():
                    return True # Window was closed
                else:
                    return False # Window was not closed
            else:
                return False
                
        except Exception as e:
            print(f"ERROR: Failed to close {self.agent_name} interface: {str(e)}")
            return False
    
    async def get_input_field_coordinates(self):
        """Get the coordinates of the input field using full screen screenshot with window context"""
        result = await self.computer_use_client.get_coordinates_from_vision_model(
            self.input_field_prompt,
            ide_name=self.window_name,
            project_name=self._current_project_name
        )
        return result
    
    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute the complete workflow: send prompt -> wait -> save to file -> return content
        
        This is the main method that orchestrates the entire agent interaction.
        """
        try:
            # Step 1: Send the prompt
            print(f"Sending prompt to {self.agent_name}...")
            await self._send_prompt_to_interface(prompt)
            # wait for 5 seconds to make sure the prompt is sent
            time.sleep(5)

            # Step 2: Wait for completion
            print(f"Waiting for {self.agent_name} to complete...")
            await self._wait_for_completion()
            
            # Step 3: Ask agent to save output
            print(f"Asking {self.agent_name} to save output to {self.output_file}...")
            save_prompt = f"""Save a summary of everything you did to a file called '{self.output_file}' in the current directory. Include:\n- All changes made\n- Explanations of what was done.\n\nIMPORTANT: Do NOT create or update any documentation files (such as README.md or docs/*) unless you are explicitly asked to do so in the original prompt. If you believe that creating a documentation file would help you better implement the required coding task, you may create it, but you must delete it once you are finished and before you finish the task."""
            
            # Ensure the window is focused before sending the save prompt
            if self._current_project_name:
                from utils.computer_use_utils import bring_to_front_window
                bring_to_front_window(self.agent_name, self._current_project_name)
            
            await self._send_prompt_to_interface(save_prompt)
            time.sleep(3)

            # Wait a bit for file save operation (use shorter timeout for file save)
            await self._wait_for_completion(timeout_seconds=240)
            
            # Step 4: Read the file
            print(f"Reading output from {self.output_file}...")
            content = await self._read_output_file()
            
            return AgentResponse(content=content, success=True)
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"Failed to execute prompt: {str(e)}"
            )
    
    async def _send_prompt_to_interface(self, prompt: str):
        """Send a prompt to the agent interface (GUI-based implementation)"""
        # Check if the correct project window is visible and focused (with auto-focus enabled)
        if self._current_project_name:
            from utils.computer_use_utils import is_project_window_visible, play_beep_sound
            
            # Use auto_focus=True to automatically bring the window to focus if needed
            if not is_project_window_visible(self.agent_name, self._current_project_name, auto_focus=True):
                print(f"ERROR: Could not bring {self.agent_name} window for project '{self._current_project_name}' to focus. Playing beep.")
                play_beep_sound()
                raise Exception(f"Could not bring {self.agent_name} window for project '{self._current_project_name}' to focus")
        
        # Get input field coordinates (this will now use the focused window screenshot)
        input_coords = await self.get_input_field_coordinates()
        if not input_coords:
            print(f"WARNING: Could not locate {self.agent_name} input field. Playing beep.")
            from utils.computer_use_utils import play_beep_sound
            play_beep_sound()
            raise Exception(f"Could not locate {self.agent_name} input field")
        
        # Click the input field
        print(f"Moving to {self.agent_name} input field...")
        pyautogui.moveTo(input_coords.coordinates.x, input_coords.coordinates.y, duration=0.5)
        time.sleep(0.5)
        pyautogui.click(input_coords.coordinates.x, input_coords.coordinates.y)
        time.sleep(1.0)
        
        # Copy prompt to clipboard and paste it
        pyperclip.copy(prompt)
        time.sleep(0.5)
        
        # Paste the prompt using Cmd+V on macOS
        pyautogui.hotkey('command', 'v')
        time.sleep(1.0)
        
        # Submit the prompt
        pyautogui.press('enter')
        time.sleep(1.0)
    
    async def _wait_for_completion(self, timeout_seconds: int = None):
        """Wait for the agent to complete processing"""
        from utils.ide_completion_detector import wait_until_ide_finishes
        from common.config import config
        
        # Use configured timeout if not explicitly provided
        if not timeout_seconds:
            timeout_seconds = config.agent_timeout_seconds
        
        await wait_until_ide_finishes(
            self.agent_name, 
            self.interface_state_prompt, 
            timeout_seconds, 
            self.resume_button_prompt, 
            require_two_subsequent_done_states=True,
            project_name=self._current_project_name,
            save_screenshots_for_debug=config.save_screenshots_for_debug
        )
    
    async def _read_output_file(self) -> str:
        """Read the output file and return its content"""
        import glob
        
        # First try the current working directory
        file_path = os.path.join(os.getcwd(), self.output_file)
        
        if os.path.exists(file_path):
            found_file = file_path
        else:
            # Search recursively in current directory and subdirectories
            search_pattern = os.path.join(os.getcwd(), "**", self.output_file)
            matching_files = glob.glob(search_pattern, recursive=True)
            
            if matching_files:
                # Use the first match found
                found_file = matching_files[0]
                print(f"Found {self.output_file} at: {found_file}")
            else:
                raise Exception(f"Output file {self.output_file} was not found in current directory or subdirectories")
        
        # Read the file
        with open(found_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # delete the file
        os.remove(found_file)
        print(f"Cleaned up {self.output_file} from {found_file}")
        
        return content 