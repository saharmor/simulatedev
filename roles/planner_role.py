#!/usr/bin/env python3
"""
Planner Role Module

This module implements the Planner role for the multi-agent system.
The Planner is responsible for analyzing requirements and creating detailed
implementation plans for other agents to follow.
"""

from typing import Dict, Any
from agents import AgentDefinition, AgentContext, AgentRole
from .base_role import BaseRole


class PlannerRole(BaseRole):
    """Planner role implementation for creating project plans and strategies"""
    
    def __init__(self):
        super().__init__(AgentRole.PLANNER)
    
    def create_prompt(self, task: str, context: AgentContext, 
                     agent_definition: AgentDefinition) -> str:
        """Create a comprehensive planning prompt"""
        prompt = f"""You are {agent_definition.coding_ide} ({agent_definition.model}), acting as a PROJECT PLANNER.

## TASK TO PLAN
{task}

## YOUR ROLE AS PLANNER
Your job is to create a comprehensive, step-by-step implementation plan for this task. You should:

1. **ANALYZE** the requirements thoroughly
2. **BREAK DOWN** the task into logical, manageable steps
3. **IDENTIFY** key components, files, and dependencies needed
4. **CONSIDER** potential challenges and solutions
5. **CREATE** a detailed implementation roadmap

## DELIVERABLES
Please provide:
1. **Executive Summary**: Brief overview of the solution approach
2. **Step-by-Step Plan**: Detailed implementation steps with clear descriptions
3. **File Structure**: List of files that need to be created/modified
4. **Dependencies**: Any external libraries or tools needed
5. **Testing Strategy**: How the solution should be tested
6. **Potential Issues**: Challenges that might arise and how to address them

## CONTEXT INFORMATION
- Work Directory: {context.work_directory}
- Current Step: {context.current_step}/{context.total_steps}
"""
        
        # Add information about previous planning attempts if any
        previous_plans = context.get_outputs_by_role(AgentRole.PLANNER)
        if previous_plans:
            prompt += f"""
## PREVIOUS PLANNING ATTEMPTS
{len(previous_plans)} previous planning attempt(s) were made. Please review and improve upon them:
"""
            for i, plan in enumerate(previous_plans[-2:], 1):  # Show last 2 attempts
                status = "SUCCESS" if plan['success'] else "FAILED"
                prompt += f"""
### Plan {i} ({status})
{plan['output'][:800]}...
"""
            prompt += "\nPlease create an improved plan that addresses any shortcomings from previous attempts."
        
        prompt += """
## OUTPUT FORMAT
Structure your response clearly with headers and bullet points. Be specific and actionable.
The coding agents that follow will implement your plan, so make it detailed and clear.

## IMPORTANT GUIDELINES
- Focus on the "what" and "how", not the actual code implementation
- Consider scalability, maintainability, and best practices
- Provide clear acceptance criteria for each step
- Think about error handling and edge cases
- Consider the target environment and constraints

Remember: You are planning, not implementing. Create a roadmap that others can follow successfully.
"""
        return prompt
    
    def create_prompt_with_workflow(self, task: str, context: AgentContext, 
                                  agent_definition: AgentDefinition, 
                                  workflow_type: str = None) -> str:
        """Create a workflow-aware planning prompt"""
        base_prompt = self.create_prompt(task, context, agent_definition)
        
        if workflow_type:
            workflow_specific = self._get_planner_workflow_context(workflow_type)
            if workflow_specific:
                # Insert workflow context after the role description
                lines = base_prompt.split('\n')
                insert_index = 8  # After "## YOUR ROLE AS PLANNER" section
                lines.insert(insert_index, workflow_specific)
                base_prompt = '\n'.join(lines)
        
        return base_prompt
    
    def _get_planner_workflow_context(self, workflow_type: str) -> str:
        """Get planner-specific workflow context"""
        workflow_contexts = {
            "bug_hunting": """
## WORKFLOW FOCUS: BUG HUNTING & SECURITY ANALYSIS
As a planner in a bug hunting workflow, your plan should prioritize:
- **Security audit strategy**: Systematic approach to finding vulnerabilities
- **Code review methodology**: Focus areas for security-critical code sections
- **Testing approach**: Security testing, penetration testing, static analysis tools
- **Risk assessment**: Prioritize high-risk areas (authentication, data handling, APIs)
- **Remediation planning**: How to fix identified vulnerabilities safely
- **Compliance considerations**: Security standards and best practices to follow
""",
            "code_optimization": """
## WORKFLOW FOCUS: PERFORMANCE OPTIMIZATION STRATEGY
As a planner in a code optimization workflow, your plan should prioritize:
- **Performance profiling strategy**: How to identify bottlenecks and performance issues
- **Optimization targets**: Database queries, algorithms, memory usage, I/O operations
- **Measurement approach**: Benchmarking, metrics collection, before/after comparisons
- **Risk mitigation**: How to optimize without breaking existing functionality
- **Testing strategy**: Performance testing, load testing, regression testing
- **Monitoring plan**: How to track performance improvements over time
""",
            "general_coding": """
## WORKFLOW FOCUS: CLEAN DEVELOPMENT STRATEGY
As a planner in a general coding workflow, your plan should prioritize:
- **Architecture design**: Clean, maintainable, and scalable code structure
- **Development methodology**: Best practices, coding standards, design patterns
- **Quality assurance**: Code review process, testing strategy, documentation
- **Integration approach**: How new code integrates with existing systems
- **Deployment strategy**: How to safely deploy and rollback changes
- **Maintenance considerations**: Long-term maintainability and extensibility
"""
        }
        
        return workflow_contexts.get(workflow_type, "")
    
    def get_role_description(self) -> str:
        """Get description of the Planner role"""
        return "Project Planner - Creates comprehensive implementation plans and strategies"
    
    def should_retry_on_failure(self) -> bool:
        """Planners should be retried if they fail"""
        return True
    
    def get_max_retries(self) -> int:
        """Planners get more retries since planning is critical"""
        return 2
    
    def post_execution_hook(self, result: Dict[str, Any], 
                          context: AgentContext) -> Dict[str, Any]:
        """Post-process planner results to extract key information"""
        if result["success"] and result["output"]:
            # Extract key sections from the plan for easier access by other roles
            output = result["output"]
            
            # Try to identify key sections (this is a simple heuristic)
            sections = {
                "executive_summary": self._extract_section(output, ["executive summary", "overview"]),
                "steps": self._extract_section(output, ["step-by-step", "implementation steps", "plan"]),
                "files": self._extract_section(output, ["file structure", "files"]),
                "dependencies": self._extract_section(output, ["dependencies", "requirements"]),
                "testing": self._extract_section(output, ["testing strategy", "testing"]),
                "issues": self._extract_section(output, ["potential issues", "challenges"])
            }
            
            # Add extracted sections to result for easier access
            result["plan_sections"] = sections
        
        return result
    
    def _extract_section(self, text: str, keywords: list) -> str:
        """Extract a section from the plan text based on keywords"""
        lines = text.split('\n')
        
        for keyword in keywords:
            for i, line in enumerate(lines):
                if keyword in line.lower() and any(char in line for char in ['#', '*', '-']):
                    # Found a section header, extract content until next section
                    section_lines = []
                    for j in range(i + 1, len(lines)):
                        next_line = lines[j].strip()
                        # Stop if we hit another section header
                        if next_line and any(char in next_line for char in ['#', '*']) and len(next_line) > 10:
                            break
                        section_lines.append(lines[j])
                    
                    return '\n'.join(section_lines).strip()
        
        return "" 