#!/usr/bin/env python3
"""
Web Automation Utilities

Common utility functions for web automation tasks using Playwright.
These utilities can be shared across different web agents.
"""

from typing import Optional
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


async def wait_for_element(page, selector: str, description: str, timeout: int = 10000):
    """Wait for an element to appear"""
    try:
        await page.wait_for_selector(selector, timeout=timeout)
    except PlaywrightTimeoutError:
        print(f"WARNING: Timeout waiting for {description}")
    except Exception as e:
        print(f"ERROR: Unexpected error waiting for {description}: {str(e)}")


async def click_element(page, selector: str, description: str) -> bool:
    """Find and click an element"""
    try:
        element = await page.query_selector(selector)
        if element and await element.is_visible() and await element.is_enabled():
            await element.click()
            await page.wait_for_timeout(1000)
            return True
        
        print(f"ERROR: Could not click {description}")
        return False
        
    except Exception as e:
        print(f"ERROR: Failed to click {description}: {str(e)}")
        return False


async def scroll_and_click(page, element, description: str):
    """Scroll element into view and click it"""
    try:
        await element.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        
        try:
            await element.click()
        except PlaywrightTimeoutError:
            # Fallback to JavaScript click if regular click fails
            await element.evaluate("element => element.click()")
        except Exception as e:
            print(f"ERROR: Failed to click {description} after scroll: {str(e)}")
            
    except Exception as e:
        print(f"ERROR: Failed to click {description}: {str(e)}")


async def wait_for_loading_complete(page, loading_selector: str):
    """Wait for any loading indicators to complete"""
    try:
        # Wait for loading indicator to appear, then disappear
        await page.wait_for_selector(loading_selector, timeout=5000)
        await page.wait_for_selector(loading_selector, state="hidden", timeout=30000)
    except PlaywrightTimeoutError:
        # No loading indicator found or already completed
        pass
    except Exception as e:
        print(f"WARNING: Unexpected error waiting for loading to complete: {str(e)}") 