#!/usr/bin/env python3
"""
OpenAI Codex Web Agent Implementation

Simplified and maintainable implementation for accessing OpenAI Codex.
Core flow: Login → Environments → Repository Selection → Task Execution → PR Creation
"""

import re
import time
from typing import Optional
from .web_agent import WebAgent, AgentResponse


# Selector constants for better maintainability
class CodexSelectors:
    # Authentication (PROVEN WORKING)
    LOGIN_BUTTON = "button[data-testid='login-button']"
    GOOGLE_BUTTON = "button:has-text('Continue with Google')"
    
    # Input and submission (PROVEN WORKING)
    PROMPT_INPUT = "#prompt-textarea"
    CODE_BUTTON = "button:has-text('Code')"
    CHAT_INPUT = "#prompt-textarea"  # Same as prompt input, placeholder check failed
    
    # Environment management (PROVEN WORKING)
    USE_THIS_BUTTON = "button:has-text('Use this')"
    CREATE_ENV_BUTTON = "button.btn-primary"  # Simple version worked, complex one failed
    
    # Repository selection (PROVEN WORKING)
    EXISTING_REPO_ROW = "tr.group\\/row:has-text('{repo_name}')"  # For existing environments
    NEW_REPO_BUTTON = "button:has(p.text-token-text-primary.text-start.text-sm.font-medium:text('{repo_name}'))"  # For new environments
    FINAL_CREATE_BUTTON = "div.flex.items-center.justify-center:text('Create environment')"  # Final create step
    REPO_LIST_CONTAINER = ".flex.max-h-56.flex-col.overflow-y-auto"  # Creation list container
    REPO_NAME_ELEMENTS = "button p.text-token-text-primary"  # For verification
    
    # Task and PR management (PROVEN WORKING)
    TASK_LINK = ".task-row-container a"
    STOP_BUTTON = "button[aria-label='stop-button'], button[data-testid='stop-button']"
    CREATE_PR_BUTTON = "div.btn-primary button:has(span:text('Create PR'))"
    VIEW_PR_LINK = "a:has(span:text('View PR'))"
    
    # Loading and status (PROVEN WORKING)
    LOADING = ".animate-pulse, .loading, [role='progressbar']"


