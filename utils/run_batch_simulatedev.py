#!/usr/bin/env python3
"""
Batch SimulateDev Runner

This script runs simulatedev for every repository in example_repos.txt with the following configuration:
- First 5 repositories: Custom workflow to find and fix one critical bug
- Remaining repositories: Low-hanging fruit workflow to find one or two improvements
- Multi-agent setup: Windsurf as planner, Cursor as coder
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
import json
from datetime import datetime

# Import simulatedev modules
from simulatedev import execute_task
from common.config import config
from agents.base import MultiAgentTask, AgentDefinition, AgentRole, WorkflowType


@dataclass
class BatchResult:
    """Result of running simulatedev on a single repository"""
    repo_url: str
    workflow: str
    success: bool
    error_message: str = ""
    execution_time: float = 0.0


class BatchSimulateDevRunner:
    """Runner for executing simulatedev on multiple repositories"""
    
    def __init__(self, repos_file: str = "example_repos.txt"):
        self.repos_file = repos_file
        self.results: List[BatchResult] = []
        
    def load_repositories(self) -> List[str]:
        """Load repository URLs from the repos file"""
        repos_file_path = Path(self.repos_file)
        if not repos_file_path.exists():
            raise FileNotFoundError(f"Repository file not found: {self.repos_file}")
        
        repos = []
        with open(repos_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    repos.append(line)
        
        if not repos:
            raise ValueError(f"No repositories found in {self.repos_file}")
        
        print(f"Loaded {len(repos)} repositories from {self.repos_file}")
        return repos
    
    def create_multi_agent_task(self, workflow: str, task_description: str = None) -> MultiAgentTask:
        """Create a multi-agent task configuration with Windsurf as planner and Cursor as coder"""
        agents = [
            AgentDefinition(
                coding_ide="windsurf",
                model="claude-sonnet-4",
                role=AgentRole.PLANNER
            ),
            AgentDefinition(
                coding_ide="cursor",
                model="claude-sonnet-4", 
                role=AgentRole.CODER
            )
        ]
        
        # Map workflow strings to WorkflowType enums
        workflow_mapping = {
            "custom": WorkflowType.CUSTOM_CODING,
            "bug-hunting": WorkflowType.BUG_HUNTING,
            "low-hanging": WorkflowType.CODE_OPTIMIZATION
        }
        
        workflow_type = workflow_mapping.get(workflow, WorkflowType.CUSTOM_CODING)
        
        return MultiAgentTask(
            agents=agents,
            workflow=workflow_type,
            coding_task_prompt=task_description
        )
    
    def create_args_for_repo(self, repo_url: str, workflow: str, task_description: str = None) -> argparse.Namespace:
        """Create arguments object for a specific repository and workflow using multi-agent setup"""
        args = argparse.Namespace()
        args.repo = repo_url
        args.workflow = workflow
        args.agent = None  # Not used for multi-agent
        
        # Create multi-agent task configuration and convert to JSON string
        multi_agent_task = self.create_multi_agent_task(workflow, task_description)
        # Convert to JSON string format that execute_task expects
        agents_json = json.dumps([agent.to_dict() for agent in multi_agent_task.agents])
        args.coding_agents = agents_json
        
        args.task = task_description
        args.target_dir = None
        args.work_dir = None
        args.no_pr = False  # Create PRs by default
        args.output = None
        args.no_report = False
        args.no_delete_existing_repo_env = False
        
        return args
    
    async def run_simulatedev_for_repo(self, repo_url: str, workflow: str, task_description: str = None) -> BatchResult:
        """Run simulatedev for a single repository"""
        print(f"\n{'='*80}")
        print(f"Processing: {repo_url}")
        print(f"Workflow: {workflow}")
        print(f"Multi-agent setup: Windsurf (Planner) + Cursor (Coder)")
        if task_description:
            print(f"Task: {task_description}")
        print(f"{'='*80}")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Create arguments for this repository
            args = self.create_args_for_repo(repo_url, workflow, task_description)
            
            # Execute the task
            success = await execute_task(args)
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            result = BatchResult(
                repo_url=repo_url,
                workflow=workflow,
                success=success,
                execution_time=execution_time
            )
            
            if success:
                print(f"✅ SUCCESS: {repo_url} completed successfully in {execution_time:.1f}s")
            else:
                print(f"❌ FAILED: {repo_url} failed after {execution_time:.1f}s")
                result.error_message = "Task execution failed"
            
            return result
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            error_msg = str(e)
            
            print(f"❌ ERROR: {repo_url} failed with exception: {error_msg}")
            
            return BatchResult(
                repo_url=repo_url,
                workflow=workflow,
                success=False,
                error_message=error_msg,
                execution_time=execution_time
            )
    
    async def run_batch(self, dry_run: bool = False) -> List[BatchResult]:
        """Run simulatedev for all repositories in the batch"""
        repos = self.load_repositories()
        
        print(f"\n🚀 Starting batch execution for {len(repos)} repositories")
        print(f"Configuration:")
        print(f"  - First 5 repos: Custom workflow (find and fix one critical bug)")
        print(f"  - Remaining repos: Code optimization workflow")
        print(f"  - Multi-agent setup: Windsurf (Planner) + Cursor (Coder)")
        print(f"  - Dry run: {dry_run}")
        
        if dry_run:
            print("\n📋 DRY RUN - Would execute the following:")
            for i, repo in enumerate(repos, 1):
                if i <= 5:
                    workflow = "custom"
                    task = "Find and fix one critical bug that could cause production incidents, security breaches, or data corruption. Focus on high-impact issues like authentication bypasses, injection vulnerabilities, race conditions, or logic bombs that affect core functionality."
                    print(f"  {i:2d}. {repo} -> {workflow} (critical bug fix) [Windsurf+Cursor]")
                else:
                    workflow = "low-hanging"
                    print(f"  {i:2d}. {repo} -> {workflow} [Windsurf+Cursor]")
            return []
        
        # Execute for each repository
        for i, repo in enumerate(repos, 1):
            try:
                if i <= 5:
                    # First 5 repositories: Custom workflow to find and fix critical bugs
                    workflow = "custom"
                    task_description = """Find and fix one critical bug that could cause production incidents, security breaches, or data corruption. Focus on high-impact issues like:

