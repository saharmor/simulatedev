#!/usr/bin/env python3
"""
OpenAI Codex Web Agent Implementation

This agent handles authentication flow to access OpenAI Codex at chatgpt.com/codex
"""

from typing import Optional
from .web_agent import WebAgent, AgentResponse


class OpenAICodexAgent(WebAgent):
    """OpenAI Codex web agent with authentication handling"""
    
    def __init__(self, computer_use_client):
        super().__init__(computer_use_client)
    
    @property
    def web_url(self) -> str:
        """Start with the login URL that redirects to codex"""
        return "https://chatgpt.com/auth/login?next=/codex"
    
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
                await input_field.type(prompt)
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
            
            # Now read the completed chat output
            output = await self._read_completed_chat_content()
            
            return output
            
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

    async def _read_completed_chat_content(self) -> str:
        """Read the completed chat content after the stop button has disappeared"""
        try:
            print("Reading completed chat content...")
            
            # Look for chat messages or task content
            chat_selectors = [
                "[data-message-author-role='assistant']",  # Assistant messages
                ".message-content",  # Message content
                ".conversation-item",  # Conversation items
                ".task-content",  # Task-specific content
                "main .prose",  # Main content area
                "[role='main'] div[data-message-author-role='assistant']"  # More specific assistant content
            ]
            
            all_content = []
            
            for selector in chat_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        
                        # Get text from recent elements (last 3)
                        for element in elements[-3:]:
                            text = await element.text_content()
                            if text and text.strip() and len(text.strip()) > 10:  # Only meaningful content
                                all_content.append(text.strip())
                        
                        # If we found meaningful content, break
                        if all_content:
                            break
                            
                except Exception as selector_error:
                    print(f"Error with selector {selector}: {selector_error}")
                    continue
            
            if all_content:
                combined_content = " | ".join(all_content[-2:])  # Last 2 meaningful pieces
                return f"Chat completed successfully. Content: {combined_content[:500]}..."
            else:
                # Fallback: get page title or URL info
                try:
                    page_title = await self.page.title()
                    return f"Chat completed successfully. Page: {page_title}"
                except:
                    return f"Chat completed successfully at: {self.page.url}"
            
        except Exception as e:
            print(f"ERROR: Failed to read completed chat content: {str(e)}")
            return f"Chat completed but could not read content. URL: {self.page.url}"
    
    async def _setup_web_interface(self) -> bool:
        """Handle the complete authentication flow to reach OpenAI Codex"""
        try:
            print(f"Setting up OpenAI Codex interface...")
            
            # Check current URL to determine what step we're on
            current_url = self.page.url
            print(f"Current URL: {current_url}")
            
            # Step 1: Handle initial login redirect
            if 'chatgpt.com/codex' in current_url:
                print("Already authenticated and at Codex page!")
                return await self._verify_codex_interface()
            
            # Step 2: Handle login/signup page
            if 'chatgpt.com' in current_url and ('auth/login' in current_url or self._is_login_signup_page()):
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
                
                # Wait for redirect back to OpenAI
                await self.page.wait_for_timeout(5000)
                current_url = self.page.url
                print(f"After Google login, URL: {current_url}")
            
            # Step 5: Final verification - should be at codex page
            if 'chatgpt.com/codex' in current_url:
                print("Successfully reached OpenAI Codex!")
                return await self._verify_codex_interface()
            else:
                print(f"ERROR: Unexpected final URL: {current_url}")
                return False
            
        except Exception as e:
            print(f"ERROR: Failed to setup OpenAI Codex interface: {str(e)}")
            return False
    
    def _is_login_signup_page(self) -> bool:
        """Check if we're on the login/signup page by looking for characteristic elements"""
        try:
            # Look for the "Get started" heading and login/signup buttons
            page_text = self.page.content() if hasattr(self.page, 'content') else ""
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