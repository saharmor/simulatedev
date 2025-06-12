#!/bin/bash

# Docker entrypoint script for SimulateDev
set -e

echo "Starting SimulateDev Docker Container..."

# Configure git if environment variables are provided
if [ -n "$GIT_USER_NAME" ]; then
    git config --global user.name "$GIT_USER_NAME"
    echo "Git user name set to: $GIT_USER_NAME"
fi

if [ -n "$GIT_USER_EMAIL" ]; then
    git config --global user.email "$GIT_USER_EMAIL"
    echo "Git user email set to: $GIT_USER_EMAIL"
fi

# Check for required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: ANTHROPIC_API_KEY not set. This is required for Claude Computer Use."
fi



# Set up X11 display if not already configured
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:99
fi

# Start Xvfb (X Virtual Framebuffer) for GUI applications
echo "Starting virtual display..."
Xvfb $DISPLAY -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for X server to start
sleep 2

# Verify X server is running
if ! xdpyinfo -display $DISPLAY >/dev/null 2>&1; then
    echo "ERROR: Failed to start X server"
    exit 1
fi

echo "Virtual display started successfully on $DISPLAY"

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    if [ -n "$XVFB_PID" ]; then
        kill $XVFB_PID 2>/dev/null || true
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Change to application directory
cd /app

# If no arguments provided, show help
if [ $# -eq 0 ]; then
    echo "SimulateDev Docker Container"
    echo "Usage examples:"
    echo ""
    echo "  # Show help"
    echo "  docker run simulatedev"
    echo ""
    echo "  # Run a coding task"
    echo "  docker run -e ANTHROPIC_API_KEY=your_key \\"
    echo "    simulatedev python3 simulatedev.py \\"
    echo "    --task 'Fix responsive design' \\"
    echo "    --repo https://github.com/user/repo \\"
    echo "    --workflow general_coding"
    echo ""
    echo "Environment variables needed:"
    echo "  - ANTHROPIC_API_KEY (required)"
    echo ""
    echo "  - GITHUB_TOKEN (optional, for PR creation)"
    echo "  - GIT_USER_NAME (optional)"
    echo "  - GIT_USER_EMAIL (optional)"
    echo ""
    python3 simulatedev.py --help
else
    # Execute the provided command
    exec "$@"
fi 