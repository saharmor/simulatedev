#!/usr/bin/env python3
"""
OpenAI Codex Web Agent Implementation

This agent handles authentication flow to access OpenAI Codex at chatgpt.com/codex
"""

import re
import time
from typing import Optional
from .web_agent import WebAgent, AgentResponse


class OpenAICodexAgent(WebAgent):
    """OpenAI Codex web agent with authentication handling"""
    
    def __init__(self, computer_use_client):
        super().__init__(computer_use_client)
    
    @property
    def web_url(self) -> str:
        """Start with the environments page URL that redirects to login if not authenticated"""
        return "https://chatgpt.com/auth/login?next=/codex/settings/environments"
    
    @property
    def input_selector(self) -> str:
        """CSS selector for the prompt input field - contenteditable ProseMirror editor"""
        return "#prompt-textarea"
    
    @property
    def submit_selector(self) -> str:
        """CSS selector for the Code button"""
        # Based on common patterns, look for a button with "Code" text
        return "button:has-text('Code'), button[aria-label*='Code'], button:contains('Code')"
    
    @property
    def output_selector(self) -> str:
        """CSS selector for the output/response area"""
        # Look for task containers or conversation responses
        return ".task-row-container, [data-message-author-role='assistant'], .conversation-item"
    
    @property
    def loading_selector(self) -> Optional[str]:
        """CSS selector for loading indicator"""
        return ".animate-pulse, .loading, [role='progressbar']"

    def _extract_repo_name_from_url(self, repo_url: str) -> str:
        """Extract repository name from GitHub URL for matching"""
        if not repo_url:
            return ""
        
        # Handle different GitHub URL formats
        # https://github.com/user/repo or https://github.com/user/repo.git
        pattern = r'github\.com[/:]([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?/?$'
        match = re.search(pattern, repo_url)
        
        if match:
            username, repo_name = match.groups()
            return f"{username}/{repo_name}"
        
        return ""

    def _extract_repo_name_only(self, repo_url: str) -> str:
        """Extract just the repository name (without username) from GitHub URL"""
        if not repo_url:
            return ""
        
        # Handle different GitHub URL formats
        # https://github.com/user/repo or https://github.com/user/repo.git
        pattern = r'github\.com[/:]([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?/?$'
        match = re.search(pattern, repo_url)
        
        if match:
            username, repo_name = match.groups()
            return repo_name  # Return just the repo name
        
        return ""

    async def _is_authenticated(self) -> bool:
        """Check if we're authenticated by looking at the current URL"""
        current_url = self.page.url
        # Check for both environments page and environment creation page
        return ('chatgpt.com/codex/settings/environments' in current_url or 
                'chatgpt.com/codex/settings/environment' in current_url)

    async def _find_repo_in_environments_table(self, repo_name: str) -> bool:
        """Check if the repository exists in the environments table and click on it if found"""
        try:
            print(f"Looking for repository '{repo_name}' in environments table...")
            
            # Look for table rows containing the repo name
            row_selector = f"tr.group\\/row:has-text('{repo_name}')"
            
            try:
                row = await self.page.query_selector(row_selector)
                if row:
                    print(f"Found repository '{repo_name}' in environments table")
                    await row.click()
                    await self.page.wait_for_timeout(2000)
                    return True
            except:
                pass
            
            # Fallback: look for any clickable element containing the repo name
            clickable_selectors = [
                f"td:has-text('{repo_name}')",
                f"div:has-text('{repo_name}')",
                f"[href*='{repo_name}']"
            ]
            
            for selector in clickable_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        print(f"Found repository '{repo_name}' with selector: {selector}")
                        # Click on the parent row if it's a table cell
                        if selector.startswith('td'):
                            row = await element.locator('xpath=ancestor::tr[1]').first
                            await row.click()
                        else:
                            await element.click()
                        await self.page.wait_for_timeout(2000)
                        return True
                except:
                    continue
            
            print(f"Repository '{repo_name}' not found in environments table")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to search for repository in environments table: {str(e)}")
            return False

    async def _wait_for_redirect_to_environment_page(self) -> bool:
        """Wait for redirect to environment page and for 'Use this' button to appear"""
        try:
            print("Waiting for redirect after creating environment...")
            
            # Wait for URL to change (indicating redirect)
            max_wait_seconds = 30
            start_time = time.time()
            initial_url = self.page.url
            
            while time.time() - start_time < max_wait_seconds:
                current_url = self.page.url
                if current_url != initial_url and 'settings/environment' not in current_url:
                    print(f"Redirect detected to: {current_url}")
                    break
                await self.page.wait_for_timeout(1000)
            else:
                print("WARNING: No redirect detected, continuing anyway...")
            
            # Wait for the "Use this" button to appear on the new page
            print("Waiting for 'Use this' button to appear...")
            use_this_selectors = [
                "button:has-text('Use this')",
                "button:contains('Use this')",
                ".btn:has-text('Use this')",
                "button[type='button']:has-text('Use this')"
            ]
            
            for selector in use_this_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=15000)
                    button = await self.page.query_selector(selector)
                    if button and await button.is_visible():
                        print(f"'Use this' button is ready with selector: {selector}")
                        return True
                except:
                    continue
            
            print("WARNING: 'Use this' button not found after redirect")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to wait for environment page redirect: {str(e)}")
            return False

    async def _click_use_this_button(self) -> bool:
        """Click the 'Use this' button after selecting a repository"""
        try:
            print("Looking for 'Use this' button...")
            
            use_this_selectors = [
                "button:has-text('Use this')",
                "button:contains('Use this')",
                ".btn:has-text('Use this')",
                "button[type='button']:has-text('Use this')"
            ]
            
            for selector in use_this_selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            print(f"Found 'Use this' button with selector: {selector}")
                            await button.click()
                            print("Successfully clicked 'Use this' button")
                            await self.page.wait_for_timeout(3000)
                            return True
                except:
                    continue
            
            print("ERROR: Could not find 'Use this' button")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to click 'Use this' button: {str(e)}")
            return False

    async def _click_create_environment_button(self) -> bool:
        """Click the 'Create environment' button to create a new environment"""
        try:
            print("Looking for 'Create environment' button...")
            
            create_env_selectors = [
                "button.btn.btn-primary:has(div:contains('Create environment'))",  # Nested div selector
                "button.btn-primary",  # Primary button selector
                "button:has(div:text('Create environment'))",  # Alternative nested text
                ".btn.btn-primary",  # Class-based fallback
                "button[type='button']:has(div:contains('Create'))"  # Generic create button
            ]
            
            for selector in create_env_selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            print(f"Found 'Create environment' button with selector: {selector}")
                            await button.click()
                            print("Successfully clicked 'Create environment' button")
                            await self.page.wait_for_timeout(3000)
                            return True
                except:
                    continue
            
            print("ERROR: Could not find 'Create environment' button")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to click 'Create environment' button: {str(e)}")
            return False

    async def _wait_for_creation_list_to_load(self) -> bool:
        """Wait for the repository creation list to load"""
        try:
            print("Waiting for repository creation list to load...")
            
            # Wait for the repository list container to appear
            list_container_selectors = [
                ".flex.max-h-56.flex-col.overflow-y-auto",  # The scrollable container
                "button p.text-token-text-primary",  # Repository name elements
                ".group.flex.w-full.items-center",  # Repository button containers
            ]
            
            scrollable_container = None
            for selector in list_container_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=10000)
                    print(f"Found creation list with selector: {selector}")
                    
                    # Try to get the scrollable container
                    if selector == ".flex.max-h-56.flex-col.overflow-y-auto":
                        scrollable_container = await self.page.query_selector(selector)
                    
                    # Wait a bit more for all repos to load
                    await self.page.wait_for_timeout(2000)
                    
                    # Verify we have at least one repository button
                    repo_buttons = await self.page.query_selector_all("button p.text-token-text-primary")
                    if repo_buttons and len(repo_buttons) > 0:
                        print(f"Repository creation list loaded with {len(repo_buttons)} repositories")
                        
                        # If we found the scrollable container, scroll to top to ensure consistent positioning
                        if scrollable_container:
                            try:
                                await scrollable_container.evaluate("element => element.scrollTop = 0")
                                await self.page.wait_for_timeout(500)
                                print("Reset scrollable container to top")
                            except Exception as scroll_reset_error:
                                print(f"Warning: Could not reset scroll position: {scroll_reset_error}")
                        
                        return True
                except:
                    continue
            
            print("WARNING: Could not detect repository creation list")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to wait for creation list: {str(e)}")
            return False

    async def _select_repo_from_creation_list(self, repo_name_only: str) -> bool:
        """Select repository from the creation list and click Create environment"""
        try:
            print(f"Looking for repository '{repo_name_only}' in creation list...")
            
            # First wait for the creation list to load
            if not await self._wait_for_creation_list_to_load():
                print("ERROR: Creation list did not load")
                return False
            
            # Look for repository name in the specific structure
            repo_button = None
            
            # Target the specific structure with repository name in p.text-token-text-primary
            button_selectors = [
                f"button:has(p.text-token-text-primary.text-start.text-sm.font-medium:text('{repo_name_only}'))",  # Most specific
                f"button:has(p.text-token-text-primary:text('{repo_name_only}'))",  # Target the p element with repo name
                f"button.group:has(p.text-token-text-primary:text('{repo_name_only}'))",  # With group class
                f"button:has(div.flex.items-center.justify-between p:text('{repo_name_only}'))",  # Target container structure
                f"button:has(p:text('{repo_name_only}'))"  # Fallback
            ]
            
            for selector in button_selectors:
                try:
                    print(f"Trying selector: {selector}")
                    repo_button = await self.page.query_selector(selector)
                    if repo_button:
                        is_visible = await repo_button.is_visible()
                        print(f"Found repository button '{repo_name_only}' with selector: {selector} (visible: {is_visible})")
                        break
                except Exception as e:
                    print(f"Selector failed: {selector} - {str(e)}")
                    continue
            
            # Fallback: search all repository buttons by text content
            if not repo_button:
                print(f"Trying fallback search for '{repo_name_only}'...")
                
                # First try to find buttons that look like repository items
                button_container_selectors = [
                    "button.group",  # Buttons with group class
                    "button:has(div.flex.items-center.justify-between)",  # Buttons with the specific container structure
                    "button:has(p.text-token-text-primary)",  # Buttons containing repository name elements
                    "button"  # All buttons as final fallback
                ]
                
                for container_selector in button_container_selectors:
                    try:
                        all_buttons = await self.page.query_selector_all(container_selector)
                        print(f"Found {len(all_buttons)} buttons with selector: {container_selector}")
                        
                        for button in all_buttons:
                            try:
                                # Look for the specific p element with the exact classes
                                p_element = await button.query_selector("p.text-token-text-primary.text-start.text-sm.font-medium")
                                if not p_element:
                                    # Fallback to less specific selector
                                    p_element = await button.query_selector("p.text-token-text-primary")
                                
                                if p_element:
                                    p_text = await p_element.text_content()
                                    if p_text and p_text.strip() == repo_name_only:
                                        repo_button = button
                                        print(f"Found repository '{repo_name_only}' in fallback search with container: {container_selector}")
                                        
                                        # Scroll into view immediately when found in fallback
                                        try:
                                            await repo_button.scroll_into_view_if_needed()
                                            await self.page.wait_for_timeout(500)
                                            print("Scrolled fallback repository button into view")
                                        except Exception as scroll_error:
                                            print(f"Warning: Could not scroll fallback button into view: {scroll_error}")
                                        
                                        break
                            except:
                                continue
                        
                        if repo_button:
                            break
                            
                    except Exception as e:
                        print(f"Container selector {container_selector} failed: {str(e)}")
                        continue
            
            if repo_button:
                print(f"Found repository '{repo_name_only}', scrolling into view and clicking...")
                
                # Scroll the element into view before clicking
                try:
                    await repo_button.scroll_into_view_if_needed()
                    await self.page.wait_for_timeout(1000)  # Wait for scroll to complete
                    print("Scrolled repository button into view")
                    
                    # Alternative scroll method using JavaScript if needed
                    try:
                        await repo_button.evaluate("element => element.scrollIntoView({behavior: 'smooth', block: 'center'})")
                        await self.page.wait_for_timeout(500)
                        print("Additional JS scroll applied")
                    except:
                        pass
                        
                except Exception as scroll_error:
                    print(f"Warning: Could not scroll into view: {scroll_error}")
                
                # Ensure the button is still visible and clickable after scrolling
                is_visible = await repo_button.is_visible()
                is_enabled = await repo_button.is_enabled()
                print(f"After scrolling - Visible: {is_visible}, Enabled: {is_enabled}")
                
                if is_visible and is_enabled:
                    # Use JavaScript click as backup if normal click fails
                    try:
                        await repo_button.click()
                        print(f"Successfully clicked on repository '{repo_name_only}' with normal click")
                    except Exception as click_error:
                        print(f"Normal click failed, trying JavaScript click: {click_error}")
                        try:
                            await repo_button.evaluate("element => element.click()")
                            print(f"Successfully clicked on repository '{repo_name_only}' with JavaScript click")
                        except Exception as js_click_error:
                            print(f"JavaScript click also failed: {js_click_error}")
                            return False
                    
                    await self.page.wait_for_timeout(2000)
                else:
                    print(f"ERROR: Repository button not clickable after scrolling (visible: {is_visible}, enabled: {is_enabled})")
                    return False
                
                # Now click the final "Create environment" button
                final_create_selectors = [
                    "div.flex.items-center.justify-center:text('Create environment')",  # Most specific div selector
                    "div:text('Create environment')",  # Generic div with exact text
                    "div.flex.items-center.justify-center:has-text('Create environment')",  # Has-text version
                    "div:has-text('Create environment')",  # Generic div with text
                    "button.btn.btn-primary.ms-auto",  # Most specific class-based selector
                    "button.btn-primary",  # Primary button selector
                    "button:has(div:text('Create environment'))",  # Nested text selector
                    ".btn.btn-primary"  # Fallback class selector
                ]
                
                create_button = None
                for create_selector in final_create_selectors:
                    try:
                        print(f"Trying create button selector: {create_selector}")
                        create_button = await self.page.query_selector(create_selector)
                        if create_button:
                            is_visible = await create_button.is_visible()
                            is_enabled = await create_button.is_enabled()
                            
                            print(f"Found create button with selector: {create_selector}")
                            print(f"  - Visible: {is_visible}")
                            print(f"  - Enabled: {is_enabled}")
                            
                            if is_visible and is_enabled:
                                break
                            else:
                                print(f"Button found but not clickable (visible: {is_visible}, enabled: {is_enabled})")
                                create_button = None
                    except Exception as e:
                        print(f"Error with selector {create_selector}: {str(e)}")
                        continue
                
                if create_button:
                    try:
                        print("Scrolling create environment button into view...")
                        # Scroll into view
                        await create_button.scroll_into_view_if_needed()
                        await self.page.wait_for_timeout(1000)
                        
                        # Additional JavaScript scroll for better positioning
                        await create_button.evaluate("element => element.scrollIntoView({behavior: 'smooth', block: 'center'})")
                        await self.page.wait_for_timeout(500)
                        
                        # Verify still clickable after scroll
                        is_visible = await create_button.is_visible()
                        is_enabled = await create_button.is_enabled()
                        print(f"After scrolling - Visible: {is_visible}, Enabled: {is_enabled}")
                        
                        if is_visible and is_enabled:
                            # Try normal click first
                            try:
                                print("Clicking final 'Create environment' button with normal click")
                                await create_button.click()
                                print("Successfully clicked create environment button")
                            except Exception as click_error:
                                print(f"Normal click failed, trying JavaScript click: {click_error}")
                                await create_button.evaluate("element => element.click()")
                                print("Successfully clicked create environment button with JavaScript")
                            
                            # Wait for redirect to the environment page with "Use this" button
                            print("Waiting for redirect to environment page...")
                            await self._wait_for_redirect_to_environment_page()
                            
                            return True
                        else:
                            print(f"Create button not clickable after scroll (visible: {is_visible}, enabled: {is_enabled})")
                    except Exception as final_click_error:
                        print(f"Failed to click create environment button: {final_click_error}")
                else:
                    # Final fallback: search for any element containing "Create environment" text
                    print("Trying final fallback search for 'Create environment' text...")
                    try:
                        all_elements = await self.page.query_selector_all("div, button")
                        for element in all_elements:
                            try:
                                text_content = await element.text_content()
                                if text_content and "Create environment" in text_content.strip():
                                    # Check if this is likely the right element (not too much text)
                                    if len(text_content.strip()) < 50:  # Reasonable text length
                                        is_visible = await element.is_visible()
                                        is_enabled = await element.is_enabled()
                                        
                                        if is_visible and is_enabled:
                                            print(f"Found create environment element in fallback: {text_content.strip()}")
                                            
                                            # Scroll and click
                                            await element.scroll_into_view_if_needed()
                                            await self.page.wait_for_timeout(500)
                                            
                                            try:
                                                await element.click()
                                                print("Successfully clicked create environment in fallback")
                                                await self._wait_for_redirect_to_environment_page()
                                                return True
                                            except:
                                                await element.evaluate("element => element.click()")
                                                print("Successfully clicked create environment in fallback with JS")
                                                await self._wait_for_redirect_to_environment_page()
                                                return True
                            except:
                                continue
                    except Exception as fallback_error:
                        print(f"Fallback search failed: {fallback_error}")
                    
                    print("ERROR: Could not find create environment button with any method")
                    return False
            else:
                print(f"Repository '{repo_name_only}' not found in creation list")
                return False
            
        except Exception as e:
            print(f"ERROR: Failed to select repository from creation list: {str(e)}")
            return False

    async def _handle_environments_page_flow(self) -> bool:
        """Handle the complete environments page flow to get to Codex with the right repo"""
        try:
            # Get the repository URL from the agent context
            working_repo_url = self.get_working_repo_url()
            if not working_repo_url:
                print("WARNING: No repository URL provided, proceeding without repo selection")
                return True
            
            repo_name = self._extract_repo_name_from_url(working_repo_url)
            if not repo_name:
                print(f"WARNING: Could not extract repository name from URL: {working_repo_url}")
                return True
            
            print(f"Handling environments page for repository: {repo_name}")
            
            # Check if we're already on the environment creation page
            current_url = self.page.url
            if 'settings/environment/create' in current_url:
                print("Already on environment creation page, selecting repository...")
                # Extract just the repo name (without username) for the creation list
                repo_name_only = self._extract_repo_name_only(working_repo_url)
                if not repo_name_only:
                    print(f"WARNING: Could not extract repo name from URL: {working_repo_url}")
                    repo_name_only = repo_name.split('/')[-1] if '/' in repo_name else repo_name
                
                print(f"Looking for repository name: '{repo_name_only}' (extracted from {working_repo_url})")
                
                # Select repo from creation list and create environment
                if not await self._select_repo_from_creation_list(repo_name_only):
                    print("ERROR: Failed to select repository from creation list")
                    return False
                
                # Wait for redirect and then click "Use this" button on the new environment page
                if await self._wait_for_redirect_to_environment_page():
                    if await self._click_use_this_button():
                        print("Successfully created and selected new environment")
                        return True
                    else:
                        print("ERROR: Created environment but failed to click 'Use this' button")
                        return False
                else:
                    print("ERROR: Failed to reach environment page after creation")
                    return False
            
            # Wait for the environments page to load
            await self.page.wait_for_timeout(3000)
            
            # Try to find the repo in existing environments
            if await self._find_repo_in_environments_table(repo_name):
                # Repo found, click "Use this" button
                if await self._click_use_this_button():
                    print("Successfully selected existing environment")
                    return True
                else:
                    print("ERROR: Found repo but failed to click 'Use this' button")
                    return False
            
            # Repo not found, need to create new environment
            print("Repository not found in existing environments, creating new one...")
            
            if not await self._click_create_environment_button():
                print("ERROR: Failed to click 'Create environment' button")
                return False
            
            # Extract just the repo name (without username) for the creation list
            repo_name_only = self._extract_repo_name_only(working_repo_url)
            if not repo_name_only:
                print(f"WARNING: Could not extract repo name from URL: {working_repo_url}")
                repo_name_only = repo_name.split('/')[-1] if '/' in repo_name else repo_name
            
            print(f"Looking for repository name: '{repo_name_only}' (extracted from {working_repo_url})")
            
            # Select repo from creation list and create environment
            if not await self._select_repo_from_creation_list(repo_name_only):
                print("ERROR: Failed to select repository from creation list")
                return False
            
            # The environment was created in _select_repo_from_creation_list, 
            # which already handles redirect and clicking "Use this"
            print("Successfully created and selected new environment")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to handle environments page flow: {str(e)}")
            return False

    async def _setup_web_interface(self) -> bool:
        """Handle the complete authentication flow to reach OpenAI Codex"""
        try:
            print(f"Setting up OpenAI Codex interface...")
            
            # Check current URL to determine what step we're on
            current_url = self.page.url
            print(f"Current URL: {current_url}")
            
            # Step 1: Check if we're already authenticated and on environments page
            if await self._is_authenticated():
                print("Already authenticated and at environments page!")
                return await self._handle_environments_page_flow()
            
            # Step 2: Handle login/signup page
            if 'chatgpt.com' in current_url and ('auth/login' in current_url or await self._is_login_signup_page()):
                print("On login/signup page, clicking Log in...")
                if not await self._click_login_button():
                    return False
                
                # Wait for redirect to OpenAI auth
                await self.page.wait_for_timeout(3000)
                current_url = self.page.url
                print(f"After login click, URL: {current_url}")
            
            # Step 3: Handle OpenAI auth page
            if 'auth.openai.com' in current_url:
                print("On OpenAI auth page, looking for Continue with Google...")
                if not await self._click_continue_with_google():
                    return False
                
                # Wait for Google auth redirect
                await self.page.wait_for_timeout(3000)
                current_url = self.page.url
                print(f"After Google button click, URL: {current_url}")
            
            # Step 4: Handle Google login if redirected there
            if 'accounts.google.com' in current_url:
                print("Redirected to Google login, handling authentication...")
                if not await self.handle_google_login():
                    return False
                
                # Wait for redirect back to OpenAI environments page
                await self.page.wait_for_timeout(5000)
                current_url = self.page.url
                print(f"After Google login, URL: {current_url}")
            
            # Step 5: Handle environments page flow
            if await self._is_authenticated():
                print("Successfully reached environments page!")
                return await self._handle_environments_page_flow()
            
            # Step 6: Check if we ended up directly at main Codex page (skip environments)
            if ('chatgpt.com/codex' in current_url and 
                'settings/environments' not in current_url and 
                'settings/environment' not in current_url):
                print("Directly reached Codex page, verifying interface...")
                return await self._verify_codex_interface()
            
            print(f"ERROR: Unexpected final URL: {current_url}")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to setup OpenAI Codex interface: {str(e)}")
            return False

    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute a prompt on OpenAI Codex interface"""
        try:
            print(f"Executing prompt on OpenAI Codex: {prompt[:100]}...")
            
            # First ensure we're properly set up and authenticated
            if not await self._setup_web_interface():
                return AgentResponse(
                    content="",
                    success=False,
                    error_message="Failed to setup OpenAI Codex interface"
                )
            
            # Wait for interface to be ready
            await self.page.wait_for_timeout(2000)
            
            # Send the prompt
            await self._send_prompt_to_interface(prompt)
            
            # Wait for task creation and click on it
            task_url = await self._wait_for_task_creation_and_click()
            
            if task_url:
                # Read the output from the task chat interface
                output = await self._read_task_chat_output()
                
                return AgentResponse(
                    content=f"Task created and opened successfully. {output}",
                    success=True
                )
            else:
                return AgentResponse(
                    content="Task was submitted but could not open task chat",
                    success=False,
                    error_message="Failed to click on created task"
                )
            
        except Exception as e:
            print(f"ERROR: Failed to execute prompt: {str(e)}")
            return AgentResponse(
                content="",
                success=False,
                error_message=str(e)
            )

    async def _send_prompt_to_interface(self, prompt: str):
        """Send prompt to the Codex interface"""
        try:
            print("Filling prompt input field...")
            
            # Wait for the input field to be available
            await self.page.wait_for_selector(self.input_selector, timeout=10000)
            
            # Clear any existing content and type the prompt
            input_field = await self.page.query_selector(self.input_selector)
            if input_field:
                # Clear the field first
                await input_field.click()
                await self.page.keyboard.press("Control+a")  # Select all
                await self.page.keyboard.press("Delete")  # Delete selection
                
                # Type the new prompt
                await input_field.fill(prompt)
                print(f"Successfully entered prompt: {prompt[:50]}...")
                
                # Wait a moment for the interface to process the input
                await self.page.wait_for_timeout(1000)
                
                # Now click the Code/Submit button
                await self._click_code_button()
            else:
                raise Exception("Could not find prompt input field")
                
        except Exception as e:
            print(f"ERROR: Failed to send prompt to interface: {str(e)}")
            raise

    async def _click_code_button(self) -> bool:
        """Click the Code button to submit the task"""
        try:
            print("Looking for Code button...")
            
            # Try multiple possible selectors for the Code button
            code_button_selectors = [
                "button:has-text('Code')",
                "button:contains('Code')", 
                "button[aria-label*='Code']",
                "button[title*='Code']",
                "[data-testid*='code']",
                "button[type='submit']",
                # Fallback to any submit-like button near the input
                "form button[type='submit']",
                ".composer-btn",
                "button[data-testid='send-button']"
            ]
            
            for selector in code_button_selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        # Check if button is visible and enabled
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            print(f"Found Code button with selector: {selector}")
                            await button.click()
                            print("Successfully clicked Code button")
                            return True
                except Exception as selector_error:
                    print(f"Selector {selector} failed: {selector_error}")
                    continue
            
            # If no specific Code button found, try Enter key as fallback
            print("No Code button found, trying Enter key...")
            await self.page.keyboard.press("Enter")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to click Code button: {str(e)}")
            return False

    async def _wait_for_task_creation_and_click(self) -> Optional[str]:
        """Wait for task creation and click on it to open the chat"""
        try:
            print("Waiting for task creation...")
            
            # Wait for any loading indicators to appear and then disappear
            try:
                # First wait for loading to start
                await self.page.wait_for_selector(self.loading_selector, timeout=5000)
                print("Loading indicator detected...")
                
                # Then wait for loading to finish
                await self.page.wait_for_selector(self.loading_selector, state="hidden", timeout=30000)
                print("Loading completed")
            except:
                print("No loading indicator detected, continuing...")
            
            # Wait a bit for the interface to update
            await self.page.wait_for_timeout(3000)
            
            # Look for the newly created task
            print("Looking for newly created task...")
            task_link = await self._find_and_click_latest_task()
            
            if task_link:
                print(f"Successfully clicked on task: {task_link}")
                # Wait for task page to load
                return task_link
            else:
                print("Could not find or click on created task")
                return None
            
        except Exception as e:
            print(f"ERROR: Error while waiting for task creation: {str(e)}")
            return None

    async def _find_and_click_latest_task(self) -> Optional[str]:
        """Find and click on the most recently created task"""
        try:
            # Look for task rows/containers
            task_selectors = [
                ".task-row-container a",  # Based on the HTML structure
                ".group.task-row-container a",
                "[href*='/tasks/']",  # Any link containing /tasks/
                "a[href*='task_e_']"  # Specific task links
            ]
            
            for selector in task_selectors:
                try:
                    task_links = await self.page.query_selector_all(selector)
                    if task_links:
                        # Click on the first (most recent) task
                        first_task = task_links[0]
                        task_href = await first_task.get_attribute('href')
                        print(f"Found task link with selector {selector}: {task_href}")
                        
                        # Click on the task
                        await first_task.click()
                        
                        # Wait for navigation
                        await self.page.wait_for_timeout(2000)
                        
                        return task_href
                except Exception as selector_error:
                    print(f"Selector {selector} failed: {selector_error}")
                    continue
            
            # If no task links found, try to find by text content
            print("No task links found with standard selectors, trying text-based search...")
            try:
                # Look for elements containing task-like text
                all_links = await self.page.query_selector_all("a")
                for link in all_links:
                    href = await link.get_attribute('href')
                    if href and '/tasks/' in href:
                        print(f"Found task link by href search: {href}")
                        await link.click()
                        await self.page.wait_for_timeout(2000)
                        return href
            except:
                pass
            
            print("No task links found")
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to find and click latest task: {str(e)}")
            return None

    async def _read_task_chat_output(self) -> str:
        """Read output from the task chat interface after completion"""
        try:
            current_url = self.page.url
            print(f"Reading output from task page: {current_url}")
            
            # Wait for the chat interface to load
            await self.page.wait_for_timeout(3000)
            
            # Focus on the input to ensure we're in the right context
            await self._focus_chat_input()
            
            # Wait for chat completion
            await self._wait_for_chat_completion()
            
            # Click the Create PR button if available
            await self._click_create_pr_button()
            
            # Wait for "View PR" button and extract PR link
            pr_url = await self._wait_for_view_pr_and_extract_link()
            
            if pr_url:
                return f"Task completed successfully. PR created: {pr_url}"
            else:
                return "Task completed successfully, but PR link could not be extracted."
            
        except Exception as e:
            print(f"WARNING: Could not read task chat output: {str(e)}")
            return f"Task opened successfully. Current URL: {self.page.url}"

    async def _focus_chat_input(self) -> bool:
        """Focus on the chat input box to ensure we're in the right context"""
        try:
            print("Focusing on chat input box...")
            
            # Look for the input field with placeholder "Request changes or ask a question"
            input_selectors = [
                "#prompt-textarea[placeholder*='Request changes']",
                "#prompt-textarea",
                "textarea[placeholder*='Request changes']",
                "textarea[placeholder*='ask a question']",
                "[contenteditable='true'][id='prompt-textarea']",
                ".ProseMirror[contenteditable='true']"
            ]
            
            for selector in input_selectors:
                try:
                    input_field = await self.page.query_selector(selector)
                    if input_field:
                        print(f"Found chat input with selector: {selector}")
                        await input_field.click()
                        await self.page.wait_for_timeout(1000)
                        return True
                except:
                    continue
            
            print("WARNING: Could not find chat input field")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to focus chat input: {str(e)}")
            return False

    async def _wait_for_chat_completion(self) -> bool:
        """Wait for the chat to complete by monitoring the stop button"""
        try:
            print("Waiting for chat completion...")
            
            # First, wait for the stop button to appear (indicating chat is running)
            stop_button_selector = "button[aria-label='stop-button'], button[data-testid='stop-button']"
            
            try:
                print("Looking for stop button to appear...")
                await self.page.wait_for_selector(stop_button_selector, timeout=30000)
                print("Stop button detected - chat is running")
            except:
                print("No stop button found initially - chat may not be running or already completed")
                return True
            
            # Now wait for the stop button to disappear (indicating completion)
            try:
                print("Waiting for stop button to disappear...")
                await self.page.wait_for_selector(stop_button_selector, state="hidden", timeout=300000)  # 5 minute timeout
                print("Stop button disappeared - chat has completed!")
                
                # Wait a moment for the interface to fully update
                await self.page.wait_for_timeout(2000)
                return True
                
            except Exception as timeout_error:
                print(f"Timeout waiting for chat completion: {timeout_error}")
                # Continue anyway in case the button selector changed
                return True
            
        except Exception as e:
            print(f"ERROR: Error while waiting for chat completion: {str(e)}")
            return False

    async def _click_create_pr_button(self) -> bool:
        """Click the Create PR button if it appears after chat completion"""
        try:
            print("Looking for Create PR button...")
            
            # Wait for the Create PR button to appear
            pr_button_selectors = [
                "div.btn-primary button:has(span:text('Create PR'))",  # Specific nested selector
                "button.rounded-s-full:has(span:text('Create PR'))",   # Button with specific class
                "div.btn-primary button.rounded-s-full",              # Container + button classes
                "button:has(span.truncate:text('Create PR'))",        # Target span with text
                ".btn-primary button",                                # Simple fallback
                "div[class*='btn-primary'] button"                    # Partial class match
            ]
            
            for selector in pr_button_selectors:
                try:
                    # Wait for button to appear with timeout
                    await self.page.wait_for_selector(selector, timeout=10000)
                    pr_button = await self.page.query_selector(selector)
                    
                    if pr_button:
                        is_visible = await pr_button.is_visible()
                        is_enabled = await pr_button.is_enabled()
                        
                        print(f"Found Create PR button with selector: {selector}")
                        print(f"  - Visible: {is_visible}")
                        print(f"  - Enabled: {is_enabled}")
                        
                        if is_visible and is_enabled:
                            print("Clicking Create PR button")
                            await pr_button.click()
                            
                            # Wait for PR creation to process
                            await self.page.wait_for_timeout(3000)
                            print("Successfully clicked Create PR button")
                            return True
                        else:
                            print(f"Create PR button found but not clickable (visible: {is_visible}, enabled: {is_enabled})")
                            
                except Exception as selector_error:
                    print(f"Selector {selector} failed: {selector_error}")
                    continue
            
            print("INFO: Create PR button not found or not ready - this may be normal if PR creation is not needed")
            return False
            
        except Exception as e:
            print(f"WARNING: Error while looking for Create PR button: {str(e)}")
            return False

    async def _wait_for_view_pr_and_extract_link(self) -> Optional[str]:
        """Wait for the 'View PR' button to appear and extract the PR link"""
        try:
            print("Waiting for 'View PR' button to appear...")
            
            # Wait for the View PR button to appear
            view_pr_selectors = [
                "a:has(span:text('View PR'))",  # Link containing span with "View PR" text
                "a:has(span.truncate:text('View PR'))",  # More specific with truncate class
                ".btn-primary a[href*='github.com']:has(span:text('View PR'))",  # Within btn-primary container
                "a[href*='/pull/']:has(span:text('View PR'))",  # Link to PR with View PR text
                "a[href*='github.com'][href*='/pull/']"  # Any GitHub PR link
            ]
            
            for selector in view_pr_selectors:
                try:
                    print(f"Checking for View PR button with selector: {selector}")
                    
                    # Wait for button to appear with timeout
                    await self.page.wait_for_selector(selector, timeout=30000)  # 30 second timeout
                    pr_link = await self.page.query_selector(selector)
                    
                    if pr_link:
                        is_visible = await pr_link.is_visible()
                        href = await pr_link.get_attribute('href')
                        
                        print(f"Found View PR button with selector: {selector}")
                        print(f"  - Visible: {is_visible}")
                        print(f"  - Href: {href}")
                        
                        if is_visible and href and 'github.com' in href and '/pull/' in href:
                            print(f"Successfully extracted PR link: {href}")
                            return href
                        else:
                            print(f"View PR button found but invalid link (visible: {is_visible}, href: {href})")
                            
                except Exception as selector_error:
                    print(f"Selector {selector} failed: {selector_error}")
                    continue
            
            # Fallback: Look for any GitHub PR links without specific button selectors
            print("Trying fallback search for any GitHub PR links...")
            try:
                all_links = await self.page.query_selector_all("a[href*='github.com']")
                for link in all_links:
                    href = await link.get_attribute('href')
                    if href and '/pull/' in href:
                        print(f"Found GitHub PR link in fallback search: {href}")
                        return href
            except Exception as fallback_error:
                print(f"Fallback search failed: {fallback_error}")
            
            print("INFO: View PR button not found - this may be normal if PR creation is not needed")
            return None
            
        except Exception as e:
            print(f"WARNING: Error while waiting for View PR button: {str(e)}")
            return None
    
    async def _is_login_signup_page(self) -> bool:
        """Check if we're on the login/signup page by looking for characteristic elements"""
        try:
            # Look for the "Get started" heading and login/signup buttons
            page_text = await self.page.content() if hasattr(self.page, 'content') else ""
            return ("Get started" in page_text and 
                    "Log in" in page_text and 
                    "Sign up for free" in page_text)
        except:
            return False
    
    async def _click_login_button(self) -> bool:
        """Click the Log in button on the OpenAI landing page"""
        try:
            # Try multiple selectors for the login button
            login_selectors = [
                "button[data-testid='login-button']",
                "button:has-text('Log in')",
                "button:contains('Log in')",
                ".btn:has-text('Log in')"
            ]
            
            for selector in login_selectors:
                try:
                    login_button = await self.page.query_selector(selector)
                    if login_button:
                        print(f"Found login button with selector: {selector}")
                        await login_button.click()
                        return True
                except:
                    continue
            
            print("ERROR: Could not find login button")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to click login button: {str(e)}")
            return False
    
    async def _click_continue_with_google(self) -> bool:
        """Click the Continue with Google button on OpenAI auth page"""
        try:
            # Wait for the page to load
            await self.page.wait_for_timeout(2000)
            
            # Try multiple selectors for Google login button
            google_selectors = [
                "button:has-text('Continue with Google')",
                "button:has-text('Sign in with Google')",
                "button:contains('Google')",
                "[data-provider='google']",
                ".social-button:has-text('Google')",
                "button[data-testid='google-login']"
            ]
            
            for selector in google_selectors:
                try:
                    google_button = await self.page.query_selector(selector)
                    if google_button:
                        print(f"Found Google login button with selector: {selector}")
                        await google_button.click()
                        return True
                except:
                    continue
            
            print("ERROR: Could not find Continue with Google button")
            return False
            
        except Exception as e:
            print(f"ERROR: Failed to click Continue with Google button: {str(e)}")
            return False
    
    async def _verify_codex_interface(self) -> bool:
        """Verify we're on the Codex interface and it's ready"""
        try:
            # Wait for the interface to load
            await self.page.wait_for_timeout(3000)
            
            # Look for the prompt input field
            try:
                await self.page.wait_for_selector(self.input_selector, timeout=10000)
                print(f"Found Codex interface input field")
                return True
            except:
                print("Could not find prompt input field")
            
            # Fallback: check for other interface elements
            interface_selectors = [
                "textarea[placeholder*='task']",
                "textarea[placeholder*='Ask']",
                "textarea[placeholder*='Type']",
                "[data-testid='composer-input']"
            ]
            
            for selector in interface_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    print(f"Found Codex interface with selector: {selector}")
                    return True
                except:
                    continue
            
            print("WARNING: Could not verify Codex interface elements")
            # Return True anyway since we're at the right URL
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to verify Codex interface: {str(e)}")
            return False 