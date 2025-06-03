#!/usr/bin/env python3
import os

def list_files_in_directory(directory="."):
    """
    Lists all files in the specified directory.
    
    Args:
        directory (str): Directory path to list files from. Defaults to current directory.
    """
    print(f"Files in {os.path.abspath(directory)}:")
    print("-" * 50)
    
    try:
        # Get list of all files and directories
        items = os.listdir(directory)
        
        # Sort alphabetically
        items.sort()
        
        # Print each item, marking directories
        for item in items:
            path = os.path.join(directory, item)
            if os.path.isdir(path):
                print(f"📁 {item}/")
            else:
                print(f"📄 {item}")
        
        print("-" * 50)
        print(f"Total items: {len(items)}")
    
    except Exception as e:
        print(f"Error listing files: {e}")

if __name__ == "__main__":
    list_files_in_directory() 