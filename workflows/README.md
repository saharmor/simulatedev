# Workflows Package

This package contains specialized workflow modules for different coding use cases. Each workflow uses the unified `Orchestrator` with specific functionality and prompts tailored for particular tasks.

## Available Workflows

### 1. General Coding (`general_coding.py`)
- **Purpose**: Handle user-provided coding prompts with enhanced context
- **Features**: 
  - Prompt enhancement with coding best practices
  - Simple task execution without enhancement
  - Flexible project path handling

### 2. Bug Hunting (`bug_hunting.py`)
- **Purpose**: AI-powered security vulnerability and bug discovery
- **Features**:
  - Systematic bug mapping and ranking
  - Focus on sophisticated, high-impact bugs
  - Professional security fix implementation

### 3. Code Optimization (`code_optimization.py`)
- **Purpose**: Performance improvements and code quality enhancements
- **Features**:
  - Performance optimization analysis
  - Code refactoring workflows
  - Low-hanging fruit identification

### 4. Test Workflow (`test_workflow.py`)
- **Purpose**: Simple end-to-end testing of agent functionality
- **Features**:
  - Basic "hello world" test execution
  - Agent pipeline validation
  - Simple file creation tests

## Usage Examples

### Basic Workflow Usage (via Unified Orchestrator)
```python
from src.orchestrator import Orchestrator

# Initialize orchestrator
orchestrator = Orchestrator()

# Create workflow request (UNIFIED METHOD)
request = Orchestrator.create_request(
    workflow_type="bugs",  # or "optimize", "refactor", "low-hanging", "test"
    repo_url="https://github.com/user/repo",
    agent_type="cursor",
    create_pr=True
)

# Execute workflow
response = await orchestrator.execute_task(request)
print(response.final_output)
```

### Alternative Usage Patterns
```python
# Single agent with custom task
request = Orchestrator.create_request(
    task_description="Fix the responsive design issues",
    agent_type="cursor",
    repo_url="https://github.com/user/repo"
)

# Multi-agent with explicit agents
from agents import AgentDefinition, AgentRole
agents = [
    AgentDefinition(coding_ide="cursor", model="claude-sonnet-4", role=AgentRole.CODER),
    AgentDefinition(coding_ide="windsurf", model="claude-sonnet-4", role=AgentRole.TESTER)
]
request = Orchestrator.create_request(
    task_description="Build a REST API with tests",
    agents=agents,
    repo_url="https://github.com/user/repo"
)

# Multi-agent with MultiAgentTask object
from agents import MultiAgentTask
task = MultiAgentTask(agents=agents, coding_task_prompt="Build API")
request = Orchestrator.create_request(multi_agent_task=task)
```

### CLI Usage (Recommended)
```bash
# Bug hunting workflow
python workflows_cli.py bugs https://github.com/user/repo cursor

# Performance optimization
python workflows_cli.py optimize https://github.com/user/repo windsurf

# Code refactoring
python workflows_cli.py refactor https://github.com/user/repo cursor
```

## Creating Custom Workflows

To create a new workflow:

1. **Create a Prompt Generator Class**:
```python
class MyCustomWorkflow:
    """Custom workflow prompt generator"""
    
    def __init__(self):
        pass  # No orchestrator needed - just generates prompts
    
    def generate_custom_prompt(self, repo_url: str) -> str:
        """Generate a custom workflow prompt"""
        return f"""Your custom prompt for {repo_url}
        
        ## Instructions
        - Custom workflow instructions here
        - Specific to your use case
        
        Please proceed with the custom task."""
```

2. **Add to Orchestrator's _generate_workflow_prompt method**:
```python
# In orchestrator.py, add to workflow_instances dict:
'custom': MyCustomWorkflow(),

# Add to prompt generation logic:
elif workflow_type == 'custom':
    return workflow_instance.generate_custom_prompt(repo_url)
```

3. **Add to CLI choices** (optional):
```python
# In workflows_cli.py, add to choices:
choices=["bugs", "optimize", "refactor", "low-hanging", "test", "custom"]
```

## Workflow Architecture

```
Unified Orchestrator (handles all execution)
├── Workflow Request Creation (create_workflow_request)
├── Agent Execution & Management
├── Repository Cloning & PR Creation
└── Uses Workflow Classes for Prompt Generation:
    ├── GeneralCodingWorkflow (prompt generation only)
    ├── BugHunter (prompt generation only)  
    ├── CodeOptimizer (prompt generation only)
    └── TestWorkflow (prompt generation only)
```

## Key Benefits

- **Unified Architecture**: All workflows use the same robust orchestrator
- **Consistent IDE Management**: Automatic IDE opening and closing
- **GitHub Integration**: Built-in PR creation for all workflows
- **Role-Based Execution**: Support for multi-agent workflows
- **Comprehensive Logging**: Detailed execution reports
- **Error Handling**: Robust error management and recovery

## Integration with Main CLI

Workflows are integrated with the main SimulateDev CLI through the unified orchestrator, providing seamless execution with features like:
- Automatic repository cloning
- IDE lifecycle management
- Pull request creation
- Execution logging and reporting 