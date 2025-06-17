#!/usr/bin/env python3
"""
Unified LLM Client using LiteLLM Gateway

This module provides a centralized LLM client that can work with multiple providers
including OpenAI and Anthropic through LiteLLM, supporting:
- IDE state analysis
- PR content generation 
- Computer use operations
- General text analysis

LiteLLM provides a unified interface for 100+ LLM models while maintaining
OpenAI-compatible format for responses.
"""

import os
import json
import base64
import warnings
from typing import Optional, Dict, Any, Union, Literal, List
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# Supported LLM providers
LLMProvider = Literal["anthropic", "openai"]

# Pydantic models for structured responses
class Coordinates(BaseModel):
    """Coordinates for UI actions"""
    x: int = Field(description="X coordinate")
    y: int = Field(description="Y coordinate")

class Action(BaseModel):
    """UI action with type and coordinates"""
    type: str = Field(description="Type of action (click, type, etc.)")
    coordinates: Coordinates = Field(description="Coordinates for the action")

class ActionResponse(BaseModel):
    """Response containing an action"""
    action: Action = Field(description="The action to perform")

class IDEState(BaseModel):
    """IDE state analysis response"""
    interface_state: Literal["done", "still_working", "paused_and_wanting_to_resume"] = Field(
        description="Current state of the IDE interface"
    )
    reasoning: str = Field(description="Brief explanation of why this state was determined")

class CommitPRContent(BaseModel):
    """Git commit and PR content"""
    commit_message: str = Field(description="Professional git commit message following conventional commit format")
    pr_title: str = Field(description="Brief, descriptive PR title")
    pr_description: str = Field(description="Professional description of the changes")
    pr_changes_summary: str = Field(description="Clear summary of what was modified/added/removed")
    branch_name: str = Field(description="Descriptive branch name following git conventions")

