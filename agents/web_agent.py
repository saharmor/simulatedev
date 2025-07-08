#!/usr/bin/env python3
"""
Web Agent Base Class Implementation

This module provides a base class for web-based coding agents that run in browsers.
Uses Botright for stealth browser automation and captcha solving.
"""

import asyncio
import time
import os
from abc import abstractmethod
from typing import Optional, Dict, Any
from .base import CodingAgent, AgentResponse
from common.exceptions import AgentTimeoutException
from common.config import config

import botright


# Selector constants for Google authentication
class GoogleSelectors:
    # Email input selectors
    EMAIL_INPUTS = [
        "input[type='email']",
        "#identifierId",
        "input[name='email']",
        "input[autocomplete='username']"
    ]
    
    # Email next/submit button selectors
    EMAIL_NEXT_BUTTONS = [
        "#identifierNext",
        "button:has-text('Next')",
        "input[type='submit']",
        "button[type='submit']"
    ]
    
    # Password input selectors
    PASSWORD_INPUTS = [
        "input[type='password']",
        "input[name='password']",
        "#password",
        "input[autocomplete='current-password']"
    ]
    
    # Password next/submit button selectors
    PASSWORD_NEXT_BUTTONS = [
        "#passwordNext",
        "button:has-text('Next')",
        "input[type='submit']",
        "button[type='submit']"
    ]


