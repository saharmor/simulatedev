# Workflows Package

This package contains specialized workflow modules for different coding use cases. Each workflow extends the `AgentOrchestrator` with specific functionality and prompts tailored for particular tasks.

## Available Workflows

### 🐛 Bug Hunting (`bug_hunting.py`)
**Class**: `BugHunter`  
**Purpose**: Finds and fixes bugs, security issues, and code vulnerabilities

**Key Methods**:
- `hunt_bugs()` - Complete bug hunting workflow
- `generate_bug_hunting_prompt()` - Creates bug-specific prompts

**Best for**:
- Security audits
- Finding hidden bugs
- Code quality issues
- Vulnerability assessments

### ⚡ Code Optimization (`code_optimization.py`) 
**Class**: `CodeOptimizer`  
**Purpose**: Performance improvements, refactoring, and code quality enhancements

**Key Methods**:
- `optimize_performance()` - Finds and implements performance optimizations
- `refactor_code()` - Improves code structure and maintainability  
- `find_low_hanging_fruit()` - Quick wins and easy improvements

**Best for**:
- Performance bottlenecks
- Code refactoring
- Quick improvements
- Architecture cleanup

### 🔧 General Coding (`general_coding.py`)
**Class**: `GeneralCodingWorkflow`  
**Purpose**: User-defined coding tasks with enhanced prompts

**Key Methods**:
- `execute_coding_task()` - Enhanced user prompt execution
- `execute_simple_task()` - Direct prompt execution without enhancement
- `enhance_user_prompt()` - Adds context and structure to user prompts

**Best for**:
- Custom feature implementation
- User-defined tasks
- General development work
- Feature additions

## Usage Examples

### Using Individual Workflows

```python
import asyncio
from workflows.bug_hunting import BugHunter
from workflows.code_optimization import CodeOptimizer
from workflows.general_coding import GeneralCodingWorkflow
from coding_agents import CodingAgentType

async def example():
    # Bug hunting
    hunter = BugHunter()
    results = await hunter.hunt_bugs(
        CodingAgentType.CURSOR, 
        "https://github.com/user/repo"
    )
    
    # Performance optimization
    optimizer = CodeOptimizer()
    results = await optimizer.optimize_performance(
        CodingAgentType.WINDSURF,
        "https://github.com/user/repo"
    )
    
    # General coding task
    general = GeneralCodingWorkflow()
    results = await general.execute_coding_task(
        CodingAgentType.CURSOR,
        "https://github.com/user/repo",
        "Add user authentication"
    )
```

### Using the CLI

For the most common use cases, use the command-line interfaces:

```bash
# Specialized workflows
python workflows_cli.py bugs https://github.com/user/repo cursor
python workflows_cli.py optimize https://github.com/user/repo windsurf
python workflows_cli.py refactor https://github.com/user/repo cursor
python workflows_cli.py low-hanging https://github.com/user/repo windsurf

# General coding tasks
python main.py https://github.com/user/repo "Add user authentication" cursor
```

## Creating Custom Workflows

To create a new workflow:

1. **Extend AgentOrchestrator**:
```python
from agent_orchestrator import AgentOrchestrator
from coding_agents import CodingAgentType

class MyCustomWorkflow(AgentOrchestrator):
    def generate_custom_prompt(self, repo_url: str) -> str:
        return "Your specialized prompt here..."
    
    async def execute_custom_task(self, agent_type: CodingAgentType, 
                                 repo_url: str, project_path: str = None) -> str:
        prompt = self.generate_custom_prompt(repo_url)
        return await self.execute_workflow(agent_type, repo_url, prompt, project_path)
```

2. **Add to workflows package**:
   - Add your module to `workflows/`
   - Import it in `workflows/__init__.py`
   - Add CLI support in `workflows_cli.py` if needed

## Architecture

```
AgentOrchestrator (base class)
├── Provides: IDE management, cloning, prompt sending, response handling
├── BugHunter (extends AgentOrchestrator)
│   └── Adds: Bug-specific prompts and hunting workflow
├── CodeOptimizer (extends AgentOrchestrator)  
│   └── Adds: Performance, refactoring, and low-hanging fruit workflows
└── GeneralCodingWorkflow (extends AgentOrchestrator)
    └── Adds: Enhanced user prompt handling and context
```

## Best Practices

1. **Use the right workflow for the task**:
   - `bugs` for security and bug fixes
   - `optimize` for performance improvements
   - `refactor` for code quality
   - `low-hanging` for quick wins
   - `main.py` for custom tasks

2. **Workflow-specific prompts** are more effective than generic ones

3. **Combine workflows** for comprehensive improvements:
   ```bash
   python workflows_cli.py bugs https://github.com/user/repo cursor
   python workflows_cli.py low-hanging https://github.com/user/repo cursor
   python workflows_cli.py optimize https://github.com/user/repo cursor
   ```

4. **Test before creating PRs** by using `--no-pr` flag first 