class LLMClient:
    """Unified LLM client using LiteLLM for multiple provider support"""
    
    # Default models for each provider
    DEFAULT_MODELS = {
        "anthropic": "anthropic/claude-sonnet-4-20250514",
        "openai": "openai/gpt-4o"
    }
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        """
        Initialize the LLM client with LiteLLM
        
        Args:
            provider: Which LLM provider to use ("anthropic" or "openai")
                     If not provided, uses LLM_PROVIDER environment variable
        """
        # Determine provider from env if not specified
        self.provider = provider or os.getenv("LLM_PROVIDER", "anthropic").lower()
        
        # Validate provider
        if self.provider not in ["anthropic", "openai"]:
            print(f"WARNING: Invalid LLM_PROVIDER '{self.provider}'. Defaulting to 'anthropic'.")
            self.provider = "anthropic"
        
        # Get API keys from environment
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Set environment variables for LiteLLM (in case they weren't already set)
        if self.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        
        # Get default model for the provider
        env_model_key = f"{self.provider.upper()}_DEFAULT_MODEL"
        self.default_model = os.getenv(env_model_key, self.DEFAULT_MODELS[self.provider])
        
        # Ensure model has correct provider prefix
        if not self.default_model.startswith(f"{self.provider}/"):
            self.default_model = f"{self.provider}/{self.default_model}"
        
        self._litellm = None
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available"""
        try:
            import litellm
            self._litellm = litellm
        except ImportError:
            print("ERROR: litellm package not installed. Run: pip install litellm")
            return False
        
        return True
    
    def is_available(self) -> bool:
        """Check if LLM client is available and configured properly"""
        if not self._litellm:
            return False
        
        # Check if we have the required API key for the selected provider
        if self.provider == "anthropic" and not self.anthropic_api_key:
            print("ERROR: ANTHROPIC_API_KEY not found. Please set it in your environment.")
            return False
        elif self.provider == "openai" and not self.openai_api_key:
            print("ERROR: OPENAI_API_KEY not found. Please set it in your environment.")
            return False
        
        return True
    
    def get_model_name(self, model: Optional[str] = None) -> str:
        """Get the full model name with provider prefix"""
        if model:
            # If model already has provider prefix, return as-is
            if "/" in model and model.split("/")[0] in ["anthropic", "openai"]:
                return model
            # Otherwise, add current provider prefix
            return f"{self.provider}/{model}"
        return self.default_model
    
    def analyze_image_with_prompt(
        self,
        image_input: Union[str, BytesIO, Image.Image],
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        expect_json: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an image with a text prompt using LiteLLM
        
        Args:
            image_input: Either a file path (str), BytesIO buffer, or PIL Image
            prompt: The analysis prompt
            system_prompt: Optional system prompt for context
            model: Model to use (uses default if not specified)
            max_tokens: Maximum tokens in response
            expect_json: Whether to expect and parse JSON response
            
        Returns:
            Dict containing the analysis result, or None if failed
        """
        if not self.is_available():
            print("ERROR: LLM client not available")
            return None
        
        try:
            # Convert image to base64
            base64_image = self._image_to_base64(image_input)
            if not base64_image:
                return None
            
            # Prepare message content for vision
            message_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            # Create messages
            messages = [{"role": "user", "content": message_content}]
            
            # Add system message if provided
            if system_prompt:
                messages.insert(0, {"role": "system", "content": system_prompt})
            
            # Get model name
            model_name = self.get_model_name(model)
            
            # Prepare completion parameters
            completion_params = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "num_retries": 3  # Add retry mechanism
            }
            
            # Add response_format if expecting JSON
            if expect_json:
                completion_params["response_format"] = {"type": "json_object"}
            
            # Make the completion call using LiteLLM with retries
            response = self._litellm.completion(**completion_params)
            
            # Extract response text from the response object
            response_text = response["choices"][0]["message"]["content"].strip()
            
            if expect_json:
                return self._parse_json_response(response_text)
            else:
                return {"response": response_text, "success": True}
                
        except Exception as e:
            print(f"Error analyzing image with LLM: {e}")
            return {"error": str(e), "success": False}
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        expect_json: bool = False,
        temperature: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Generate text using LiteLLM
        
        Args:
            prompt: The text prompt
            system_prompt: Optional system prompt for context
            model: Model to use (uses default if not specified)
            max_tokens: Maximum tokens in response
            expect_json: Whether to expect and parse JSON response
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            Dict containing the generated text, or None if failed
        """
        if not self.is_available():
            print("ERROR: LLM client not available")
            return None
        
        try:
            # Create messages
            messages = [{"role": "user", "content": prompt}]
            
            # Add system message if provided
            if system_prompt:
                messages.insert(0, {"role": "system", "content": system_prompt})
            
            # Get model name
            model_name = self.get_model_name(model)
            
            # Prepare completion parameters
            completion_params = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "num_retries": 3
            }
            
            # Add response_format if expecting JSON
            if expect_json:
                completion_params["response_format"] = {"type": "json_object"}
            
            # Make the completion call using LiteLLM with retries
            response = self._litellm.completion(**completion_params)
            
            # Extract response text from the response object
            response_text = response["choices"][0]["message"]["content"].strip()
            
            if expect_json:
                return self._parse_json_response(response_text)
            else:
                return {"response": response_text, "success": True}
                
        except Exception as e:
            print(f"Error generating text with LLM: {e}")
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
        """Parse JSON response from LLM, handling code blocks"""
        try:
            # Clean up the response text
            response_text = response_text.strip()
            
            # Remove any markdown code block formatting
            if "```json" in response_text:
                # Extract content between ```json and ```
                parts = response_text.split("```json", 1)
                if len(parts) > 1:
                    json_part = parts[1].split("```", 1)[0].strip()
                    json_content = json_part
                else:
                    json_content = response_text
            elif response_text.startswith("```") and response_text.count("```") >= 2:
                # Handle generic code blocks
                parts = response_text.split("```", 2)
                if len(parts) >= 3:
                    json_content = parts[1].strip()
                else:
                    json_content = response_text
            else:
                json_content = response_text
            
            # Additional cleanup - remove any leading/trailing whitespace and newlines
            json_content = json_content.strip()
            
            # Try to find JSON object boundaries if the content has extra text
            if not json_content.startswith('{') and '{' in json_content:
                start_idx = json_content.find('{')
                json_content = json_content[start_idx:]
            
            if not json_content.endswith('}') and '}' in json_content:
                end_idx = json_content.rfind('}') + 1
                json_content = json_content[:end_idx]
            
            # Parse the JSON
            parsed_data = json.loads(json_content)
            return {"data": parsed_data, "success": True}
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            print(f"Response was: {response_text}")
            return {"error": f"JSON parsing failed: {e}", "response": response_text, "success": False}
        except Exception as e:
            print(f"Unexpected error parsing JSON response: {e}")
            print(f"Response was: {response_text}")
            return {"error": f"Unexpected parsing error: {e}", "response": response_text, "success": False}

    def analyze_image_with_structured_response(
        self,
        image_input: Union[str, BytesIO, Image.Image],
        prompt: str,
        response_model: BaseModel,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2000
    ) -> Optional[BaseModel]:
        """
        Analyze an image with a text prompt using LiteLLM and return structured Pydantic response
        
        Args:
            image_input: Either a file path (str), BytesIO buffer, or PIL Image
            prompt: The analysis prompt
            response_model: Pydantic model class for the expected response structure
            system_prompt: Optional system prompt for context
            model: Model to use (uses default if not specified)
            max_tokens: Maximum tokens in response
            
        Returns:
            Instance of the response_model, or None if failed
        """
        if not self.is_available():
            print("ERROR: LLM client not available")
            return None
        
        try:
            # Convert image to base64
            base64_image = self._image_to_base64(image_input)
            if not base64_image:
                return None
            
            # Prepare message content for vision
            message_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            # Create messages
            messages = [{"role": "user", "content": message_content}]
            
            # Add system message if provided
            if system_prompt:
                messages.insert(0, {"role": "system", "content": system_prompt})
            
            # Get model name
            model_name = self.get_model_name(model)
            
            # Prepare completion parameters with Pydantic model
            completion_params = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "response_format": response_model,
                "num_retries": 3
            }
            
            # Make the completion call using LiteLLM with retries
            response = self._litellm.completion(**completion_params)
            
            # Extract and parse the structured response
            if hasattr(response.choices[0].message, 'parsed') and response.choices[0].message.parsed:
                return response.choices[0].message.parsed
            else:
                # Fallback to manual parsing if parsed attribute not available
                response_text = response.choices[0].message.content.strip()
                return response_model.model_validate_json(response_text)
                
        except Exception as e:
            print(f"Error analyzing image with structured response: {e}")
            
            # Provide more specific error handling for common issues
            error_str = str(e).lower()
            if "overloaded" in error_str:
                print("INFO: Anthropic API is temporarily overloaded. LiteLLM will automatically retry with exponential backoff and fallback to alternative models if configured.")
            elif "rate" in error_str and "limit" in error_str:
                print("INFO: Rate limit encountered. LiteLLM will handle cooldown periods and retry automatically.")
            elif "context" in error_str and ("length" in error_str or "window" in error_str):
                print("INFO: Context window exceeded. LiteLLM will attempt fallback to models with larger context windows if configured.")
            
            return None

    def generate_structured_text(
        self,
        prompt: str,
        response_model: BaseModel,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.1
    ) -> Optional[BaseModel]:
        """
        Generate structured text using LiteLLM with Pydantic model
        
        Args:
            prompt: The text prompt
            response_model: Pydantic model class for the expected response structure
            system_prompt: Optional system prompt for context
            model: Model to use (uses default if not specified)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            Instance of the response_model, or None if failed
        """
        if not self.is_available():
            print("ERROR: LLM client not available")
            return None
        
        try:
            # Create messages
            messages = [{"role": "user", "content": prompt}]
            
            # Add system message if provided
            if system_prompt:
                messages.insert(0, {"role": "system", "content": system_prompt})
            
            # Get model name
            model_name = self.get_model_name(model)
            
            # Prepare completion parameters with Pydantic model
            completion_params = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": response_model,
                "num_retries": 3
            }
            
            # Make the completion call using LiteLLM with retries
            response = self._litellm.completion(**completion_params)
            
            # Extract and parse the structured response
            if hasattr(response.choices[0].message, 'parsed') and response.choices[0].message.parsed:
                return response.choices[0].message.parsed
            else:
                # Fallback to manual parsing if parsed attribute not available
                response_text = response.choices[0].message.content.strip()
                return response_model.model_validate_json(response_text)
                
        except Exception as e:
            print(f"Error generating structured text: {e}")
            return None


# Global instance for easy access - completely LLM-agnostic
llm_client = LLMClient()


def analyze_ide_state_with_llm(
    image_input: Union[str, BytesIO, Image.Image],
    interface_state_analysis_prompt: str
) -> tuple[bool, str, str]:
    """
    Analyze IDE state using the configured LLM provider with structured response
    
    Args:
        image_input: Either a path to screenshot image (str), BytesIO buffer, or PIL Image
        interface_state_analysis_prompt: Prompt for IDE state analysis
        
    Returns:
        tuple: (bool, str, str) - (Whether the IDE is done, State, Reasoning)
    """
    system_prompt = """You are an IDE State Analysis AI. Analyze screenshots of IDE interfaces to determine their current state.

