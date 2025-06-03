import subprocess

def count_and_speak():
    # The word to analyze
    word = "strawberry"
    
    # Count occurrences of 'r'
    count = word.count('r')
    
    # Create the message
    message = f"The letter r appears {count} times in the word {word}"
    
    # Create the AppleScript command
    applescript = f'''
    say "{message}"
    '''
    
    # Execute the AppleScript command
    subprocess.run(["osascript", "-e", applescript])
    
    # Also print for visual feedback
    print(message)

if __name__ == "__main__":
    count_and_speak() 