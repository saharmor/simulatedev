#!/bin/bash

# SimulateDev Integration Test Runner
# This script runs the integration tests for SimulateDev

echo "SimulateDev Integration Test Runner"
echo "=================================="

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Check if required packages are installed
echo "Checking dependencies..."
python3 -c "import asyncio, json, pathlib" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: Required Python packages are missing."
    echo "Please install requirements: pip install -r requirements.txt"
    exit 1
fi

# Change to tests directory
cd "$(dirname "$0")"

# Run the integration tests
echo "Starting integration tests..."
echo ""

python3 integration_test.py

# Capture exit code
exit_code=$?

# Print final status
echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ Integration tests completed successfully!"
else
    echo "❌ Integration tests failed!"
fi

echo "Check integration_test_report.json for detailed results."

exit $exit_code 