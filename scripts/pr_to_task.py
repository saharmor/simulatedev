#!/usr/bin/env python3
"""
PR to Task Script for SimulateDev

This script reads a GitHub pull request URL and either:
1. Processes it with a custom task using SimulateDev, or
2. Automatically analyzes PR review comments and generates code to address them

The script can push changes directly to the PR branch with descriptive commit messages.

Usage:
    # Custom task mode
    python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --task "Review and improve this code" --agent cursor
    python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --task "Add tests for this feature" --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'
    
    # Review comments mode - automatically address PR feedback
    python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --review-comments --agent cursor
"""

import argparse
import asyncio
import os
import sys
import tempfile
from dotenv import load_dotenv

# Add the parent directory to Python path to import SimulateDev modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import SimulateDev modules
from simulatedev import execute_task, validate_coding_agents_json, create_default_coder_agent
from agents import CodingAgentIdeType
from src.github_integration import GitHubPRProcessor

# Load environment variables
load_dotenv()


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Process GitHub PR with SimulateDev Custom Task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single agent
  python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --task "Add error handling" --agent cursor
  
  # Multi-agent
  python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --task "Review and add tests" \\
    --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'
  
  # Test mode (no push)
  python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --task "Code review" --agent cursor --no-push
  
  # Review comments mode - automatically address PR review comments
  python pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --review-comments --agent cursor
        """
    )
    
    # Required arguments
    parser.add_argument("--pr-url", required=True, 
                       help="GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)")
    
    # Task specification (either custom task or review comments)
    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task",
                           help="Custom task description to perform on the PR")
    task_group.add_argument("--review-comments", action="store_true",
                           help="Automatically address all PR review comments and feedback")
    
    # Agent specification (either single agent or multi-agent JSON)
    agent_group = parser.add_mutually_exclusive_group(required=True)
    agent_group.add_argument("--agent", 
                           choices=[agent.value for agent in CodingAgentIdeType],
                           help="Single AI coding agent to use")
    agent_group.add_argument("--coding-agents", 
                           help="JSON array of coding agents for multi-agent workflows")
    
    # Optional arguments
    parser.add_argument("--no-push", action="store_true", 
                       help="Don't push changes to PR branch (just print results)")
    parser.add_argument("--target-dir", 
                       help="Target directory for cloning (default: temp directory)")
    parser.add_argument("--output", 
                       help="Output file for execution report")
    parser.add_argument("--no-report", action="store_true", 
                       help="Skip saving execution report")
    
    return parser.parse_args()


async def main():
    """Main function to process GitHub PR and run SimulateDev"""
    try:
        args = parse_arguments()
        
        print("PR to Task Processor for SimulateDev")
        print("=" * 50)
        
        # Initialize GitHub PR processor
        processor = GitHubPRProcessor()
        
        # Parse PR URL
        print(f"Parsing PR URL: {args.pr_url}")
        repo_info = processor.parse_pr_url(args.pr_url)
        print(f"Repository: {repo_info['owner']}/{repo_info['repo']}")
        print(f"PR Number: #{repo_info['pr_number']}")
        
        # Fetch PR data
        print("Fetching PR data from GitHub...")
        pr_data = processor.fetch_pr_data(
            repo_info['owner'], 
            repo_info['repo'], 
            repo_info['pr_number']
        )
        
        print(f"PR Title: {pr_data.get('title', 'Untitled')}")
        
        # Get PR diff
        print("Fetching PR diff...")
        pr_diff = processor.get_pr_diff(
            repo_info['owner'], 
            repo_info['repo'], 
            repo_info['pr_number']
        )
        
        # Determine task based on mode
        if args.review_comments:
            print("Analyzing PR comments and generating review response task...")
            task_prompt = processor.analyze_pr_comments_and_generate_task(pr_data)
            if "No comments or reviews found" in task_prompt:
                print("ℹ️  No actionable comments found on this PR.")
                return True
            task_description = "Address PR review comments and feedback"
        else:
            print("Synthesizing custom task prompt...")
            task_prompt = processor.synthesize_pr_task_prompt(pr_data, repo_info, args.task, pr_diff)
            task_description = args.task
        
        # Parse coding agents
        if args.coding_agents:
            try:
                agents = validate_coding_agents_json(args.coding_agents)
                print(f"Using {len(agents)} custom agents")
            except ValueError as e:
                print(f"Error parsing coding agents: {e}")
                return False
        else:
            agents = create_default_coder_agent(args.agent)
            print(f"Using default single {args.agent} agent")
        
        # Determine target directory
        if args.target_dir:
            target_dir = args.target_dir
        else:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="simulatedev_pr_")
            target_dir = os.path.join(temp_dir, f"{repo_info['repo']}")
        
        # Clone PR branch
        head_branch = pr_data.get('head', {}).get('ref', 'main')
        print(f"Cloning repository to work on branch '{head_branch}'...")
        
        try:
            processor.clone_pr_branch(repo_info['repo_url'], head_branch, target_dir)
        except ValueError as e:
            print(f"Error cloning repository: {e}")
            return False
        
        # Create arguments for SimulateDev execution
        simulatedev_args = argparse.Namespace()
        simulatedev_args.workflow = "custom"
        simulatedev_args.repo = repo_info['repo_url']
        simulatedev_args.task = task_prompt
        simulatedev_args.agent = args.agent if not args.coding_agents else None
        simulatedev_args.coding_agents = args.coding_agents
        simulatedev_args.target_dir = None  # We already cloned
        simulatedev_args.work_dir = target_dir
        simulatedev_args.no_pr = True  # Don't create new PR, we're working on existing one
        simulatedev_args.output = args.output
        simulatedev_args.no_report = args.no_report
        simulatedev_args.no_delete_existing_repo_env = True  # Keep our cloned repo
        
        print("\nTask Summary:")
        print(f"  PR: #{repo_info['pr_number']} - {pr_data.get('title', 'Untitled')}")
        print(f"  Repository: {repo_info['repo_url']}")
        print(f"  Branch: {head_branch}")
        print(f"  Mode: {'Review Comments' if args.review_comments else 'Custom Task'}")
        print(f"  Task: {task_description}")
        print(f"  Agents: {len(agents)} agent(s)")
        for i, agent in enumerate(agents, 1):
            print(f"    {i}. {agent.role.value} - {agent.coding_ide} ({agent.model})")
        print(f"  Push Changes: {'No' if args.no_push else 'Yes'}")
        
        # Execute SimulateDev task
        print(f"\nSTARTING: Processing PR #{repo_info['pr_number']} with custom task...")
        try:
            success = await execute_task(simulatedev_args)
            
            if success:
                print(f"\n✅ COMPLETED: PR #{repo_info['pr_number']} processed successfully!")
                
                # Check for changes and push if requested
                if not args.no_push:
                    if processor.check_for_changes(target_dir):
                        print("Changes detected. Committing and pushing to PR branch...")
                        if args.review_comments:
                            push_success = processor.commit_and_push_review_changes(
                                target_dir, head_branch, pr_data
                            )
                        else:
                            push_success = processor.commit_and_push_changes(
                                target_dir, head_branch, args.task
                            )
                        
                        if push_success:
                            print(f"🚀 Changes pushed to PR branch '{head_branch}'!")
                            print(f"📋 You can review the updated PR at: {pr_data.get('html_url', '')}")
                            
                            if args.review_comments:
                                print("💡 The changes address the review comments. Consider:")
                                print("   - Replying to individual comments to explain your changes")
                                print("   - Requesting a re-review from the original reviewers")
                        else:
                            print("❌ Failed to push changes to PR branch")
                    else:
                        print("ℹ️  No changes were made by SimulateDev")
                else:
                    if processor.check_for_changes(target_dir):
                        print("ℹ️  Changes were made but not pushed (--no-push flag used)")
                    else:
                        print("ℹ️  No changes were made by SimulateDev")
                        
            else:
                print(f"\n❌ FAILED: PR #{repo_info['pr_number']} processing failed.")
                print("Check the output above for specific error details.")
            
            return success
            
        except Exception as task_error:
            print(f"\n❌ ERROR: Exception occurred while processing PR #{repo_info['pr_number']}: {str(task_error)}")
            return False
        
    except KeyboardInterrupt:
        print("\nTask interrupted by user")
        return False
    except Exception as e:
        print(f"Error processing PR: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 