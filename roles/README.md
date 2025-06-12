# Multi-Agent Role System

This directory contains the role-based architecture for the multi-agent orchestrator system. Each role (Planner, Coder, Tester) is implemented as a separate, specialized class that handles role-specific logic, prompts, and configurations.

## Architecture Overview

```
roles/
├── __init__.py           # Package exports
├── base_role.py          # Abstract base class for all roles
├── planner_role.py       # Planner role implementation
├── coder_role.py         # Coder role implementation  
├── tester_role.py        # Tester role implementation
├── role_factory.py       # Factory for creating role instances
├── example_usage.py      # Usage examples and demonstrations
└── README.md            # This documentation
```

## Key Components

### BaseRole (base_role.py)
Abstract base class that defines the interface for all roles:
- `create_prompt()` - Generate role-specific prompts
- `get_role_description()` - Human-readable role description
- `post_execution_hook()` - Post-process execution results

### Role Implementations

#### PlannerRole (planner_role.py)
- **Purpose**: Creates comprehensive implementation plans
- **Specialization**: Strategic planning and requirement analysis
- **Features**: 
  - Extracts plan sections for easier access by other roles
  - Considers previous planning attempts
  - Provides detailed implementation roadmaps

#### CoderRole (coder_role.py)
- **Purpose**: Implements solutions based on plans
- **Specialization**: Software development and coding
- **Features**:
  - Extracts implementation details (files, technologies, features)
  - Calculates confidence scores
  - Processes previous implementation attempts
  - Provides comprehensive coding guidelines

#### TesterRole (tester_role.py)
- **Purpose**: Validates implementations and ensures quality
- **Specialization**: Quality assurance and testing
- **Features**:
  - Comprehensive test analysis and metrics
  - Issue categorization (critical, major, minor)
  - Quality scoring and approval determination
  - Test coverage estimation

### RoleFactory (role_factory.py)
Centralized factory for creating and managing role instances:
- `create_role(role)` - Create role instance by AgentRole enum
- `register_role(role, class)` - Register custom role implementations
- `get_available_roles()` - List all supported roles
- `is_role_supported(role)` - Check role support

## Usage Examples

### Basic Role Creation
```python
from roles import RoleFactory
from agents import AgentRole

# Create a planner role
planner = RoleFactory.create_role(AgentRole.PLANNER)
print(planner.get_role_description())
```

### Custom Role Implementation
```python
from roles import BaseRole, RoleFactory
from agents import AgentRole

class CustomRole(BaseRole):
    def __init__(self):
        super().__init__(AgentRole.CODER)
    
    def create_prompt(self, task, context, agent_def):
        return f"Custom prompt for: {task}"
    
    def get_role_description(self):
        return "Custom role implementation"

# Register the custom role
RoleFactory.register_role(AgentRole.CODER, CustomRole)
```

### Integration with Orchestrator
The orchestrator automatically uses the role system:
```python
# The orchestrator now automatically:
# 1. Creates appropriate role instances
# 2. Uses role-specific prompts
# 3. Processes results with role hooks

orchestrator = MultiAgentOrchestrator()
result = await orchestrator.execute_multi_agent_task(task)
```

## Benefits of the New Architecture

### Modularity
- Each role is a separate, focused class
- Clear separation of concerns
- Easy to understand and maintain

### Extensibility
- Simple to add new roles
- Easy to customize existing roles
- Plugin-like architecture

### Specialization
- Role-specific prompts and logic
- Tailored configurations per role
- Optimized behavior for each role type

### Maintainability
- Centralized role management
- Consistent interface across roles
- Reduced code duplication

### Enhanced Features
- Post-execution result processing
- Role-specific metrics and analysis
- Streamlined execution flow

## Migration from Old System

The refactoring maintains backward compatibility while providing these improvements:

### Before (in multi_agent_orchestrator.py)
```python
def _create_planner_prompt(self, task, context, agent_def):
    # 50+ lines of prompt logic
    
def _create_coder_prompt(self, task, context, agent_def):
    # 40+ lines of prompt logic
    
def _create_tester_prompt(self, task, context, agent_def):
    # 60+ lines of prompt logic
```

### After (using role system)
```python
def _create_role_specific_prompt(self, role, context, agent_def):
    role_instance = RoleFactory.create_role(role)
    return role_instance.create_prompt(context.task_description, context, agent_def)
```

## Running the Example

To see the role system in action:

```bash
cd roles
python example_usage.py
```

This will demonstrate:
- Role creation and configuration
- Prompt generation for each role
- Custom role implementation
- Key benefits of the new system

## Future Enhancements

The role system is designed to support future enhancements:

1. **Dynamic Role Loading**: Load roles from external plugins
2. **Role Composition**: Combine multiple roles for complex behaviors
3. **Role Metrics**: Advanced analytics and performance tracking
4. **Role Templates**: Predefined role configurations for common scenarios
5. **Role Validation**: Automated testing of role implementations

## Contributing

When adding new roles:

1. Inherit from `BaseRole`
2. Implement all abstract methods
3. Add comprehensive docstrings
4. Include role-specific configurations
5. Add tests and examples
6. Update this documentation

The role system makes the multi-agent orchestrator more powerful, flexible, and maintainable while keeping the codebase clean and organized. 