#!/usr/bin/env python3
"""
Coder Role Module

This module implements the Coder role for the multi-agent system.
The Coder is responsible for implementing solutions based on plans and requirements,
creating working code files and ensuring functionality.
"""

from typing import Dict, Any
from agents import AgentDefinition, AgentContext, AgentRole
from .base_role import BaseRole


class CoderRole(BaseRole):
    """Coder role implementation for software development and implementation"""
    
    def __init__(self):
        super().__init__(AgentRole.CODER)
    
    def create_prompt(self, task: str, context: AgentContext, 
                     agent_definition: AgentDefinition) -> str:
        """Create a comprehensive coding prompt"""
        prompt = f"""You are {agent_definition.coding_ide} ({agent_definition.model}), acting as a SOFTWARE DEVELOPER.

## TASK TO IMPLEMENT
{task}

## YOUR ROLE AS CODER
Your job is to implement the solution based on the planning information provided.
You are responsible for creating working, production-ready code that fulfills the requirements.

## CONTEXT INFORMATION
- Work Directory: {context.work_directory}
- Current Step: {context.current_step}/{context.total_steps}
"""
        
        # Include planner output if available
        planner_output = context.get_latest_output_by_role(AgentRole.PLANNER)
        if planner_output:
            prompt += f"""
## IMPLEMENTATION PLAN (from Planner)
{planner_output['output']}

## YOUR IMPLEMENTATION TASK
Follow the plan above and implement the solution. Key points to consider:
- Implement all components outlined in the plan
- Follow the suggested file structure
- Include all specified dependencies
- If the plan needs adjustments based on your technical expertise, make them but explain why
"""
            
            # Include extracted plan sections if available
            if 'plan_sections' in planner_output:
                sections = planner_output['plan_sections']
                if sections.get('files'):
                    prompt += f"""
### File Structure to Implement:
{sections['files']}
"""
                if sections.get('dependencies'):
                    prompt += f"""
### Dependencies to Include:
{sections['dependencies']}
"""
        else:
            prompt += """
## NO PRE-EXISTING PLAN
No planner output is available. Please create and implement a solution from scratch.
Analyze the requirements carefully and design an appropriate solution.
"""
        
        # Include previous coder attempts if any
        previous_coder_outputs = context.get_outputs_by_role(AgentRole.CODER)
        if previous_coder_outputs:
            prompt += f"""
## PREVIOUS IMPLEMENTATION ATTEMPTS
{len(previous_coder_outputs)} previous coding attempt(s) were made:
"""
            for i, output in enumerate(previous_coder_outputs[-2:], 1):  # Show last 2 attempts
                status = "✅ SUCCESS" if output['success'] else "❌ FAILED"
                prompt += f"""
### Attempt {i} by {output['coding_ide']} ({status})
Output: {output['output'][:500]}...
"""
                if not output['success'] and output.get('error'):
                    prompt += f"Error: {output['error']}\n"
            
            prompt += """
## IMPROVEMENT INSTRUCTIONS
Please improve upon or complete the previous work:
- Fix any errors or issues from previous attempts
- Complete any unfinished functionality
- Enhance code quality and structure
- Add missing components or features
"""
        
        prompt += """
## CRITICAL: ANALYZE REPOSITORY FIRST
Before coding, study existing files to understand:
- Coding style (indentation, naming, comments, imports)
- Architecture patterns and file organization
- Error handling and testing approaches

**REQUIREMENT**: Your code MUST match the existing repository's style and conventions exactly.

## IMPLEMENTATION STEPS
1. **ANALYZE** existing codebase for style and patterns
2. **CREATE** working code files that match repository style
3. **IMPLEMENT** full functionality following existing patterns
4. **TEST** implementation works correctly
5. **DOCUMENT** what you built and how it integrates

## DELIVERABLES
□ Complete, working code files
□ Code matches repository style
□ Proper error handling
□ Clear documentation
□ Implementation summary

Create production-ready code that feels like a natural extension of the existing codebase.
"""
        return prompt
    
    def get_role_description(self) -> str:
        """Get description of the Coder role"""
        return "Software Developer - Implements solutions and creates working code"
    
    def should_retry_on_failure(self) -> bool:
        """Coders should be retried if they fail"""
        return True
    
    def get_max_retries(self) -> int:
        """Coders get standard retries"""
        return 1
    
    def post_execution_hook(self, result: Dict[str, Any], 
                          context: AgentContext) -> Dict[str, Any]:
        """Post-process coder results to extract implementation details"""
        if result["success"] and result["output"]:
            output = result["output"]
            
            # Extract implementation details
            implementation_info = {
                "files_created": self._extract_files_mentioned(output),
                "technologies_used": self._extract_technologies(output),
                "key_features": self._extract_features(output),
                "setup_instructions": self._extract_setup_info(output)
            }
            
            # Add implementation info to result
            result["implementation_info"] = implementation_info
            
            # Check for common success indicators
            success_indicators = [
                "successfully created", "implementation complete", "working code",
                "files created", "ready to use", "tested and working"
            ]
            
            output_lower = output.lower()
            result["confidence_score"] = sum(1 for indicator in success_indicators 
                                           if indicator in output_lower) / len(success_indicators)
        
        return result
    
    def _extract_files_mentioned(self, text: str) -> list:
        """Extract file names mentioned in the implementation output"""
        import re
        # Look for common file patterns
        file_patterns = [
            r'`([^`]+\.[a-zA-Z0-9]+)`',  # Files in backticks
            r'(\w+\.[a-zA-Z0-9]+)',      # Simple file.ext pattern
            r'created?\s+([^\s]+\.[a-zA-Z0-9]+)',  # "created filename.ext"
        ]
        
        files = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            files.update(matches)
        
        return list(files)
    
    def _extract_technologies(self, text: str) -> list:
        """Extract technologies/frameworks mentioned"""
        common_tech = [
            'python', 'javascript', 'react', 'node.js', 'express', 'flask', 'django',
            'html', 'css', 'typescript', 'vue', 'angular', 'fastapi', 'sqlite',
            'postgresql', 'mongodb', 'redis', 'docker', 'kubernetes'
        ]
        
        text_lower = text.lower()
        found_tech = [tech for tech in common_tech if tech in text_lower]
        return found_tech
    
    def _extract_features(self, text: str) -> list:
        """Extract key features mentioned in the implementation"""
        feature_keywords = [
            'feature', 'functionality', 'capability', 'component', 'module',
            'api', 'endpoint', 'service', 'function', 'method'
        ]
        
        lines = text.split('\n')
        features = []
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in feature_keywords):
                # Extract the feature description
                clean_line = line.strip('- *#').strip()
                if len(clean_line) > 10 and len(clean_line) < 100:
                    features.append(clean_line)
        
        return features[:10]  # Limit to top 10 features
    
    def _extract_setup_info(self, text: str) -> str:
        """Extract setup/installation instructions"""
        setup_keywords = ['setup', 'install', 'run', 'start', 'usage', 'how to']
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in setup_keywords):
                # Extract the next few lines as setup info
                setup_lines = []
                for j in range(i, min(i + 10, len(lines))):
                    setup_lines.append(lines[j])
                    if j > i and lines[j].strip() == '':
                        break
                return '\n'.join(setup_lines).strip()
        
        return "" 