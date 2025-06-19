#!/usr/bin/env python3
"""
Tester Role Module

This module implements the Tester role for the multi-agent system.
The Tester is responsible for validating implementations, running tests,
and ensuring code quality and functionality.
"""

from typing import Dict, Any
from agents import AgentDefinition, AgentContext, AgentRole
from .base_role import BaseRole


class TesterRole(BaseRole):
    """Tester role implementation for quality assurance and validation"""
    
    def __init__(self):
        super().__init__(AgentRole.TESTER)
    
    def create_prompt(self, task: str, context: AgentContext, 
                     agent_definition: AgentDefinition) -> str:
        """Create a comprehensive testing prompt"""
        prompt = f"""You are {agent_definition.coding_ide}, acting as a SOFTWARE TESTER.

## ORIGINAL TASK
{task}

## YOUR ROLE AS TESTER
Your job is to thoroughly test the implementation created by the coding agents.
You are responsible for ensuring quality, functionality, and reliability of the solution.

## CONTEXT INFORMATION
- Work Directory: {context.work_directory}
- Current Step: {context.current_step}/{context.total_steps}
"""
        
        # Include planner output for reference
        planner_output = context.get_latest_output_by_role(AgentRole.PLANNER)
        if planner_output:
            prompt += f"""
## ORIGINAL PLAN (for Reference)
{planner_output['output'][:1000]}...

### Testing Strategy from Plan:
"""
            if 'plan_sections' in planner_output and planner_output['plan_sections'].get('testing'):
                prompt += planner_output['plan_sections']['testing']
            else:
                prompt += "No specific testing strategy was provided in the plan."
        
        # Include coder output - this is the main focus for testing
        coder_outputs = context.get_outputs_by_role(AgentRole.CODER)
        if coder_outputs:
            prompt += f"""
## IMPLEMENTATION TO TEST
The following implementations were created and need to be tested:
"""
            for i, output in enumerate(coder_outputs, 1):
                status = "SUCCESS" if output['success'] else "FAILED"
                prompt += f"""
### Implementation {i} by {output['coding_ide']} ({status})
{output['output'][:1200]}...
"""
                if 'implementation_info' in output:
                    info = output['implementation_info']
                    if info.get('files_created'):
                        prompt += f"\nFiles Created: {', '.join(info['files_created'])}"
                    if info.get('technologies_used'):
                        prompt += f"\nTechnologies: {', '.join(info['technologies_used'])}"
                    if info.get('setup_instructions'):
                        prompt += f"\nSetup Info: {info['setup_instructions'][:200]}..."
        else:
            prompt += """
## NO IMPLEMENTATION FOUND
No coder outputs available to test. This indicates a problem in the workflow.
Please investigate why no implementation was created.
"""
        
        # Include previous testing attempts if any
        previous_test_outputs = context.get_outputs_by_role(AgentRole.TESTER)
        if previous_test_outputs:
            prompt += f"""
## PREVIOUS TESTING ATTEMPTS
{len(previous_test_outputs)} previous testing attempt(s) were made:
"""
            for i, output in enumerate(previous_test_outputs[-2:], 1):
                status = "SUCCESS" if output['success'] else "FAILED"
                prompt += f"""
### Test {i} ({status})
{output['output'][:600]}...
"""
            prompt += "\nPlease build upon previous testing efforts and address any remaining issues."
        
        prompt += """
## SMART TESTING APPROACH
**ANALYZE FIRST**: Read README, check dependencies, assess what's feasible in automated environment

**FEASIBLE STRATEGIES**: Unit tests, static analysis, mock testing, code review
**AVOID**: Docker, database installs, external services, heavy infrastructure, GUI tools

**TESTING TRANSPARENCY REQUIRED**:
Your report must include:
1. **Coverage Summary**: What was tested automatically vs. code review vs. needs manual testing
2. **Limitations Section**: 
   ```
   ## Testing Limitations
   Due to automated environment constraints:
   - Docker functionality requires manual verification
   - Database connections need manual testing
   - External APIs require manual validation
   ```
3. **Review Focus**: Highlight code areas needing careful review due to limited automated testing

## TESTING FOCUS AREAS
**FUNCTIONALITY**: Core features, input validation, error handling, component integration
**CODE QUALITY**: Structure, standards compliance, documentation, security, performance  
**SETUP**: Installation process, dependencies, file organization

## REPORT STRUCTURE
1. **Executive Summary**: Overall Pass/Fail assessment with key findings
2. **Test Results**: What was tested and outcomes
3. **Issues Found**: Critical/Major/Minor issues with specific examples
4. **Recommendations**: Immediate actions needed and future improvements

## OUTPUT FORMAT
Structure your response with clear sections and use bullet points for readability.
Be specific about what you tested, how you tested it, and what the results were.
Include code snippets or examples where relevant.

## TESTING PRINCIPLES
- Be thorough but practical
- Focus on real-world usage scenarios
- Document everything clearly
- Provide actionable feedback
- Consider the end user's perspective
- Balance perfectionism with practicality

**Be thorough but practical. Focus on real-world scenarios and provide actionable feedback.**
"""
        return prompt
    
    def create_prompt_with_workflow(self, task: str, context: AgentContext, 
                                  agent_definition: AgentDefinition, 
                                  workflow_type: str = None) -> str:
        """Create a workflow-aware testing prompt with workflow context first"""
        # Start with workflow context if available
        prompt_parts = []
        
        if workflow_type:
            workflow_specific = self._get_tester_workflow_context(workflow_type)
            if workflow_specific:
                prompt_parts.append(workflow_specific)
        
        # Add the main role-specific prompt
        role_prompt = f"""You are {agent_definition.coding_ide}, acting as a SOFTWARE TESTER.

## ORIGINAL TASK
{task}

## YOUR ROLE AS TESTER
Your job is to thoroughly test the implementation created by the coding agents.
You are responsible for ensuring quality, functionality, and reliability of the solution.

## CONTEXT INFORMATION
- Work Directory: {context.work_directory}
- Current Step: {context.current_step}/{context.total_steps}
"""
        
        # Include planner output for reference
        planner_output = context.get_latest_output_by_role(AgentRole.PLANNER)
        if planner_output:
            role_prompt += f"""
## ORIGINAL PLAN (for Reference)
{planner_output['output'][:1000]}...

### Testing Strategy from Plan:
"""
            if 'plan_sections' in planner_output and planner_output['plan_sections'].get('testing'):
                role_prompt += planner_output['plan_sections']['testing']
            else:
                role_prompt += "No specific testing strategy was provided in the plan."
        
        # Include coder output - this is the main focus for testing
        coder_outputs = context.get_outputs_by_role(AgentRole.CODER)
        if coder_outputs:
            role_prompt += f"""
## IMPLEMENTATION TO TEST
The following implementations were created and need to be tested:
"""
            for i, output in enumerate(coder_outputs, 1):
                status = "SUCCESS" if output['success'] else "FAILED"
                role_prompt += f"""
### Implementation {i} by {output['coding_ide']} ({status})
{output['output'][:1200]}...
"""
                if 'implementation_info' in output:
                    info = output['implementation_info']
                    if info.get('files_created'):
                        role_prompt += f"\nFiles Created: {', '.join(info['files_created'])}"
                    if info.get('technologies_used'):
                        role_prompt += f"\nTechnologies: {', '.join(info['technologies_used'])}"
                    if info.get('setup_instructions'):
                        role_prompt += f"\nSetup Info: {info['setup_instructions'][:200]}..."
        else:
            role_prompt += """
## NO IMPLEMENTATION FOUND
No coder outputs available to test. This indicates a problem in the workflow.
Please investigate why no implementation was created.
"""
        
        # Include previous testing attempts if any
        previous_test_outputs = context.get_outputs_by_role(AgentRole.TESTER)
        if previous_test_outputs:
            role_prompt += f"""
## PREVIOUS TESTING ATTEMPTS
{len(previous_test_outputs)} previous testing attempt(s) were made:
"""
            for i, output in enumerate(previous_test_outputs[-2:], 1):
                status = "SUCCESS" if output['success'] else "FAILED"
                role_prompt += f"""
### Test {i} ({status})
{output['output'][:600]}...
"""
            role_prompt += "\nPlease build upon previous testing efforts and address any remaining issues."
        
        role_prompt += """
## SMART TESTING APPROACH
**ANALYZE FIRST**: Read README, check dependencies, assess what's feasible in automated environment

**FEASIBLE STRATEGIES**: Unit tests, static analysis, mock testing, code review
**AVOID**: Docker, database installs, external services, heavy infrastructure, GUI tools

**TESTING TRANSPARENCY REQUIRED**:
Your report must include:
1. **Coverage Summary**: What was tested automatically vs. code review vs. needs manual testing
2. **Limitations Section**: 
   ```
   ## Testing Limitations
   Due to automated environment constraints:
   - Docker functionality requires manual verification
   - Database connections need manual testing
   - External APIs require manual validation
   ```
3. **Review Focus**: Highlight code areas needing careful review due to limited automated testing

## TESTING FOCUS AREAS
**FUNCTIONALITY**: Core features, input validation, error handling, component integration
**CODE QUALITY**: Structure, standards compliance, documentation, security, performance  
**SETUP**: Installation process, dependencies, file organization

## REPORT STRUCTURE
1. **Executive Summary**: Overall Pass/Fail assessment with key findings
2. **Test Results**: What was tested and outcomes
3. **Issues Found**: Critical/Major/Minor issues with specific examples
4. **Recommendations**: Immediate actions needed and future improvements

**Be thorough but practical. Focus on real-world scenarios and provide actionable feedback.**
"""
        
        prompt_parts.append(role_prompt)
        return '\n\n'.join(prompt_parts)
    
    def _get_tester_workflow_context(self, workflow_type: str) -> str:
        """Get tester-specific workflow context"""
        workflow_contexts = {
            "bug_hunting": """
## WORKFLOW FOCUS: SECURITY & VULNERABILITY TESTING
Prioritize: Security vulnerabilities, input validation, access controls, dependency security
Testing: Lightweight security tools, acknowledge penetration testing limitations
""",
            "code_optimization": """
## WORKFLOW FOCUS: PERFORMANCE & EFFICIENCY TESTING
Prioritize: Performance benchmarking, memory profiling, algorithm efficiency, database performance
Testing: Simple timing tests and profiling, acknowledge load testing limitations
""",
            "custom_coding": """
## WORKFLOW FOCUS: COMPREHENSIVE QUALITY TESTING
Prioritize: Functional testing, unit testing, code quality assessment, documentation testing
Testing: Lightweight approaches, document limitations for complex scenarios
"""
        }
        
        return workflow_contexts.get(workflow_type, "")
    
    def get_role_description(self) -> str:
        """Get description of the Tester role"""
        return "Quality Assurance Tester - Validates implementations and ensures quality"
    

    
    def post_execution_hook(self, result: Dict[str, Any], 
                          context: AgentContext) -> Dict[str, Any]:
        """Post-process tester results to extract test metrics and findings"""
        if result["success"] and result["output"]:
            output = result["output"]
            
            # Extract test results and metrics
            test_analysis = {
                "overall_assessment": self._extract_overall_assessment(output),
                "critical_issues": self._extract_issues(output, "critical"),
                "major_issues": self._extract_issues(output, "major"),
                "minor_issues": self._extract_issues(output, "minor"),
                "test_coverage": self._estimate_test_coverage(output),
                "quality_score": self._calculate_quality_score(output),
                "recommendations": self._extract_recommendations(output)
            }
            
            # Add test analysis to result
            result["test_analysis"] = test_analysis
            
            # Determine if the implementation passes testing
            result["implementation_approved"] = self._determine_approval(test_analysis)
        
        return result
    
    def _extract_overall_assessment(self, text: str) -> str:
        """Extract the overall assessment from test output"""
        assessment_keywords = [
            "overall", "summary", "assessment", "conclusion", "verdict", "result"
        ]
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in assessment_keywords):
                # Extract the assessment section
                assessment_lines = []
                for j in range(i, min(i + 5, len(lines))):
                    assessment_lines.append(lines[j])
                return '\n'.join(assessment_lines).strip()
        
        return "No overall assessment found"
    
    def _extract_issues(self, text: str, severity: str) -> list:
        """Extract issues of a specific severity level"""
        text_lower = text.lower()
        severity_patterns = {
            "critical": ["critical", "blocker", "severe", "fatal"],
            "major": ["major", "important", "significant"],
            "minor": ["minor", "small", "trivial", "enhancement"]
        }
        
        patterns = severity_patterns.get(severity, [])
        issues = []
        
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(pattern in line_lower for pattern in patterns):
                clean_line = line.strip('- *#').strip()
                if len(clean_line) > 10:
                    issues.append(clean_line)
        
        return issues[:5]  # Limit to top 5 issues per severity
    
    def _estimate_test_coverage(self, text: str) -> str:
        """Estimate test coverage based on testing activities mentioned"""
        coverage_indicators = [
            "functionality", "unit test", "integration", "system test",
            "error handling", "edge case", "validation", "performance"
        ]
        
        text_lower = text.lower()
        covered_areas = [indicator for indicator in coverage_indicators 
                        if indicator in text_lower]
        
        coverage_percentage = (len(covered_areas) / len(coverage_indicators)) * 100
        return f"{coverage_percentage:.0f}% ({len(covered_areas)}/{len(coverage_indicators)} areas)"
    
    def _calculate_quality_score(self, text: str) -> float:
        """Calculate a quality score based on positive and negative indicators"""
        positive_indicators = [
            "works correctly", "passes", "successful", "good quality",
            "well implemented", "robust", "secure", "efficient"
        ]
        
        negative_indicators = [
            "fails", "error", "bug", "issue", "problem", "broken",
            "poor quality", "insecure", "inefficient"
        ]
        
        text_lower = text.lower()
        positive_count = sum(1 for indicator in positive_indicators 
                           if indicator in text_lower)
        negative_count = sum(1 for indicator in negative_indicators 
                           if indicator in text_lower)
        
        # Calculate score (0.0 to 1.0)
        total_indicators = positive_count + negative_count
        if total_indicators == 0:
            return 0.5  # Neutral score if no indicators found
        
        return positive_count / total_indicators
    
    def _extract_recommendations(self, text: str) -> list:
        """Extract recommendations from the test output"""
        recommendation_keywords = [
            "recommend", "suggest", "should", "improvement", "enhance",
            "fix", "address", "consider"
        ]
        
        lines = text.split('\n')
        recommendations = []
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in recommendation_keywords):
                clean_line = line.strip('- *#').strip()
                if len(clean_line) > 15 and len(clean_line) < 150:
                    recommendations.append(clean_line)
        
        return recommendations[:8]  # Limit to top 8 recommendations
    
    def _determine_approval(self, test_analysis: Dict[str, Any]) -> bool:
        """Determine if the implementation should be approved based on test results"""
        # Implementation is approved if:
        # 1. Quality score is above 0.6
        # 2. No critical issues
        # 3. Test coverage is reasonable
        
        quality_score = test_analysis.get("quality_score", 0.0)
        critical_issues = test_analysis.get("critical_issues", [])
        
        return quality_score >= 0.6 and len(critical_issues) == 0 