State definitions:
- "done": The IDE has completed its task and is ready for new input
- "still_working": The IDE is actively working on a task
- "paused_and_wanting_to_resume": The IDE is paused and waiting for user action to continue

Analyze the image and provide your assessment in the required JSON format."""
    
    try:
        result = llm_client.analyze_image_with_structured_response(
            image_input=image_input,
            prompt=interface_state_analysis_prompt,
            response_model=IDEState,
            system_prompt=system_prompt
        )
        
        if result:
            state = result.interface_state.lower()
            reasoning = result.reasoning
            
            # Determine if IDE is done
            is_done = state == "done"
            return is_done, state, reasoning
        else:
            return False, "error", "LLM analysis failed: No response received"
        
    except Exception as e:
        print(f"Error analyzing IDE state with LLM: {e}")
        return False, f"error: {str(e)}", str(e)


def generate_commit_and_pr_content_with_llm(
    agent_execution_report_summary: str,
    workflow_name: str,
    coding_ides_info: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use the configured LLM provider to generate both commit message and PR content using structured response
    
    Args:
        agent_execution_report_summary: The summary/output from the coding agent
        workflow_name: Name of the workflow used (preset workflow name or task description for custom coding)
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
        result = llm_client.generate_structured_text(
            prompt=user_message,
            response_model=CommitPRContent,
            system_prompt=system_prompt,
            max_tokens=2500
        )
        
        if result:
            print(f"SUCCESS: Generated commit message and PR content using {llm_client.provider.upper()}")
            return {
                "commit_message": result.commit_message,
                "pr_title": result.pr_title,
                "pr_description": result.pr_description,
                "pr_changes_summary": result.pr_changes_summary,
                "branch_name": result.branch_name
            }
        else:
            print("WARNING: LLM PR content generation failed, using default formats")
            return _generate_default_commit_and_pr_content(workflow_name)
            
    except Exception as e:
        print(f"WARNING: Error calling LLM for content generation: {str(e)}")
        return _generate_default_commit_and_pr_content(workflow_name)


def _generate_default_commit_and_pr_content(workflow_name: str) -> Dict[str, Any]:
    """Generate default commit message and PR content when LLM processing fails"""
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