class OpenAICodexAgent(WebAgent):
    """Simplified OpenAI Codex web agent"""
    
    def __init__(self, computer_use_client):
        super().__init__(computer_use_client)
    
    @property
    def web_url(self) -> str:
        return "https://chatgpt.com/auth/login?next=/codex/settings/environments"
    
    @property
    def input_selector(self) -> str:
        return CodexSelectors.PROMPT_INPUT
    
    @property
    def submit_selector(self) -> str:
        return CodexSelectors.CODE_BUTTON
    
    @property
    def output_selector(self) -> str:
        return CodexSelectors.TASK_LINK
    
    @property
    def loading_selector(self) -> Optional[str]:
        return CodexSelectors.LOADING

    # =============================================================================
    # CORE FLOW METHODS
    # =============================================================================

    async def _setup_web_interface(self) -> bool:
        """Main setup flow: authenticate and navigate to correct environment"""
        try:
            print("🚀 Starting OpenAI Codex setup...")
            
            # Step 1: Handle authentication if needed
            if not await self._handle_authentication():
                return False
            
            # Step 2: Handle environments page
            if not await self._handle_environments_page():
                return False
            
            print("✅ OpenAI Codex setup completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {str(e)}")
            return False

    async def execute_prompt(self, prompt: str) -> AgentResponse:
        """Execute a coding task on OpenAI Codex"""
        try:
            print(f"🎯 Executing task: {prompt[:100]}...")
            
            # Send prompt and create task
            await self._send_prompt(prompt)
            
            # Open the created task
            if not await self._open_created_task():
                return AgentResponse(content="", success=False, error_message="Failed to open task")
            
            # Wait for completion and get PR URL
            pr_url = await self._complete_task_and_get_pr()
            
            if pr_url:
                return AgentResponse(content=f"Task completed successfully. PR created: {pr_url}", success=True)
            else:
                return AgentResponse(content="Task completed but no PR created", success=True)
            
        except Exception as e:
            return AgentResponse(content="", success=False, error_message=str(e))

    # =============================================================================
    # AUTHENTICATION FLOW
    # =============================================================================

    async def _handle_authentication(self) -> bool:
        """Handle the complete authentication flow"""
        current_url = self.page.url
        print(f"📍 Current URL: {current_url}")
        
        # Check if already authenticated
        if self._is_environments_page(current_url):
            print("✅ Already authenticated")
            return True
        
        # Handle login page
        if 'auth/login' in current_url or await self._is_login_page():
            print("🔐 On login page, clicking login...")
            if not await self._click_element(CodexSelectors.LOGIN_BUTTON, "login button"):
                return False
            await self.page.wait_for_timeout(3000)
            current_url = self.page.url
        
        # Handle OpenAI auth page
        if 'auth.openai.com' in current_url:
            print("🔗 On OpenAI auth page, clicking Google login...")
            if not await self._click_element(CodexSelectors.GOOGLE_BUTTON, "Google login button"):
                return False
            await self.page.wait_for_timeout(3000)
            current_url = self.page.url
        
        # Handle Google authentication
        if 'accounts.google.com' in current_url:
            print("🔑 Handling Google authentication...")
            if not await self.handle_google_login():
                return False
            await self.page.wait_for_timeout(5000)
        
        # Verify we reached environments page
        return self._is_environments_page(self.page.url)

    async def _is_login_page(self) -> bool:
        """Check if we're on a login/signup page"""
        try:
            page_text = await self.page.content()
            return all(text in page_text for text in ["Get started", "Log in", "Sign up"])
        except:
            return False

    def _is_environments_page(self, url: str) -> bool:
        """Check if we're on the environments page"""
        return 'chatgpt.com/codex/settings/environment' in url

    # =============================================================================
    # ENVIRONMENTS AND REPOSITORY MANAGEMENT
    # =============================================================================

    async def _handle_environments_page(self) -> bool:
        """Handle environment selection or creation for the repository"""
        repo_url = self.get_working_repo_url()
        if not repo_url:
            print("⚠️ No repository URL provided")
            return True
        
        repo_name = self._extract_repo_name(repo_url)
        print(f"🏗️ Setting up environment for repository: {repo_name}")
        
        # Check if we're already on environment creation page
        if 'settings/environment/create' in self.page.url:
            print("📍 Already on environment creation page")
            return await self._create_new_environment(repo_name)
        
        # Look for existing environment
        if await self._find_and_select_existing_environment(repo_name):
            print("✅ Found and selected existing environment")
            return True
        
        # Create new environment
        print("📝 Repository not found, creating new environment...")
        if not await self._click_element(CodexSelectors.CREATE_ENV_BUTTON, "create environment button"):
            print("❌ Failed to click create environment button, trying fallback method...")
            # Try the more detailed method as fallback
            if not await self._click_create_environment_final():
                print("❌ All create environment button methods failed")
                return False
        
        return await self._create_new_environment(repo_name)

    async def _find_and_select_existing_environment(self, repo_name: str) -> bool:
        """Find and select an existing environment"""
        try:
            # Look for repository in environments table using proven selector
            repo_selector = CodexSelectors.EXISTING_REPO_ROW.format(repo_name=repo_name)
            element = await self.page.query_selector(repo_selector)
            
            if element:
                print(f"✅ Found existing environment for {repo_name}")
                await element.click()
                await self.page.wait_for_timeout(2000)
                return await self._click_element(CodexSelectors.USE_THIS_BUTTON, "Use this button")
            
            # Fallback: try simpler selectors
            fallback_selectors = [
                f"td:has-text('{repo_name}')",
                f"div:has-text('{repo_name}')"
            ]
            
            for selector in fallback_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    print(f"✅ Found existing environment with fallback: {selector}")
                    await element.click()
                    await self.page.wait_for_timeout(2000)
                    return await self._click_element(CodexSelectors.USE_THIS_BUTTON, "Use this button")
            
            return False
        except Exception as e:
            print(f"❌ Error finding existing environment: {str(e)}")
            return False

    async def _create_new_environment(self, repo_name: str) -> bool:
        """Create a new environment by selecting repository"""
        try:
            # Wait for repository creation list to load (proven from logs)
            await self._wait_for_element(CodexSelectors.REPO_LIST_CONTAINER, "creation list container")
            await self._wait_for_element(CodexSelectors.REPO_NAME_ELEMENTS, "repository list")
            await self.page.wait_for_timeout(2000)  # Allow list to fully populate
            
            # Wait for at least one repository button to become available
            print("⏳ Waiting for repository buttons to become available...")
            await self.page.wait_for_selector("button p.text-token-text-primary", timeout=10000)
            print("✅ Repository buttons are available")
            
            # Find and click repository using proven selector
            repo_only = repo_name.split('/')[-1] if '/' in repo_name else repo_name
            repo_selector = CodexSelectors.NEW_REPO_BUTTON.format(repo_name=repo_only)
            
            print(f"🔍 Looking for repository: {repo_only}")
            element = await self.page.query_selector(repo_selector)
            
            if element and await element.is_visible():
                print(f"✅ Found repository with proven selector")
                await self._scroll_and_click(element, f"repository {repo_only}")
            else:
                # Use fallback search if proven selector doesn't work
                if not await self._fallback_repository_search(repo_only):
                    return False
            
            # Click final create button using proven selector
            await self.page.wait_for_timeout(2000)
            final_create_element = await self.page.query_selector(CodexSelectors.FINAL_CREATE_BUTTON)
            
            if final_create_element and await final_create_element.is_visible():
                print("✅ Found final create environment button")
                await self._scroll_and_click(final_create_element, "final create environment button")
            else:
                print("❌ Final create environment button not found")
                return False
            
            # Wait for redirect and click "Use this"
            await self._wait_for_redirect()
            return await self._click_element(CodexSelectors.USE_THIS_BUTTON, "Use this button")
            
        except Exception as e:
            print(f"❌ Failed to create environment: {str(e)}")
            return False

    async def _fallback_repository_search(self, repo_name: str) -> bool:
        """Fallback method to find repository by searching all buttons"""
        try:
            print(f"🔍 Using fallback search for repository: {repo_name}")
            buttons = await self.page.query_selector_all("button")
            for button in buttons:
                try:
                    p_element = await button.query_selector("p.text-token-text-primary")
                    if p_element:
                        text = await p_element.text_content()
                        if text and text.strip() == repo_name:
                            print(f"✅ Found repository in fallback search")
                            await self._scroll_and_click(button, f"repository {repo_name}")
                            return True
                except:
                    continue
            return False
        except:
            return False

    async def _click_create_environment_final(self) -> bool:
        """Click the final Create environment button (fallback method)"""
        try:
            # Try the proven final create button selector first
            element = await self.page.query_selector(CodexSelectors.FINAL_CREATE_BUTTON)
            if element and await element.is_visible() and await element.is_enabled():
                print(f"✅ Found final create environment button")
                await self._scroll_and_click(element, "final create environment button")
                return True
            
            # Fallback to the basic create button
            element = await self.page.query_selector(CodexSelectors.CREATE_ENV_BUTTON)
            if element and await element.is_visible() and await element.is_enabled():
                print(f"✅ Found create environment button (fallback)")
                await self._scroll_and_click(element, "create environment button")
                return True
            else:
                print(f"❌ No create environment button found")
                return False
        except Exception as e:
            print(f"❌ Failed to find create environment button: {str(e)}")
            return False

    async def _wait_for_redirect(self):
        """Wait for redirect to environment page"""
        await self.page.wait_for_timeout(3000)
        await self._wait_for_element(CodexSelectors.USE_THIS_BUTTON, "Use this button")

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extract repository name from GitHub URL"""
        if not repo_url:
            return ""
        
        pattern = r'github\.com[/:]([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?/?$'
        match = re.search(pattern, repo_url)
        
        if match:
            username, repo_name = match.groups()
            return f"{username}/{repo_name}"
        
        return ""

    # =============================================================================
    # TASK EXECUTION FLOW
    # =============================================================================

    async def _send_prompt(self, prompt: str):
        """Send prompt to the Codex interface"""
        print("📝 Sending prompt to Codex...")
        
        # Wait for and fill input field
        await self._wait_for_element(CodexSelectors.PROMPT_INPUT, "prompt input")
        input_field = await self.page.query_selector(CodexSelectors.PROMPT_INPUT)
        
        await input_field.click()
        await self.page.keyboard.press("Control+a")
        await input_field.fill(prompt)
        print(f"✅ Prompt entered: {prompt[:50]}...")
        
        # Click Code button
        await self._click_element(CodexSelectors.CODE_BUTTON, "Code button")

    async def _open_created_task(self) -> bool:
        """Find and open the newly created task"""
        print("🔍 Looking for created task...")
        
        # Wait for loading to complete
        await self._wait_for_loading_complete()
        
        # Find and click task link
        await self.page.wait_for_timeout(3000)
        task_element = await self.page.query_selector(CodexSelectors.TASK_LINK)
        
        if task_element:
            href = await task_element.get_attribute('href')
            print(f"✅ Found task: {href}")
            await task_element.click()
            await self.page.wait_for_timeout(2000)
            return True
        
        print("❌ No task found")
        return False

    async def _complete_task_and_get_pr(self) -> Optional[str]:
        """Wait for task completion and extract PR URL"""
        print("⏳ Waiting for task completion...")
        
        # Focus on chat input
        await self._focus_chat_input()
        
        # Wait for completion (stop button disappears)
        await self._wait_for_completion()
        
        # Try to create PR
        await self._try_create_pr()
        
        # Extract PR URL
        return await self._extract_pr_url()

    async def _focus_chat_input(self):
        """Focus on the chat input field"""
        try:
            # Use proven chat input selector (same as prompt input)
            element = await self.page.query_selector(CodexSelectors.CHAT_INPUT)
            if element:
                print("✅ Focused on chat input")
                await element.click()
                await self.page.wait_for_timeout(1000)
            else:
                print("⚠️ Chat input field not found")
        except Exception as e:
            print(f"⚠️ Could not focus chat input: {str(e)}")

    async def _wait_for_completion(self):
        """Wait for task completion by monitoring stop button"""
        print("⏳ Monitoring task completion...")
        
        try:
            # Wait for stop button to appear (proven selector)
            await self.page.wait_for_selector(CodexSelectors.STOP_BUTTON, timeout=30000)
            print("🔄 Task is running...")
            
            # Wait for stop button to disappear (proven selector)
            await self.page.wait_for_selector(CodexSelectors.STOP_BUTTON, state="hidden", timeout=300000)
            print("✅ Task completed!")
            
        except:
            print("⚠️ Stop button monitoring failed, assuming completion")
        
        await self.page.wait_for_timeout(2000)

    async def _try_create_pr(self):
        """Try to click Create PR button if available"""
        try:
            await self.page.wait_for_selector(CodexSelectors.CREATE_PR_BUTTON, timeout=10000)
            element = await self.page.query_selector(CodexSelectors.CREATE_PR_BUTTON)
            
            if element and await element.is_visible():
                print("🔗 Creating PR...")
                await element.click()
                await self.page.wait_for_timeout(3000)
            
        except:
            print("ℹ️ No Create PR button found")

    async def _extract_pr_url(self) -> Optional[str]:
        """Extract PR URL from View PR button"""
        print("🔍 Looking for PR URL...")
        
        try:
            await self.page.wait_for_selector(CodexSelectors.VIEW_PR_LINK, timeout=30000)
            pr_link = await self.page.query_selector(CodexSelectors.VIEW_PR_LINK)
            
            if pr_link:
                href = await pr_link.get_attribute('href')
                if href and 'github.com' in href and '/pull/' in href:
                    print(f"✅ Found PR: {href}")
                    return href
                    
        except Exception as e:
            print(f"❌ No PR URL found: {str(e)}")
        
        return None

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

    async def _wait_for_element(self, selector: str, description: str, timeout: int = 10000):
        """Wait for an element to appear"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            print(f"✅ Found {description}")
        except:
            print(f"⚠️ Timeout waiting for {description}")

    async def _click_element(self, selector: str, description: str) -> bool:
        """Find and click an element with multiple strategies"""
        try:
            element = await self.page.query_selector(selector)
            if element and await element.is_visible() and await element.is_enabled():
                await element.click()
                print(f"✅ Clicked {description}")
                await self.page.wait_for_timeout(1000)
                return True
            
            print(f"❌ Could not click {description}")
            return False
            
        except Exception as e:
            print(f"❌ Error clicking {description}: {str(e)}")
            return False

    async def _scroll_and_click(self, element, description: str):
        """Scroll element into view and click it"""
        try:
            await element.scroll_into_view_if_needed()
            await self.page.wait_for_timeout(500)
            
            try:
                await element.click()
                print(f"✅ Clicked {description}")
            except:
                await element.evaluate("element => element.click()")
                print(f"✅ JS clicked {description}")
                
        except Exception as e:
            print(f"❌ Failed to click {description}: {str(e)}")

    async def _wait_for_loading_complete(self):
        """Wait for any loading indicators to complete"""
        try:
            # Use proven loading selector from logs
            await self.page.wait_for_selector(CodexSelectors.LOADING, timeout=5000)
            print("🔄 Loading detected, waiting for completion...")
            await self.page.wait_for_selector(CodexSelectors.LOADING, state="hidden", timeout=30000)
            print("✅ Loading completed")
        except:
            print("ℹ️ No loading indicator found or already completed") 