1. **Critical Security Flaws**: Authentication bypasses, injection vulnerabilities, privilege escalation
2. **Data Integrity Issues**: Race conditions causing data corruption, transaction boundary problems  
3. **Reliability Killers**: Resource leaks, infinite loops, unhandled exceptions in critical paths
4. **Logic Bombs**: Edge cases that cause incorrect business logic execution

Choose the SINGLE most critical bug that maximizes security/reliability impact while remaining fixable in a focused, reviewable PR. Provide clear documentation of the vulnerability and implement a secure fix with appropriate tests."""
                    
                    result = await self.run_simulatedev_for_repo(repo, workflow, task_description)
                else:
                    # Remaining repositories: Code optimization workflow
                    workflow = "low-hanging"
                    result = await self.run_simulatedev_for_repo(repo, workflow)
                
                self.results.append(result)
                
            except KeyboardInterrupt:
                print(f"\n⏹️  Batch execution interrupted by user after {i-1} repositories")
                break
            except Exception as e:
                print(f"❌ Unexpected error processing {repo}: {str(e)}")
                error_result = BatchResult(
                    repo_url=repo,
                    workflow="custom" if i <= 5 else "low-hanging",
                    success=False,
                    error_message=f"Unexpected error: {str(e)}"
                )
                self.results.append(error_result)
        
        return self.results
    
    def print_summary(self):
        """Print a summary of all batch results"""
        if not self.results:
            print("\n📊 No results to summarize")
            return
        
        print(f"\n{'='*80}")
        print(f"📊 BATCH EXECUTION SUMMARY")
        print(f"{'='*80}")
        
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        total_time = sum(r.execution_time for r in self.results)
        
        print(f"Total repositories processed: {len(self.results)}")
        print(f"Successful: {len(successful)} ✅")
        print(f"Failed: {len(failed)} ❌")
        print(f"Success rate: {len(successful)/len(self.results)*100:.1f}%")
        print(f"Total execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        print(f"Multi-agent setup: Windsurf (Planner) + Cursor (Coder)")
        
        if successful:
            print(f"\n✅ SUCCESSFUL REPOSITORIES:")
            for result in successful:
                print(f"  - {result.repo_url} ({result.workflow}) - {result.execution_time:.1f}s")
        
        if failed:
            print(f"\n❌ FAILED REPOSITORIES:")
            for result in failed:
                print(f"  - {result.repo_url} ({result.workflow}) - {result.error_message}")
    
    def save_results(self, output_file: str = None):
        """Save batch results to a JSON file"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"batch_simulatedev_results_{timestamp}.json"
        
        # Convert results to dictionaries for JSON serialization
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "agent_setup": "multi-agent: Windsurf (Planner) + Cursor (Coder)",
            "total_repos": len(self.results),
            "successful": len([r for r in self.results if r.success]),
            "failed": len([r for r in self.results if not r.success]),
            "total_execution_time": sum(r.execution_time for r in self.results),
            "results": [
                {
                    "repo_url": r.repo_url,
                    "workflow": r.workflow,
                    "success": r.success,
                    "error_message": r.error_message,
                    "execution_time": r.execution_time
                }
                for r in self.results
            ]
        }
        
        # Ensure output directory exists
        output_path = Path(output_file)
        if output_path.parent != Path('.'):
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"📄 Results saved to: {output_file}")


async def main():
    """Main entry point for the batch runner"""
    parser = argparse.ArgumentParser(
        description="Run SimulateDev for multiple repositories in batch with multi-agent setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run batch execution for all repos in example_repos.txt
  python run_batch_simulatedev.py
  
  # Dry run to see what would be executed
  python run_batch_simulatedev.py --dry-run
  
  # Use a custom repos file
  python run_batch_simulatedev.py --repos-file my_repos.txt
  
  # Save results to a custom file
  python run_batch_simulatedev.py --output batch_results.json

Configuration:
  - First 5 repositories: Custom workflow to find and fix one critical bug
  - Remaining repositories: Code optimization workflow
  - Multi-agent setup: Windsurf (Planner) + Cursor (Coder)
        """
    )
    
    parser.add_argument("--repos-file", default="example_repos.txt",
                       help="File containing repository URLs (default: example_repos.txt)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be executed without actually running")
    parser.add_argument("--output", help="Output file for batch results (JSON format)")
    
    args = parser.parse_args()
    
    try:
        # Create and run the batch runner
        runner = BatchSimulateDevRunner(args.repos_file)
        results = await runner.run_batch(dry_run=args.dry_run)
        
        if not args.dry_run:
            # Print summary and save results
            runner.print_summary()
            runner.save_results(args.output)
        
        print(f"\n🎉 Batch execution completed!")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Batch execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Batch execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 