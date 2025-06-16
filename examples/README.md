# SimulateDev Examples

This directory contains example configuration files for different types of tasks that can be executed with SimulateDev.

## Sample Task Files

### `sample_bug_hunting_task.json`
Example configuration for bug hunting workflow with a single Coder agent using Cursor IDE.

### `sample_multi_agent_task.json`
Example configuration for a custom coding task with multiple agents:
- Coder agent using Windsurf IDE
- Tester agent using Cursor IDE

### `sample_optimization_task.json`
Example configuration for code optimization workflow with three agents:
- Planner agent using Claude
- Coder agent using Windsurf IDE  
- Tester agent using Cursor IDE

## Usage

You can use these example files with the SimulateDev CLI:

```bash
# Run a bug hunting task
python simulatedev.py --multi examples/sample_bug_hunting_task.json --repo https://github.com/your/repo

# Run a multi-agent coding task
python simulatedev.py --multi examples/sample_multi_agent_task.json --repo https://github.com/your/repo

# Run a code optimization task
python simulatedev.py --multi examples/sample_optimization_task.json --repo https://github.com/your/repo
```

## Customization

Feel free to modify these examples or create your own task configurations based on your specific needs. Each task file should follow the JSON schema expected by SimulateDev's multi-agent orchestrator. 