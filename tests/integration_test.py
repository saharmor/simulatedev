#!/usr/bin/env python3
"""
Integration Testing Script for SimulateDev

This script runs two integration test scenarios:
1. Single agent scenario: Windsurf coder with simple hello world task
2. Multi-agent scenario: Windsurf coder + Cursor tester with the same task

Both scenarios use a simple task to count occurrences of 'r' in 'strawberry'
to ensure quick execution and easy validation.
"""

import asyncio
import json
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent  # Go up one level from tests/ to project root
sys.path.insert(0, str(project_root))

from src.orchestrator import Orchestrator, TaskRequest
from agents import AgentDefinition, AgentRole


class IntegrationTestRunner:
    """Runner for integration tests"""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.test_results = []
        self.repo_url = "https://github.com/saharmor/gemini-multimodal-playground"
        self.simple_task = "Create a local hello world file that counts the occurrences of the letter 'r' in the word 'strawberry'. The file should be named 'hello_world_strawberry.py' and should print both the word and the count."
        
    def log_test_result(self, scenario_name: str, success: bool, details: Dict[str, Any]):
        """Log test result"""
        result = {
            "scenario": scenario_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status} - {scenario_name}")
        if not success and "error" in details:
            print(f"Error: {details['error']}")
    
    def check_pr_created(self, response) -> bool:
        """Check if PR was created successfully"""
        if not response.success:
            return False
            
        # Check execution log for PR creation
        for log_entry in response.execution_log:
            if "pr_url" in log_entry or "pull_request" in str(log_entry).lower():
                return True
                
        # Check final output for PR indicators
        if "pull request" in response.final_output.lower() or "pr" in response.final_output.lower():
            return True
            
        return False
    
    async def run_single_agent_scenario(self) -> bool:
        """
        Scenario 1: Single Windsurf coder agent
        Task: Create hello world file counting 'r' in 'strawberry'
        Expected: PR created successfully, no console errors
        """
        print("\n" + "="*60)
        print("SCENARIO 1: Single Agent (Windsurf Coder)")
        print("="*60)
        
        try:
            # Create single agent request
            agents = [AgentDefinition(
                coding_ide="windsurf",
                model="claude-4-sonnet",
                role=AgentRole.CODER
            )]
            
            request = TaskRequest(
                task_description=self.simple_task,
                agents=agents,
                workflow_type="general_coding",
                repo_url=self.repo_url,
                create_pr=True,
                delete_existing=True  # Clean slate for testing
            )
            
            print(f"Task: {self.simple_task}")
            print(f"Repository: {self.repo_url}")
            print(f"Agent: Windsurf (Coder) with Claude 4 Sonnet")
            print("\nExecuting...")
            
            start_time = time.time()
            response = await self.orchestrator.execute_task(request)
            execution_time = time.time() - start_time
            
            # Check results
            pr_created = self.check_pr_created(response)
            
            details = {
                "execution_time": execution_time,
                "response_success": response.success,
                "pr_created": pr_created,
                "final_output": response.final_output[:500] + "..." if len(response.final_output) > 500 else response.final_output,
                "execution_log_count": len(response.execution_log),
                "error_message": response.error_message
            }
            
            success = response.success and pr_created
            self.log_test_result("Single Agent Scenario", success, details)
            
            return success
            
        except Exception as e:
            details = {
                "error": str(e),
                "error_type": type(e).__name__
            }
            self.log_test_result("Single Agent Scenario", False, details)
            return False
    
    async def run_multi_agent_scenario(self) -> bool:
        """
        Scenario 2: Multi-agent with Windsurf coder and Cursor tester
        Task: Same hello world file counting 'r' in 'strawberry'
        Expected: Both agents run in sequence, PR created successfully
        """
        print("\n" + "="*60)
        print("SCENARIO 2: Multi-Agent (Windsurf Coder + Cursor Tester)")
        print("="*60)
        
        try:
            # Create multi-agent request
            agents = [
                AgentDefinition(
                    coding_ide="windsurf",
                    model="claude-4-sonnet",
                    role=AgentRole.CODER
                ),
                AgentDefinition(
                    coding_ide="cursor",
                    model="claude-4-sonnet",
                    role=AgentRole.TESTER
                )
            ]
            
            request = TaskRequest(
                task_description=self.simple_task,
                agents=agents,
                workflow_type="general_coding",
                repo_url=self.repo_url,
                create_pr=True,
                delete_existing=True  # Clean slate for testing
            )
            
            print(f"Task: {self.simple_task}")
            print(f"Repository: {self.repo_url}")
            print(f"Agents:")
            print(f"  1. Windsurf (Coder) with Claude 4 Sonnet")
            print(f"  2. Cursor (Tester) with Claude 4 Sonnet")
            print("\nExecuting...")
            
            start_time = time.time()
            response = await self.orchestrator.execute_task(request)
            execution_time = time.time() - start_time
            
            # Check results
            pr_created = self.check_pr_created(response)
            
            # Check if both agents executed
            coder_executed = any("coder" in str(log).lower() or "windsurf" in str(log).lower() 
                               for log in response.execution_log)
            tester_executed = any("tester" in str(log).lower() or "cursor" in str(log).lower() 
                                for log in response.execution_log)
            
            details = {
                "execution_time": execution_time,
                "response_success": response.success,
                "pr_created": pr_created,
                "coder_executed": coder_executed,
                "tester_executed": tester_executed,
                "both_agents_executed": coder_executed and tester_executed,
                "final_output": response.final_output[:500] + "..." if len(response.final_output) > 500 else response.final_output,
                "execution_log_count": len(response.execution_log),
                "test_results": response.test_results,
                "error_message": response.error_message
            }
            
            success = response.success and pr_created and coder_executed and tester_executed
            self.log_test_result("Multi-Agent Scenario", success, details)
            
            return success
            
        except Exception as e:
            details = {
                "error": str(e),
                "error_type": type(e).__name__
            }
            self.log_test_result("Multi-Agent Scenario", False, details)
            return False
    
    def save_test_report(self, filename: str = "integration_test_report.json"):
        """Save test results to JSON file"""
        report = {
            "test_run_timestamp": datetime.now().isoformat(),
            "total_scenarios": len(self.test_results),
            "passed_scenarios": sum(1 for r in self.test_results if r["success"]),
            "failed_scenarios": sum(1 for r in self.test_results if not r["success"]),
            "test_results": self.test_results
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nTest report saved to: {filename}")
        return filename
    
    def print_summary(self):
        """Print test execution summary"""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["success"])
        failed = total - passed
        
        print("\n" + "="*60)
        print("INTEGRATION TEST SUMMARY")
        print("="*60)
        print(f"Total Scenarios: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        if failed > 0:
            print("\nFailed Scenarios:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['scenario']}: {result['details'].get('error', 'Unknown error')}")
        
        print("\nDetailed results saved in integration_test_report.json")
    
    async def run_all_tests(self):
        """Run all integration test scenarios"""
        print("SimulateDev Integration Testing")
        print("="*60)
        print("Running two scenarios with simple strawberry counting task")
        print("This ensures quick execution while validating core functionality")
        
        # Run scenarios
        scenario1_success = await self.run_single_agent_scenario()
        scenario2_success = await self.run_multi_agent_scenario()
        
        # Generate report
        self.save_test_report()
        self.print_summary()
        
        # Return overall success
        return scenario1_success and scenario2_success


async def main():
    """Main entry point for integration testing"""
    try:
        runner = IntegrationTestRunner()
        success = await runner.run_all_tests()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error during test execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Ensure we're in the right directory
    os.chdir(project_root)
    
    # Run the integration tests
    asyncio.run(main()) 