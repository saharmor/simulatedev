#!/usr/bin/env python3
"""
Web Agent Base Class Implementation

This module provides a base class for web-based coding agents that run in browsers.
Uses the BrowserManager for centralized browser management.
"""

import asyncio
import time
import os
from abc import abstractmethod
from typing import Optional, Dict, Any
from .base import CodingAgent, AgentResponse
from common.exceptions import AgentTimeoutException
from common.config import config
from utils.browser_manager import BrowserManager


class WebAgent(CodingAgent):
    """Base class for web-based coding agents using centralized BrowserManager"""
    
    def __init__(self, computer_use_client):
        super().__init__(computer_use_client)
        self.browser_manager: Optional[BrowserManager] = None
    
    @property
    def window_name(self) -> str:
        """Web agents don't have traditional windows, but we keep this for compatibility"""
        return f"{self.agent_name}_browser"
    
    @property
    @abstractmethod
    def web_url(self) -> str:
        """The URL of the web-based coding agent"""
        pass
    
    @property
    @abstractmethod
    def input_selector(self) -> str:
        """CSS selector for the input field where prompts are entered"""
        pass
    
    @property
    @abstractmethod
    def submit_selector(self) -> str:
        """CSS selector for the submit button"""
        pass
    
    @property
    @abstractmethod
    def output_selector(self) -> str:
        """CSS selector for the output/response area"""
        pass
    
    @property
    @abstractmethod
    def loading_selector(self) -> Optional[str]:
        """CSS selector for loading indicator (optional)"""
        pass
    
    @property
    def interface_state_prompt(self) -> str:
        """Not used for web agents, but kept for compatibility"""
        return ""
    
    @property
    def resume_button_prompt(self) -> str:
        """Not used for web agents, but kept for compatibility"""
        return ""
    
    @property
    def input_field_prompt(self) -> str:
        """Not used for web agents, but kept for compatibility"""
        return ""
    
    def set_current_project(self, project_path: str):
        """Override to handle web agent project context"""
        super().set_current_project(project_path)
        # Web agents might need to navigate to project-specific URLs or set context
        # This can be customized by subclasses
    
    def set_repository_context(self, repo_url: str, original_repo_url: Optional[str] = None):
        """Set repository context for web agents
        
        Args:
            repo_url: The repository URL the agent should work with (may be a fork)
            original_repo_url: The original repository URL (if repo_url is a fork)
        """
        self.repo_url = repo_url
        self.original_repo_url = original_repo_url
    
    def get_working_repo_url(self) -> Optional[str]:
        """Get the repository URL the agent should work with"""
        return getattr(self, 'repo_url', None)
    
    def get_original_repo_url(self) -> Optional[str]:
        """Get the original repository URL (before any forking)"""
        return getattr(self, 'original_repo_url', None)
    
    def is_ide_open_with_correct_project(self) -> bool:
        """Check if browser is open with the correct context"""
        if not self._current_project_name:
            return self.browser_manager and self.browser_manager.is_ready
        
        # For web agents, we consider the project "correct" if the browser is ready
        # and we're on the right URL. Subclasses can override for more specific checks.
        return self.browser_manager and self.browser_manager.is_ready
    
    async def is_coding_agent_open(self) -> bool:
        """Check if the browser is open and ready"""
        try:
            return self.browser_manager and self.browser_manager.is_ready
                
        except Exception as e:
            return False
    
    async def is_coding_agent_open_with_project(self) -> bool:
        """Check if the browser is open and ready with correct project context"""
        if not await self.is_coding_agent_open():
            return False
            
        if not self.is_ide_open_with_correct_project():
            return False
            
        return True
    
    async def open_coding_interface(self) -> bool:
        """Open the web browser and navigate to the coding agent's website"""
        
        try:
            print(f"Opening {self.agent_name} web interface...")
            
            # Initialize browser manager
            self.browser_manager = BrowserManager(
                headless=False,  # Keep visible for debugging, can be made configurable
                auth_file_path=os.getenv('PLAYWRIGHT_AUTH_FILE')
            )
            
            # Initialize browser
            if not await self.browser_manager.initialize():
                print(f"ERROR: Failed to initialize browser manager for {self.agent_name}")
                return False
            
            # Navigate to the web agent URL
            if not await self.browser_manager.navigate_to(self.web_url):
                print(f"ERROR: Failed to navigate to {self.web_url}")
                return False
            
            # Perform any agent-specific setup
            setup_success = await self._setup_web_interface()
            if not setup_success:
                print(f"ERROR: Failed to setup {self.agent_name} web interface")
                return False
            
            print(f"SUCCESS: {self.agent_name} web interface is ready")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to open {self.agent_name} web interface: {str(e)}")
            await self.close_coding_interface()
            return False
    
    async def close_coding_interface(self) -> bool:
        """Close the web browser"""
        try:
            if self.browser_manager:
                await self.browser_manager.cleanup()
                self.browser_manager = None
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to close {self.agent_name} web interface: {str(e)}")
            return False
    

    
    async def _setup_web_interface(self) -> bool:
        """Perform agent-specific setup after navigation. Override in subclasses."""
        # Default implementation - subclasses can override for specific setup
        try:
            if not self.browser_manager:
                return False
            
            # Example: Handle Google login if redirected to Google login page
            # current_url = self.browser_manager.current_url
            # if current_url and 'accounts.google.com' in current_url:
            #     google_email = os.getenv('GOOGLE_EMAIL')
            #     google_password = os.getenv('GOOGLE_PASSWORD')
            #     if google_email and google_password:
            #         await self.browser_manager.handle_google_login(google_email, google_password)
            
            # Solve any captchas that might appear
            await self.browser_manager.solve_captcha_if_present()
            
            # Wait for input field to be available
            if not await self.browser_manager.wait_for_selector(self.input_selector, timeout=10000):
                print(f"ERROR: Could not find input field for {self.agent_name}")
                return False
            
            return True
            
        except Exception as e:
            print(f"ERROR: Setup failed for {self.agent_name}: {str(e)}")
            return False
    
    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute prompt by sending it to the web interface"""
        try:
            if not self.browser_manager or not self.browser_manager.is_ready:
                raise Exception("Browser not ready. Call open_coding_interface() first.")
            
            print(f"Executing task: {prompt[:100]}...")
            
            # Combine prompt with instruction to save output
            combined_prompt = f"""{prompt}\n\nAfter completing the above task, please save a comprehensive summary of everything you did to a file called '{self.output_file}' in the current directory. Include:\n- All changes made\n- Explanations of what was done.\n- If you created a pull request, include the PR URL.\n\nIMPORTANT: Do NOT create or update any documentation files (such as README.md or docs/*) unless you are explicitly asked to do so in the original prompt. If you believe that creating a documentation file would help you better implement the required coding task, you may create it, but you must delete it once you are finished and before you finish the task."""
            
            # Send prompt to web interface
            await self._send_prompt_to_web_interface(combined_prompt)
            
            # Wait for completion
            await self._wait_for_web_completion()
            
            # Try to extract PR URL from the web interface
            pr_url = await self._extract_pr_url_from_interface()
            
            # Read output file
            content = await self._read_output_file()
            
            # If we found a PR URL, add it to the content
            if pr_url and content:
                if "PR created:" not in content and pr_url not in content:
                    content += f"\n\nPR created: {pr_url}"
            
            return AgentResponse(content=content, success=True)
            
        except Exception as e:
            return AgentResponse(
                content="",
                success=False,
                error_message=f"Failed to execute prompt: {str(e)}"
            )
    
    async def _send_prompt_to_web_interface(self, prompt: str):
        """Send prompt to the web interface"""
        try:
            if not self.browser_manager:
                raise Exception("Browser manager not initialized")
            
            # Click on input field
            if not await self.browser_manager.click_element(self.input_selector):
                raise Exception(f"Failed to click input field: {self.input_selector}")
            
            # Fill the prompt
            if not await self.browser_manager.fill_input(self.input_selector, prompt, clear_first=True):
                raise Exception(f"Failed to fill input field: {self.input_selector}")
            
            # Submit the prompt
            if not await self.browser_manager.click_element(self.submit_selector):
                raise Exception(f"Failed to click submit button: {self.submit_selector}")
            
            # Small delay after submission
            await asyncio.sleep(2)
            
        except Exception as e:
            raise Exception(f"Failed to send prompt to web interface: {str(e)}")
    
    async def _wait_for_web_completion(self):
        """Wait for the web agent to complete processing"""
        timeout_seconds = config.agent_timeout_seconds
        start_time = time.time()
        
        try:
            if not self.browser_manager:
                raise Exception("Browser manager not initialized")
            
            while time.time() - start_time < timeout_seconds:
                # Check if loading indicator is present (if defined)
                if self.loading_selector:
                    if await self.browser_manager.wait_for_selector(
                        self.loading_selector, 
                        state="hidden", 
                        timeout=5000
                    ):
                        break
                
                # Check if output area has been updated (basic implementation)
                output_text = await self.browser_manager.get_text_content(
                    self.output_selector, 
                    timeout=5000
                )
                if output_text and len(output_text.strip()) > 100:  # Arbitrary threshold
                    # Wait a bit more to ensure completion
                    await asyncio.sleep(10)
                    break
                
                # Wait before next check
                await asyncio.sleep(5)
            
            if time.time() - start_time >= timeout_seconds:
                raise AgentTimeoutException(self.agent_name, timeout_seconds, "Web agent processing timed out")
                
        except Exception as e:
            if isinstance(e, AgentTimeoutException):
                raise
            else:
                print(f"WARNING: Error waiting for completion, assuming done: {str(e)}")
    
    async def get_web_output(self) -> str:
        """Extract output from the web interface. Override in subclasses for specific parsing."""
        try:
            if not self.browser_manager:
                return ""
            
            # Try to get output from the designated output selector
            output_text = await self.browser_manager.get_text_content(self.output_selector)
            return output_text or ""
            
        except Exception as e:
            print(f"WARNING: Could not extract output from web interface: {str(e)}")
            return ""
    
 

    async def _extract_pr_url_from_interface(self) -> Optional[str]:
        """Extract PR URL from the web interface. Override in subclasses for specific extraction logic."""
        try:
            if not self.browser_manager or not self.browser_manager.page:
                return None
            
            # Generic approach: look for GitHub PR links on the page
            pr_links = await self.browser_manager.page.query_selector_all('a[href*="github.com"][href*="/pull/"]')
            
            for link in pr_links:
                href = await link.get_attribute('href')
                if href and '/pull/' in href and href.startswith('https://github.com/'):
                    print(f"Found PR URL in interface: {href}")
                    return href
            
            # Also check page content for PR URLs
            page_content = await self.browser_manager.page.content()
            import re
            pr_pattern = r'https://github\.com/[^/]+/[^/]+/pull/\d+'
            matches = re.findall(pr_pattern, page_content)
            if matches:
                pr_url = matches[-1]  # Get the most recent PR URL
                print(f"Found PR URL in page content: {pr_url}")
                return pr_url
            
            return None
            
        except Exception as e:
            print(f"WARNING: Could not extract PR URL from interface: {str(e)}")
            return None 