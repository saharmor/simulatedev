import pyttsx3

def count_and_speak():
    # The word to analyze
    word = "strawberry"
    
    # Count occurrences of 'r'
    count = word.count('r')
    
    # Initialize the text-to-speech engine
    engine = pyttsx3.init()
    
    # Create the message
    message = f"The letter r appears {count} times in the word {word}"
    
    # Speak the result
    print(message)  # Also print for visual feedback
    engine.say(message)
    engine.runAndWait()

if __name__ == "__main__":
    count_and_speak() 