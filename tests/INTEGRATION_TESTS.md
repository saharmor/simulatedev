# SimulateDev Integration Tests

This document describes the integration testing setup for SimulateDev, which validates the core functionality of both single-agent and multi-agent scenarios.

## Overview

The integration tests run two key scenarios:

1. **Single Agent Scenario**: Tests a single Windsurf coder agent
2. **Multi-Agent Scenario**: Tests collaboration between Windsurf coder and Cursor tester agents

Both scenarios use a simple task to ensure quick execution while validating core functionality.

## Test Task

The test task is intentionally simple to minimize execution time:

> "Create a local hello world file that counts the occurrences of the letter 'r' in the word 'strawberry'. The file should be named 'hello_world_strawberry.py' and should print both the word and the count."

This task validates:
- File creation capabilities
- Basic coding logic implementation
- String manipulation
- Output generation

## Test Scenarios

### Scenario 1: Single Agent
- **Agent**: Windsurf (Coder role)
- **Model**: Claude 4 Sonnet
- **Repository**: https://github.com/saharmor/gemini-multimodal-playground
- **Expected Outcome**: PR created successfully with the hello world file

### Scenario 2: Multi-Agent
- **Agent 1**: Windsurf (Coder role) with Claude 4 Sonnet
- **Agent 2**: Cursor (Tester role) with Claude 4 Sonnet
- **Repository**: https://github.com/saharmor/gemini-multimodal-playground
- **Expected Outcome**: 
  - Both agents execute in sequence (coder first, then tester)
  - PR created successfully
  - Test results available

## Running the Tests

### Method 1: Using the Shell Script (Recommended)

```bash
./run_integration_tests.sh
```

This script will:
- Check for Python 3 availability
- Activate virtual environment if available
- Verify dependencies
- Run the integration tests
- Display results

### Method 2: Direct Python Execution

```bash
python3 integration_test.py
```

## Test Results

### Console Output
The tests provide real-time feedback with:
- Scenario descriptions
- Execution progress
- Pass/fail status with ✅/❌ indicators
- Summary statistics

### JSON Report
Detailed results are saved to `execution_output/{timestamp}_integration_test_report.json` containing:
- Test execution timestamp
- Individual scenario results
- Execution times
- Error details (if any)
- Agent execution logs

### Example Report Structure
```json
{
  "test_run_timestamp": "2024-01-15T10:30:00.000Z",
  "total_scenarios": 2,
  "passed_scenarios": 2,
  "failed_scenarios": 0,
  "test_results": [
    {
      "scenario": "Single Agent Scenario",
      "success": true,
      "timestamp": "2024-01-15T10:30:15.000Z",
      "details": {
        "execution_time": 45.2,
        "response_success": true,
        "pr_created": true,
        "final_output": "...",
        "execution_log_count": 3
      }
    }
  ]
}
```

## Success Criteria

### Single Agent Scenario
- ✅ Agent executes without errors
- ✅ Task completes successfully
- ✅ Pull request is created
- ✅ No console errors

### Multi-Agent Scenario
- ✅ Coder agent executes first
- ✅ Tester agent executes second
- ✅ Both agents complete successfully
- ✅ Pull request is created
- ✅ Test results are generated
- ✅ No console errors

## Troubleshooting

### Common Issues

1. **Missing Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Virtual Environment Issues**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Permission Issues**
   ```bash
   chmod +x run_integration_tests.sh
   ```

4. **GitHub Authentication**
   - Ensure GitHub credentials are properly configured
   - Check that the repository URL is accessible

### Debug Mode

For detailed debugging, you can modify the integration test script to add more verbose logging or run individual scenarios.

## Configuration

The integration tests use these default configurations:

- **Repository**: `https://github.com/saharmor/gemini-multimodal-playground`
- **Models**: Claude 4 Sonnet for all agents
- **Workflow**: Custom coding
- **PR Creation**: Enabled
- **Clean Slate**: Repository is re-cloned for each test

These can be modified in the `IntegrationTestRunner` class in `integration_test.py`.

## Extending the Tests

To add new test scenarios:

1. Create a new method in `IntegrationTestRunner` class
2. Follow the pattern of existing scenarios
3. Add the scenario to `run_all_tests()` method
4. Update this documentation

## Performance Expectations

- **Single Agent Scenario**: ~30-60 seconds
- **Multi-Agent Scenario**: ~60-120 seconds
- **Total Test Suite**: ~2-3 minutes

Times may vary based on:
- Network connectivity
- Repository size
- Agent response times
- System performance 