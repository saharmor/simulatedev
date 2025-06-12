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

### Basic Workflow Usage
```python
from workflows.general_coding import GeneralCodingWorkflow
from coding_agents import CodingAgentIdeType

# Initialize workflow
workflow = GeneralCodingWorkflow()

# Execute coding task
result = await workflow.execute_coding_task(
    agent_type=CodingAgentIdeType.CURSOR,
    repo_url="https://github.com/user/repo",
    user_prompt="Add error handling to the API endpoints",
    project_path="/path/to/project"
)
```

### Bug Hunting Workflow
```python
from workflows.bug_hunting import BugHunter
from coding_agents import CodingAgentIdeType

# Initialize bug hunter
bug_hunter = BugHunter()

# Hunt for bugs
result = await bug_hunter.hunt_bugs(
    agent_type=CodingAgentIdeType.WINDSURF,
    repo_url="https://github.com/user/repo",
    project_path="/path/to/project"
)
```

### Performance Optimization
```python
from workflows.code_optimization import CodeOptimizer
from coding_agents import CodingAgentIdeType

# Initialize optimizer
optimizer = CodeOptimizer()

# Optimize performance
result = await optimizer.optimize_performance(
    agent_type=CodingAgentIdeType.CLAUDE_CODE,
    repo_url="https://github.com/user/repo",
    project_path="/path/to/project"
)
```

## Creating Custom Workflows

To create a new workflow:

1. **Use the Unified Orchestrator**:
```python
from src.orchestrator import Orchestrator
from coding_agents import CodingAgentIdeType

class MyCustomWorkflow:
    def __init__(self):
        self.orchestrator = Orchestrator()
    
    async def execute_custom_task(self, agent_type: CodingAgentIdeType, repo_url: str, project_path: str = None):
        # Create single-agent request
        request = Orchestrator.create_single_agent_request(
            task_description="Your custom prompt here",
            agent_type=agent_type.value,
            workflow_type="custom",
            repo_url=repo_url,
            work_directory=project_path
        )
        
        # Execute task
        response = await self.orchestrator.execute_task(request)
        return response.final_output
```

2. **Add specialized prompt generation methods**
3. **Implement workflow-specific logic**
4. **Add comprehensive error handling**

## Workflow Architecture

```
Unified Orchestrator (base functionality)
├── GeneralCodingWorkflow (uses Orchestrator)
├── BugHunter (uses Orchestrator)  
├── CodeOptimizer (uses Orchestrator)
└── TestWorkflow (uses Orchestrator)
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