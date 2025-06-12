#!/usr/bin/env python3
"""
Shared Claude Client Utility

This module provides a centralized Claude API client that can be used across
the codebase for various operations including:
- IDE state analysis
- PR content generation
- Computer use operations
- General text analysis
"""

import os
import json
import base64
from typing import Optional, Dict, Any, Union
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()


class ClaudeClient:
    """Shared Claude API client for various operations"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            print("WARNING: No ANTHROPIC_API_KEY found. Claude operations will be limited.")
        
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Anthropic client"""
        if self._client is None and self.api_key:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                print("ERROR: anthropic package not installed. Run: pip install anthropic")
                return None
        return self._client
    
    def is_available(self) -> bool:
        """Check if Claude client is available and configured"""
        return self.client is not None
    
    def analyze_image_with_prompt(
        self,
        image_input: Union[str, BytesIO, Image.Image],
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2000,
        expect_json: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an image with a text prompt using Claude Vision
        
        Args:
            image_input: Either a file path (str), BytesIO buffer, or PIL Image
            prompt: The analysis prompt
            system_prompt: Optional system prompt for context
            model: Claude model to use
            max_tokens: Maximum tokens in response
            expect_json: Whether to expect and parse JSON response
            
        Returns:
            Dict containing the analysis result, or None if failed
        """
        if not self.is_available():
            print("ERROR: Claude client not available")
            return None
        
        try:
            # Convert image to base64
            base64_image = self._image_to_base64(image_input)
            if not base64_image:
                return None
            
            # Prepare message content
            message_content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64_image
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            # Create message
            messages = [{"role": "user", "content": message_content}]
            
            # Add system prompt if provided
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            # Get response from Claude
            response = self.client.messages.create(**kwargs)
            response_text = response.content[0].text.strip()
            
            if expect_json:
                return self._parse_json_response(response_text)
            else:
                return {"response": response_text, "success": True}
                
        except Exception as e:
            print(f"Error analyzing image with Claude: {e}")
            return {"error": str(e), "success": False}
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2000,
        expect_json: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Generate text using Claude
        
        Args:
            prompt: The text prompt
            system_prompt: Optional system prompt for context
            model: Claude model to use
            max_tokens: Maximum tokens in response
            expect_json: Whether to expect and parse JSON response
            
        Returns:
            Dict containing the generated text, or None if failed
        """
        if not self.is_available():
            print("ERROR: Claude client not available")
            return None
        
        try:
            # Create message
            messages = [{"role": "user", "content": prompt}]
            
            # Add system prompt if provided
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            # Get response from Claude
            response = self.client.messages.create(**kwargs)
            response_text = response.content[0].text.strip()
            
            if expect_json:
                return self._parse_json_response(response_text)
            else:
                return {"response": response_text, "success": True}
                
        except Exception as e:
            print(f"Error generating text with Claude: {e}")
            return {"error": str(e), "success": False}
    
    def _image_to_base64(self, image_input: Union[str, BytesIO, Image.Image]) -> Optional[str]:
        """Convert various image inputs to base64 string"""
        try:
            if isinstance(image_input, str):
                # It's a file path
                with open(image_input, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            
            elif isinstance(image_input, BytesIO):
                # It's a BytesIO buffer
                image_input.seek(0)  # Reset to beginning
                return base64.b64encode(image_input.read()).decode('utf-8')
            
            elif isinstance(image_input, Image.Image):
                # It's a PIL Image
                # Ensure image is in RGB format for compatibility
                if image_input.mode != "RGB":
                    image_input = image_input.convert("RGB")
                
                # Convert to bytes
                buffer = BytesIO()
                image_input.save(buffer, format="PNG")
                buffer.seek(0)
                return base64.b64encode(buffer.read()).decode('utf-8')
            
            else:
                print(f"ERROR: Unsupported image input type: {type(image_input)}")
                return None
                
        except Exception as e:
            print(f"Error converting image to base64: {e}")
            return None
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from Claude, handling code blocks"""
        try:
            # Remove any markdown code block formatting
            if "```json" in response_text:
                json_content = response_text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in response_text and "```" in response_text.split("```", 1)[1]:
                json_content = response_text.split("```", 1)[1].split("```", 1)[0].strip()
            else:
                json_content = response_text
            
            # Parse the JSON
            parsed_data = json.loads(json_content)
            return {"data": parsed_data, "success": True}
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            print(f"Response was: {response_text}")
            return {"error": f"JSON parsing failed: {e}", "response": response_text, "success": False}


# Global instance for easy access
claude_client = ClaudeClient()


def analyze_ide_state_with_claude(
    image_input: Union[str, BytesIO, Image.Image],
    interface_state_analysis_prompt: str
) -> tuple[bool, str, str]:
    """
    Analyze IDE state using Claude Vision
    
    Args:
        image_input: Either a path to screenshot image (str), BytesIO buffer, or PIL Image
        interface_state_analysis_prompt: Prompt for IDE state analysis
        
    Returns:
        tuple: (bool, str, str) - (Whether the IDE is done, State, Reasoning)
    """
    system_prompt = """You are an IDE State Analysis AI. Analyze screenshots of IDE interfaces to determine their current state.

You must respond with JSON in this exact format:
{
    "interface_state": "done" | "processing" | "paused_and_wanting_to_resume" | "error",
    "reasoning": "Brief explanation of why you determined this state"
}

State definitions:
- "done": The IDE has completed its task and is ready for new input
- "processing": The IDE is actively working on a task
- "paused_and_wanting_to_resume": The IDE is paused and waiting for user action to continue
- "error": The IDE encountered an error or is in an error state

Respond ONLY with the JSON format above."""
    
    try:
        result = claude_client.analyze_image_with_prompt(
            image_input=image_input,
            prompt=interface_state_analysis_prompt,
            system_prompt=system_prompt,
            expect_json=True
        )
        
        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown error") if result else "Claude client unavailable"
            return False, "error", f"Claude analysis failed: {error_msg}"
        
        analysis = result["data"]
        state = analysis["interface_state"].lower()
        reasoning = analysis["reasoning"]
        
        # Determine if IDE is done
        is_done = state == "done"
        return is_done, state, reasoning
        
    except Exception as e:
        print(f"Error analyzing IDE state with Claude: {e}")
        return False, f"error: {str(e)}", str(e)


def generate_commit_and_pr_content_with_claude(
    agent_execution_report_summary: str,
    workflow_name: str,
    coding_ides_info: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use Claude to generate both commit message and PR content in a single API call
    
    Args:
        agent_execution_report_summary: The summary/output from the coding agent
        workflow_name: Name of the workflow used (preset workflow name or task description for general coding)
        coding_ides_info: Optional information about coding IDEs used (roles, models, etc.)
        
    Returns:
        Dict with 'commit_message', 'pr_title', 'pr_description', 'pr_changes_summary', and 'branch_name' keys
    """
    system_prompt = """You are a technical writing assistant specializing in creating professional git commit messages and pull request descriptions from AI coding agent outputs.

Given a coding agent's execution report summary, original prompt, and agent name, generate:
1. A professional git commit message following conventional commit standards
2. A concise, descriptive PR title (max 60 characters)
3. A professional PR description 
4. A clear summary of what changed
5. A descriptive branch name for the changes

Format your response as JSON with these exact keys:
{
    "commit_message": "Professional git commit message following conventional commit format",
    "pr_title": "Brief, descriptive PR title",
    "pr_description": "Professional description of the changes",
    "pr_changes_summary": "Clear summary of what was modified/added/removed",
    "branch_name": "Descriptive branch name following git conventions"
}

Guidelines for commit message:
- Use conventional commit format: type(scope): description
- Keep the first line under 72 characters
- Use present tense, imperative mood ("Add feature" not "Added feature")
- Be specific about what was changed
- Include a brief body if the changes are complex
- Common types: feat, fix, refactor, docs, style, test, chore

Guidelines for PR content:
- Title should be actionable and specific (e.g., "Add user authentication system" not "Update code")
- Description should be 2-3 sentences explaining the purpose and approach
- Changes summary should list the key files/features modified
- Keep it professional and technical but accessible
- Focus on what was accomplished, not just what was requested
- If coding IDE information is provided, include a brief mention of the tools/models used

Guidelines for branch name:
- Use kebab-case (lowercase with hyphens)
- Be descriptive but concise (max 50 characters)
- Include the type of change (feature/, fix/, refactor/, etc.)
- Examples: "feature/user-auth", "fix/login-bug", "refactor/api-endpoints"
- Avoid special characters except hyphens and forward slashes"""

    # Build user message with optional IDE information
    user_message_parts = [
        f"Workflow: {workflow_name}",
        "",
        "Agent Execution Report Summary:",
        agent_execution_report_summary
    ]
    
    if coding_ides_info:
        user_message_parts.extend([
            "",
            "Coding IDEs Information:",
            coding_ides_info
        ])
    
    user_message_parts.extend([
        "",
        "Please generate a professional git commit message and PR content based on this information."
    ])
    
    user_message = "\n".join(user_message_parts)
    
    try:
        result = claude_client.generate_text(
            prompt=user_message,
            system_prompt=system_prompt,
            max_tokens=2500,
            expect_json=True
        )
        
        if not result or not result.get("success"):
            print("WARNING: Claude PR content generation failed, using default formats")
            return _generate_default_commit_and_pr_content(workflow_name)
        
        parsed_response = result["data"]
        
        # Validate required keys
        required_keys = ['commit_message', 'pr_title', 'pr_description', 'pr_changes_summary', 'branch_name']
        if all(key in parsed_response for key in required_keys):
            # Basic validation for commit message
            commit_msg = parsed_response['commit_message']
            if commit_msg and len(commit_msg) > 10:
                print("SUCCESS: Generated commit message and PR content using Claude")
                return parsed_response
            else:
                print("WARNING: Claude generated invalid commit message, using default formats")
                return _generate_default_commit_and_pr_content(workflow_name)
        else:
            print("WARNING: Claude response missing required keys, using default formats")
            return _generate_default_commit_and_pr_content(workflow_name)
            
    except Exception as e:
        print(f"WARNING: Error calling Claude for content generation: {str(e)}")
        return _generate_default_commit_and_pr_content(workflow_name)


def _generate_default_commit_and_pr_content(workflow_name: str) -> Dict[str, Any]:
    """Generate default commit message and PR content when Claude processing fails"""
    from datetime import datetime
    
    # Generate default branch name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_workflow_name = workflow_name.replace(" ", "-").replace("(", "").replace(")", "").replace("_", "-").lower()
    default_branch_name = f"simulatedev/{sanitized_workflow_name}_{timestamp}"
    
    return {
        "commit_message": f"SimulateDev: {workflow_name}",
        "pr_title": f"[SimulateDev] {workflow_name[:50]}{'...' if len(workflow_name) > 50 else ''}",
        "pr_description": f"Automated changes generated by SimulateDev workflow.",
        "pr_changes_summary": f"Changes implemented according to the workflow: \"{workflow_name}\"",
        "branch_name": default_branch_name
    } 