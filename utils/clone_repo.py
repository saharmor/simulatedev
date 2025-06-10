#!/usr/bin/env python3
"""
Repository Cloner for AI Bug-Hunting Project

This script clones a git repository into a specified local directory.
It's designed to help prepare repositories for AI-powered bug discovery.

Usage:
    python clone_repo.py <repository_url> [target_directory]

If target_directory is not specified, the repository will be cloned into 
a directory named after the repository in the current working directory.
"""

import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse


def parse_repo_name(repo_url):
    """Extract repository name from URL."""
    path = urlparse(repo_url).path
    repo_name = path.strip('/').split('/')[-1]
    
    # Remove .git extension if present
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    
    return repo_name


def clone_repository(repo_url, target_dir=None):
    """
    Clone a git repository to a local directory.
    
    Args:
        repo_url (str): URL of the repository to clone
        target_dir (str, optional): Directory to clone into. If not specified,
                                  uses the repository name in the current directory.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # If target directory not specified, use repo name in current directory
        if not target_dir:
            repo_name = parse_repo_name(repo_url)
            target_dir = os.path.join(os.getcwd(), repo_name)
        
        # Create parent directory if it doesn't exist
        parent_dir = os.path.dirname(target_dir)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # Clone the repository
        print(f"Cloning {repo_url} into {target_dir}...")
        subprocess.run(["git", "clone", repo_url, target_dir], 
                      check=True, 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE)
        
        print(f"Repository successfully cloned to {target_dir}")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e.stderr.decode()}")
        return False
    
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Clone a git repository for AI bug-hunting."
    )
    parser.add_argument(
        "repo_url", 
        help="URL of the repository to clone"
    )
    parser.add_argument(
        "target_dir", 
        nargs="?", 
        default=None,
        help="Directory to clone the repository into (optional)"
    )
    
    args = parser.parse_args()
    
    success = clone_repository(args.repo_url, args.target_dir)
    
    if success:
        print("Ready for AI bug hunting!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
