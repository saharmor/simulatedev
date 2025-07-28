#!/bin/bash
#
# Tmux Tests Runner
# =================
# Convenience script to run all tmux-related tests
#

set -e  # Exit on any error

echo "🧪 Running Tmux Tests Suite"
echo "=========================="
echo

# Check if we're in the right directory
if [ ! -f "tmux_operations_manager.py" ]; then
    echo "❌ Error: Please run this script from the simulatedev project root directory"
    echo "   Current directory: $(pwd)"
    echo "   Expected files: tmux_operations_manager.py"
    exit 1
fi

# Check if tmux is available
if ! command -v tmux &> /dev/null; then
    echo "❌ Error: tmux is not installed or not in PATH"
    echo "   Please install tmux: brew install tmux (macOS) or apt-get install tmux (Ubuntu)"
    exit 1
fi

# Check for required API key
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  Warning: GEMINI_API_KEY environment variable is not set"
    echo "   Some tests may fail without proper API credentials"
    echo
fi

echo "📋 Running focused concurrency tests..."
echo "======================================"
python3 tmux_tests/test_tmux_concurrency_bug_focused.py

echo
echo "📋 Running cross-pane isolation tests..."
echo "======================================="
python3 tmux_tests/test_tmux_cross_pane_input.py

echo
echo "🎉 All tmux tests completed!"
echo "==========================" 