class WebAgent(CodingAgent):
    """Base class for web-based coding agents using Botright"""
    
    def __init__(self, computer_use_client):
        super().__init__(computer_use_client)
        self.botright_client = None
        self.browser = None
        self.page = None
        self._is_browser_ready = False
    
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
            return self._is_browser_ready
        
        # For web agents, we consider the project "correct" if the browser is ready
        # and we're on the right URL. Subclasses can override for more specific checks.
        return self._is_browser_ready and self.page is not None
    
    async def is_coding_agent_open(self) -> bool:
        """Check if the browser is open and ready"""
        try:
            return self._is_browser_ready and self.page is not None
                
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
            
            # Initialize Botright client if not already done
            if not self.botright_client:
                self.botright_client = await botright.Botright(
                    headless=False,  # Keep visible for debugging, can be made configurable
                    user_action_layer=True,  # Show what the bot is doing
                    mask_fingerprint=True,  # Enable stealth mode
                    spoof_canvas=True,  # Spoof canvas fingerprinting
                    scroll_into_view=True,  # Scroll into view
                )
            
            # Create new browser if not already done
            if not self.browser:
                self.browser = await self.botright_client.new_browser(no_viewport=True)
                
            # Create new page
            self.page = await self.browser.new_page()
            
            # Navigate to the web agent URL
            await self.page.goto(self.web_url)
            
            # Wait for page to load
            await self.page.wait_for_load_state("networkidle")
            
            # Perform any agent-specific setup
            setup_success = await self._setup_web_interface()
            if not setup_success:
                print(f"ERROR: Failed to setup {self.agent_name} web interface")
                return False
            
            self._is_browser_ready = True
            print(f"SUCCESS: {self.agent_name} web interface is ready")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to open {self.agent_name} web interface: {str(e)}")
            await self._cleanup_browser()
            return False
    
    async def close_coding_interface(self) -> bool:
        """Close the web browser"""
        try:
            await self._cleanup_browser()
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to close {self.agent_name} web interface: {str(e)}")
            return False
    
    async def _cleanup_browser(self):
        """Clean up browser resources"""
        try:
            self._is_browser_ready = False
            
            if self.page:
                await self.page.close()
                self.page = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
            if self.botright_client:
                await self.botright_client.close()
                self.botright_client = None
                
        except Exception as e:
            print(f"WARNING: Error during browser cleanup: {str(e)}")
    
    async def _setup_web_interface(self) -> bool:
        """Perform agent-specific setup after navigation. Override in subclasses."""
        # Default implementation - subclasses can override for specific setup
        try:
            # Example: Handle Google login if redirected to Google login page
            # if 'accounts.google.com' in self.page.url:
            #     await self.handle_google_login()
            
            # Solve any captchas that might appear
            await self.solve_captcha_if_present()
            
            # Wait for input field to be available
            await self.page.wait_for_selector(self.input_selector, timeout=10000)
            return True
        except Exception as e:
            print(f"ERROR: Could not find input field for {self.agent_name}: {str(e)}")
            return False
    
    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute prompt by sending it to the web interface"""
        try:
            if not self._is_browser_ready or not self.page:
                raise Exception("Browser not ready. Call open_coding_interface() first.")
            
            print(f"Executing task: {prompt[:100]}...")
            
            # Combine prompt with instruction to save output
            combined_prompt = f"""{prompt}\n\nAfter completing the above task, please save a comprehensive summary of everything you did to a file called '{self.output_file}' in the current directory. Include:\n- All changes made\n- Explanations of what was done.\n\nIMPORTANT: Do NOT create or update any documentation files (such as README.md or docs/*) unless you are explicitly asked to do so in the original prompt. If you believe that creating a documentation file would help you better implement the required coding task, you may create it, but you must delete it once you are finished and before you finish the task."""
            
            # Send prompt to web interface
            await self._send_prompt_to_web_interface(combined_prompt)
            
            # Wait for completion
            await self._wait_for_web_completion()
            
            # Read output file
            content = await self._read_output_file()
            
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
            # Focus on input field
            await self.page.click(self.input_selector)
            
            # Clear any existing content
            await self.page.fill(self.input_selector, "")
            
            # Enter the prompt
            await self.page.fill(self.input_selector, prompt)
            
            # Submit the prompt
            await self.page.click(self.submit_selector)
            
            # Small delay after submission
            await self.page.wait_for_timeout(2000)
            
        except Exception as e:
            raise Exception(f"Failed to send prompt to web interface: {str(e)}")
    
    async def _wait_for_web_completion(self):
        """Wait for the web agent to complete processing"""
        timeout_seconds = config.agent_timeout_seconds
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout_seconds:
                # Check if loading indicator is present (if defined)
                if self.loading_selector:
                    # If loading indicator is still visible, keep waiting
                    await self.page.wait_for_selector(
                        self.loading_selector, 
                        state="hidden", 
                        timeout=5000
                    )
                    break
                
                # Check if output area has been updated (basic implementation)
                output_element = await self.page.query_selector(self.output_selector)
                if output_element:
                    output_text = await output_element.text_content()
                    if output_text and len(output_text.strip()) > 100:  # Arbitrary threshold
                        # Wait a bit more to ensure completion
                        await self.page.wait_for_timeout(10000)
                        break
                
                # Wait before next check
                await self.page.wait_for_timeout(5000)
            
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
            if not self.page:
                return ""
            
            # Try to get output from the designated output selector
            output_element = await self.page.query_selector(self.output_selector)
            if output_element:
                return await output_element.text_content() or ""
            
            return ""
            
        except Exception as e:
            print(f"WARNING: Could not extract output from web interface: {str(e)}")
            return ""
    
    async def handle_google_login(self) -> bool:
        """Handle Google authentication using environment variables
        
        Assumes we're already on the Google login page.
        Uses GOOGLE_EMAIL and GOOGLE_PASSWORD environment variables.
        
        Returns:
            bool: True if login was successful, False if login failed
        """
        try:
            # Get credentials from environment variables
            google_email = os.getenv('GOOGLE_EMAIL')
            google_password = os.getenv('GOOGLE_PASSWORD')
            
            if not google_email or not google_password:
                print("ERROR: GOOGLE_EMAIL or GOOGLE_PASSWORD environment variables not set")
                return False
            
            # Wait for Google login page to be ready
            await self.page.wait_for_timeout(2000)
            
            # Handle email input
            email_input = None
            for selector in GoogleSelectors.EMAIL_INPUTS:
                try:
                    email_input = await self.page.query_selector(selector)
                    if email_input:
                        break
                except:
                    continue
            
            if email_input:
                await email_input.fill(google_email)
                
                # Click Next or submit button for email
                for selector in GoogleSelectors.EMAIL_NEXT_BUTTONS:
                    try:
                        next_button = await self.page.query_selector(selector)
                        if next_button:
                            await next_button.click()
                            break
                    except:
                        continue
                
                # Wait for password page
                await self.page.wait_for_timeout(3000)
            
            # Handle password input
            password_input = None
            for selector in GoogleSelectors.PASSWORD_INPUTS:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    password_input = await self.page.query_selector(selector)
                    if password_input:
                        break
                except:
                    continue
            
            if password_input:
                await password_input.fill(google_password)
                
                # Click Next or submit button for password
                for selector in GoogleSelectors.PASSWORD_NEXT_BUTTONS:
                    try:
                        next_button = await self.page.query_selector(selector)
                        if next_button:
                            await next_button.click()
                            break
                    except:
                        continue
                
                # Wait for login to complete
                await self.page.wait_for_timeout(5000)
                
                # Check if we're back to the original site (successful login)
                current_url = self.page.url
                if 'accounts.google.com' not in current_url:
                    return True
                else:
                    # Check for 2FA or other verification steps with polling
                    print("Waiting for verification (2FA, etc.)...")
                    
                    # Poll every 5 seconds for up to 5 minutes (300 seconds)
                    max_wait_seconds = 300  # 5 minutes
                    poll_interval_seconds = 5
                    elapsed_seconds = 0
                    
                    while elapsed_seconds < max_wait_seconds:
                        await self.page.wait_for_timeout(poll_interval_seconds * 1000)
                        elapsed_seconds += poll_interval_seconds
                        
                        # Check if login completed
                        current_url = self.page.url
                        if 'accounts.google.com' not in current_url:
                            return True
                    
                    # Timed out
                    print("WARNING: Login verification timed out")
                    return False
            else:
                print("ERROR: Could not find password input field")
                return False
                
        except Exception as e:
            print(f"ERROR: Google login failed: {str(e)}")
            return False

    async def solve_captcha_if_present(self) -> bool:
        """Use Botright's captcha solving capabilities if a captcha is detected"""
        try:
            # Check for common captcha types and solve them using Botright
            # This is a basic implementation - subclasses can override for specific captcha handling
            
            # Try to solve hCaptcha
            try:
                await self.page.solve_hcaptcha()
                return True
            except:
                pass
            
            # Try to solve reCaptcha
            try:
                await self.page.solve_recaptcha()
                return True
            except:
                pass
            
            # Try to solve geeTest
            try:
                await self.page.solve_geetest()
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"WARNING: Error during captcha solving: {str(e)}")
            return False 