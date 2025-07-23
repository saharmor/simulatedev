#!/usr/bin/env python3
"""
Browser Manager for Web Agents

This module provides a centralized browser management class that handles:
- Browser initialization and cleanup
- Session state management
- Authentication flows (Google, GitHub, etc.)
- Captcha detection and solving
- Human-like interactions
- File downloads
- Screenshot capture

Used by web agents to avoid code duplication and provide consistent browser behavior.
"""

import asyncio
import os
import time
import random
import math
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError


class BrowserManager:
    """Centralized browser management for web agents using Playwright"""
    
    def __init__(self, headless: bool = False, auth_file_path: Optional[str] = None):
        """
        Initialize the browser manager
        
        Args:
            headless: Whether to run browser in headless mode
            auth_file_path: Path to save/load authentication state
        """
        self.headless = headless
        self.auth_file_path = auth_file_path or os.getenv('PLAYWRIGHT_AUTH_FILE')
        
        # Browser components
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # State tracking
        self._is_ready = False
        self._current_url: Optional[str] = None
        
        # Configuration
        self.window_width = int(os.getenv('PLAYWRIGHT_WINDOW_WIDTH', '1920'))
        self.window_height = int(os.getenv('PLAYWRIGHT_WINDOW_HEIGHT', '1080'))
        self.window_x = int(os.getenv('PLAYWRIGHT_WINDOW_X', '0'))
        self.window_y = int(os.getenv('PLAYWRIGHT_WINDOW_Y', '0'))
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()
    
    @property
    def is_ready(self) -> bool:
        """Check if browser is ready for use"""
        return self._is_ready and self.page is not None and not self.page.is_closed()
    
    @property
    def current_url(self) -> Optional[str]:
        """Get current page URL"""
        if self.page and not self.page.is_closed():
            return self.page.url
        return self._current_url
    
    async def initialize(self) -> bool:
        """Initialize browser and create context"""
        try:
            print("Initializing browser manager...")
            
            # Start Playwright
            self.playwright = await async_playwright().start()
            
            # Configure launch arguments
            launch_args = []
            if not self.headless:
                launch_args.extend([
                    f"--window-position={self.window_x},{self.window_y}",
                    f"--window-size={self.window_width},{self.window_height}"
                ])
            
            # Launch browser
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=launch_args
            )
            
            # Load storage state if available
            storage_state = await self._load_storage_state()
            
            # Create context
            self.context = await self.browser.new_context(
                storage_state=storage_state,
                accept_downloads=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Create page
            self.page = await self.context.new_page()
            
            self._is_ready = True
            print("Browser manager initialized successfully")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to initialize browser manager: {str(e)}")
            await self.cleanup()
            return False
    
    async def cleanup(self):
        """Clean up all browser resources"""
        try:
            self._is_ready = False
            
            if self.page and not self.page.is_closed():
                await self.page.close()
                self.page = None
            
            if self.context:
                await self.context.close()
                self.context = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            print("Browser manager cleaned up successfully")
            
        except Exception as e:
            print(f"WARNING: Error during browser cleanup: {str(e)}")
    
    async def navigate_to(self, url: str, wait_until: str = 'networkidle', timeout: int = 60000) -> bool:
        """
        Navigate to a URL
        
        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete
            timeout: Navigation timeout in milliseconds
            
        Returns:
            bool: True if navigation successful
        """
        if not self.is_ready:
            print("ERROR: Browser not ready for navigation")
            return False
        
        try:
            print(f"Navigating to: {url}")
            await self.page.goto(url, wait_until=wait_until, timeout=timeout)
            self._current_url = url
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to navigate to {url}: {str(e)}")
            return False
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000, state: str = 'visible') -> bool:
        """
        Wait for a selector to appear
        
        Args:
            selector: CSS selector to wait for
            timeout: Timeout in milliseconds
            state: State to wait for ('visible', 'hidden', 'attached', 'detached')
            
        Returns:
            bool: True if selector found
        """
        if not self.is_ready:
            return False
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return True
        except PlaywrightTimeoutError:
            return False
        except Exception as e:
            print(f"WARNING: Error waiting for selector {selector}: {str(e)}")
            return False
    
    async def click_element(self, selector: str, human_like: bool = True, timeout: int = 30000) -> bool:
        """
        Click an element
        
        Args:
            selector: CSS selector of element to click
            human_like: Whether to use human-like clicking behavior
            timeout: Timeout in milliseconds
            
        Returns:
            bool: True if click successful
        """
        if not self.is_ready:
            return False
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            element = await self.page.query_selector(selector)
            
            if not element:
                return False
            
            if human_like:
                await self._human_like_click(element)
            else:
                await element.click()
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to click element {selector}: {str(e)}")
            return False
    
    async def fill_input(self, selector: str, text: str, clear_first: bool = True, timeout: int = 30000) -> bool:
        """
        Fill an input field
        
        Args:
            selector: CSS selector of input field
            text: Text to fill
            clear_first: Whether to clear field first
            timeout: Timeout in milliseconds
            
        Returns:
            bool: True if fill successful
        """
        if not self.is_ready:
            return False
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            
            if clear_first:
                await self.page.fill(selector, "")
            
            await self.page.fill(selector, text)
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to fill input {selector}: {str(e)}")
            return False
    
    async def get_text_content(self, selector: str, timeout: int = 10000) -> Optional[str]:
        """
        Get text content of an element
        
        Args:
            selector: CSS selector of element
            timeout: Timeout in milliseconds
            
        Returns:
            Optional[str]: Text content or None if not found
        """
        if not self.is_ready:
            return None
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            element = await self.page.query_selector(selector)
            if element:
                return await element.text_content()
            return None
            
        except Exception as e:
            print(f"WARNING: Failed to get text content for {selector}: {str(e)}")
            return None
    
    async def take_screenshot(self, filename: Optional[str] = None, full_page: bool = True) -> Optional[str]:
        """
        Take a screenshot
        
        Args:
            filename: Optional filename (will generate timestamp-based name if not provided)
            full_page: Whether to capture full page
            
        Returns:
            Optional[str]: Path to screenshot file
        """
        if not self.is_ready:
            return None
        
        try:
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            # Ensure screenshots directory exists
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            
            screenshot_path = screenshots_dir / filename
            
            await self.page.screenshot(path=str(screenshot_path), full_page=full_page)
            print(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            print(f"WARNING: Failed to take screenshot: {str(e)}")
            return None
    
    async def handle_google_login(self, email: str, password: str) -> bool:
        """
        Handle Google authentication flow
        
        Args:
            email: Google email address
            password: Google password
            
        Returns:
            bool: True if login successful
        """
        try:
            print("Starting Google authentication flow...")
            
            # Wait for page to be ready
            await self.page.wait_for_timeout(2000)
            
            # Handle email input
            email_selectors = [
                "input[type='email']",
                "#identifierId",
                "input[name='email']",
                "input[autocomplete='username']"
            ]
            
            email_filled = False
            for selector in email_selectors:
                try:
                    if await self.wait_for_selector(selector, timeout=5000):
                        await self.fill_input(selector, email)
                        email_filled = True
                        break
                except:
                    continue
            
            if not email_filled:
                print("ERROR: Could not find email input field")
                return False
            
            # Click Next button for email
            next_selectors = [
                "#identifierNext",
                "button:has-text('Next')",
                "input[type='submit']",
                "button[type='submit']"
            ]
            
            for selector in next_selectors:
                try:
                    if await self.click_element(selector, timeout=5000):
                        break
                except:
                    continue
            
            # Wait for password page
            await self.page.wait_for_timeout(3000)
            
            # Handle password input
            password_selectors = [
                "input[type='password']",
                "input[name='password']",
                "#password",
                "input[autocomplete='current-password']"
            ]
            
            password_filled = False
            for selector in password_selectors:
                try:
                    if await self.wait_for_selector(selector, timeout=10000):
                        await self.fill_input(selector, password)
                        password_filled = True
                        break
                except:
                    continue
            
            if not password_filled:
                print("ERROR: Could not find password input field")
                return False
            
            # Click Next button for password
            for selector in next_selectors:
                try:
                    if await self.click_element(selector, timeout=5000):
                        break
                except:
                    continue
            
            # Wait for login completion or 2FA
            await self.page.wait_for_timeout(5000)
            
            # Check if still on Google login page (might need 2FA)
            current_url = self.page.url
            if 'accounts.google.com' in current_url:
                print("Waiting for additional verification (2FA, etc.)...")
                
                # Poll for completion (up to 5 minutes)
                max_wait = 300  # 5 minutes
                poll_interval = 5
                elapsed = 0
                
                while elapsed < max_wait:
                    await self.page.wait_for_timeout(poll_interval * 1000)
                    elapsed += poll_interval
                    
                    current_url = self.page.url
                    if 'accounts.google.com' not in current_url:
                        print("Google authentication completed")
                        return True
                
                print("WARNING: Google authentication timed out")
                return False
            
            print("Google authentication completed")
            return True
            
        except Exception as e:
            print(f"ERROR: Google authentication failed: {str(e)}")
            return False
    
    async def solve_captcha_if_present(self) -> bool:
        """
        Detect and attempt to solve captchas
        
        Returns:
            bool: True if captcha was handled (or none present)
        """
        try:
            # Check for Cloudflare Turnstile
            if await self._solve_cloudflare_turnstile():
                return True
            
            # Check for other captcha types
            captcha_selectors = [
                'iframe[src*="hcaptcha.com"]',
                'iframe[src*="recaptcha"]',
                '.captcha',
                '#captcha',
                '[data-captcha]'
            ]
            
            for selector in captcha_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f"CAPTCHA detected: {selector}")
                        print("Manual intervention may be required")
                        await self.page.wait_for_timeout(5000)
                        return True
                except:
                    continue
            
            return True  # No captcha found
            
        except Exception as e:
            print(f"WARNING: Error during captcha detection: {str(e)}")
            return True
    
    async def download_file(self, download_url: str, filename: Optional[str] = None) -> Optional[str]:
        """
        Download a file
        
        Args:
            download_url: URL to download from
            filename: Optional filename (will use URL filename if not provided)
            
        Returns:
            Optional[str]: Path to downloaded file
        """
        if not self.is_ready:
            return None
        
        try:
            # Ensure downloads directory exists
            downloads_dir = Path("downloads")
            downloads_dir.mkdir(exist_ok=True)
            
            # Start download
            async with self.page.expect_download() as download_info:
                await self.page.goto(download_url)
            
            download = await download_info.value
            
            # Determine filename
            if not filename:
                filename = download.suggested_filename or f"download_{int(time.time())}"
            
            download_path = downloads_dir / filename
            
            # Save download
            await download.save_as(str(download_path))
            print(f"File downloaded: {download_path}")
            return str(download_path)
            
        except Exception as e:
            print(f"ERROR: Failed to download file: {str(e)}")
            return None
    
    async def save_storage_state(self) -> bool:
        """
        Save current browser storage state for session persistence
        
        Returns:
            bool: True if save successful
        """
        if not self.context or not self.auth_file_path:
            return False
        
        try:
            auth_path = Path(self.auth_file_path)
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            
            await self.context.storage_state(path=str(auth_path))
            print(f"Storage state saved: {auth_path}")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to save storage state: {str(e)}")
            return False
    
    async def _load_storage_state(self) -> Optional[str]:
        """Load storage state from file"""
        if not self.auth_file_path:
            return None
        
        auth_path = Path(self.auth_file_path)
        if auth_path.exists():
            print(f"Loading storage state from: {auth_path}")
            return str(auth_path)
        
        print("No saved storage state found")
        return None
    
    async def _solve_cloudflare_turnstile(self) -> bool:
        """Solve Cloudflare Turnstile captcha"""
        try:
            # Check for Turnstile indicators
            turnstile_selectors = [
                'input[name="cf-turnstile-response"]',
                'div[id*="cf-chl-widget"]',
                '.cf-turnstile',
                '[data-sitekey]',
                'iframe[src*="challenges.cloudflare.com"]'
            ]
            
            turnstile_found = False
            for selector in turnstile_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        turnstile_found = True
                        print(f"Cloudflare Turnstile detected: {selector}")
                        break
                except:
                    continue
            
            if not turnstile_found:
                return False
            
            # Wait for Turnstile to load
            print("Waiting for Cloudflare Turnstile to load...")
            await self.page.wait_for_timeout(3000)
            
            # Look for interactive elements
            checkbox_selectors = [
                'input[type="checkbox"]',
                '.cf-turnstile input',
                'iframe[src*="challenges.cloudflare.com"]',
                '[role="checkbox"]',
                'button[type="button"]'
            ]
            
            checkbox_element = None
            for selector in checkbox_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements:
                        if await element.is_visible():
                            box = await element.bounding_box()
                            if box and box['width'] > 10 and box['height'] > 10:
                                checkbox_element = element
                                print(f"Found Turnstile interactive element: {selector}")
                                break
                    if checkbox_element:
                        break
                except:
                    continue
            
            # Click with human-like behavior
            if checkbox_element:
                await self._human_like_click(checkbox_element)
                print("Waiting for Turnstile verification...")
                await self.page.wait_for_timeout(10000)
            else:
                print("No visible Turnstile checkbox found, waiting for automatic verification...")
                await self.page.wait_for_timeout(10000)
            
            # Check if verification successful
            try:
                response_input = await self.page.query_selector('input[name="cf-turnstile-response"]')
                if response_input:
                    response_value = await response_input.get_attribute('value')
                    if response_value and len(response_value) > 10:
                        print("Cloudflare Turnstile verification successful!")
                        return True
            except:
                pass
            
            # Check URL redirect
            current_url = self.page.url
            if 'challenge' not in current_url.lower() and '__cf_chl_' not in current_url:
                print("Cloudflare Turnstile verification successful (redirected)!")
                return True
            
            return False
            
        except Exception as e:
            print(f"WARNING: Error solving Cloudflare Turnstile: {str(e)}")
            return False
    
    async def _human_like_click(self, element):
        """Perform human-like click with natural cursor movements"""
        try:
            # Get element position
            box = await element.bounding_box()
            if not box:
                await element.click()
                return
            
            # Calculate target position with randomness
            target_x = box['x'] + box['width'] * (0.3 + random.random() * 0.4)
            target_y = box['y'] + box['height'] * (0.3 + random.random() * 0.4)
            
            # Start from nearby position
            start_x = target_x + random.randint(-100, 100)
            start_y = target_y + random.randint(-100, 100)
            
            # Move mouse naturally
            await self._move_mouse_naturally(start_x, start_y, target_x, target_y)
            
            # Random delay before click
            await self.page.wait_for_timeout(random.randint(100, 500))
            
            # Click
            await self.page.mouse.click(target_x, target_y)
            
            # Random delay after click
            await self.page.wait_for_timeout(random.randint(200, 800))
            
        except Exception as e:
            print(f"WARNING: Error in human-like click: {str(e)}")
            await element.click()
    
    async def _move_mouse_naturally(self, start_x: float, start_y: float, end_x: float, end_y: float):
        """Move mouse in natural, curved path"""
        try:
            # Move to starting position
            await self.page.mouse.move(start_x, start_y)
            
            # Calculate steps
            distance = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            steps = max(10, int(distance / 10))
            
            for i in range(steps):
                progress = (i + 1) / steps
                
                # Add curve and randomness
                curve_offset = math.sin(progress * math.pi) * random.uniform(-10, 10)
                
                current_x = start_x + (end_x - start_x) * progress + curve_offset
                current_y = start_y + (end_y - start_y) * progress + curve_offset
                
                # Add micro-movements
                current_x += random.uniform(-2, 2)
                current_y += random.uniform(-2, 2)
                
                await self.page.mouse.move(current_x, current_y)
                
                # Variable delays
                if i < 2 or i > steps - 3:
                    delay = random.randint(50, 150)
                else:
                    delay = random.randint(20, 80)
                
                await self.page.wait_for_timeout(delay)
            
            # Final move to exact target
            await self.page.mouse.move(end_x, end_y)
            
        except Exception as e:
            print(f"WARNING: Error in natural mouse movement: {str(e)}")
            await self.page.mouse.move(end_x, end_y) 

    async def handle_authentication(self, auth_type: str, credentials: Dict[str, str]) -> bool:
        """
        Handle various authentication flows
        
        Args:
            auth_type: Type of authentication ('google', 'github', 'email')
            credentials: Dictionary containing authentication credentials
                        For Google: {'email': '...', 'password': '...'}
                        For GitHub: {'username': '...', 'password': '...'}
                        For email: {'email': '...', 'password': '...'}
        
        Returns:
            bool: True if authentication successful
        """
        if auth_type.lower() == 'google':
            email = credentials.get('email')
            password = credentials.get('password')
            if not email or not password:
                print("ERROR: Google authentication requires 'email' and 'password' in credentials")
                return False
            return await self.handle_google_login(email, password)
        
        elif auth_type.lower() == 'github':
            # GitHub authentication logic could be added here
            username = credentials.get('username')
            password = credentials.get('password')
            if not username or not password:
                print("ERROR: GitHub authentication requires 'username' and 'password' in credentials")
                return False
            
            # GitHub login implementation would go here
            print("GitHub authentication not yet implemented")
            return False
        
        elif auth_type.lower() == 'email':
            # Generic email/password form authentication
            email = credentials.get('email')
            password = credentials.get('password')
            if not email or not password:
                print("ERROR: Email authentication requires 'email' and 'password' in credentials")
                return False
            
            # Try common email/password selectors
            email_selectors = ['input[type="email"]', 'input[name="email"]', '#email']
            password_selectors = ['input[type="password"]', 'input[name="password"]', '#password']
            submit_selectors = ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Login")', 'button:has-text("Sign in")']
            
            # Fill email
            email_filled = False
            for selector in email_selectors:
                if await self.fill_input(selector, email, timeout=5000):
                    email_filled = True
                    break
            
            if not email_filled:
                print("ERROR: Could not find email input field")
                return False
            
            # Fill password
            password_filled = False
            for selector in password_selectors:
                if await self.fill_input(selector, password, timeout=5000):
                    password_filled = True
                    break
            
            if not password_filled:
                print("ERROR: Could not find password input field")
                return False
            
            # Submit form
            for selector in submit_selectors:
                if await self.click_element(selector, timeout=5000):
                    await asyncio.sleep(3)  # Wait for login to process
                    return True
            
            print("ERROR: Could not find submit button")
            return False
        
        else:
            print(f"ERROR: Unsupported authentication type: {auth_type}")
            return False 