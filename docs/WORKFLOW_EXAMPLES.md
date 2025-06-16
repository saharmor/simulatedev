# SimulateDev Workflow Examples

This document provides comprehensive examples of how to use SimulateDev's new workflow system with JSON configuration files.

## Overview

SimulateDev now supports three ways to specify tasks:

1. **Predefined Workflows** - Use specialized workflows like `bug_hunting` or `code_optimization`
2. **Custom Coding** - Use the `custom_coding` workflow with custom prompts
3. **Multi-Agent Roles** - Use the traditional role-based system without predefined workflows

## JSON Structure

All JSON task files now support these fields:

```json
{
      "coding_task_prompt": "Custom prompt for custom_coding workflow only",
  "agents": [
    {
      "role": "Coder|Planner|Tester",
      "coding_ide": "cursor|windsurf|claude",
      "model": "model_name"
    }
  ]
}
```

### Required Fields
- `agents`: Array of agent definitions

### Optional Fields
- `coding_task_prompt`: Custom prompt (required only for `custom_coding` workflow)

### Command-Line Parameters
- `--repo`: GitHub repository URL to work on
- `--workflow`: Predefined workflow to use (`bug_hunting`, `code_optimization`, `custom_coding`)

**Note**: Repository URL and workflow type are now passed as command-line arguments instead of being embedded in the JSON. This provides better separation of concerns and matches the pattern used in single-agent workflows.

## Workflow Examples

### 1. Bug Hunting Workflow

Find and fix security vulnerabilities and bugs in a codebase. No `coding_task_prompt` needed - the task is predefined by the workflow.

```json
{
  "agents": [
    {
      "role": "Coder",
      "coding_ide": "cursor",
      "model": "claude-sonnet-4"
    }
  ]
}
```

**Usage:**
```bash
python simulatedev.py --multi sample_bug_hunting_task.json --repo https://github.com/user/webapp-repo --workflow bug_hunting
```

### 2. Code Optimization Workflow

Optimize performance and improve code quality. No `coding_task_prompt` needed - the task is predefined by the workflow.

```json
{
  "agents": [
    {
      "role": "Planner",
      "coding_ide": "claude_code",
      "model": "claude-sonnet-4"
    },
    {
      "role": "Coder",
      "coding_ide": "windsurf",
      "model": "claude-sonnet-4"
    },
    {
      "role": "Tester",
      "coding_ide": "cursor",
      "model": "gemini-2.5-pro"
    }
  ]
}
```

**Usage:**
```bash
python simulatedev.py --multi sample_optimization_task.json --repo https://github.com/user/performance-critical-app --workflow code_optimization
```

### 3. Custom Coding Workflow

Use custom prompts for specific coding tasks. The `coding_task_prompt` field is required for this workflow.

```json
{
  "coding_task_prompt": "Build a Python script that scrapes article headlines from Hacker News and saves them to a CSV file. Create a robust web scraper that fetches the top 30 headlines from Hacker News homepage, handles errors gracefully, and saves the data to a CSV file with proper formatting. Include proper error handling, rate limiting, and data validation.",
  "agents": [
    {
      "role": "Coder",
      "coding_ide": "windsurf",
      "model": "claude-sonnet-4"
    },
    {
      "role": "Tester",
      "coding_ide": "cursor",
      "model": "gemini-2.5-pro"
    }
  ]
}
```

**Usage:**
```bash
python simulatedev.py --multi sample_multi_agent_task.json --repo https://github.com/user/example-repo --workflow custom_coding
```

### 4. Multi-Agent Role System (No Workflow)

Use the traditional role-based system for complex collaborative tasks. Without a workflow, the system uses the agent roles to coordinate the task.

```json
{
  "agents": [
    {
      "role": "Planner",
      "coding_ide": "claude_code",
      "model": "claude-sonnet-4"
    },
    {
      "role": "Coder",
      "coding_ide": "cursor",
      "model": "claude-sonnet-4"
    },
    {
      "role": "Tester",
      "coding_ide": "windsurf",
      "model": "gemini-2.5-pro"
    }
  ]
}
```

**Usage:**
```bash
python simulatedev.py --multi complex_api_task.json --repo https://github.com/user/api-project
```

## Command Line Usage

### Multi-Agent with JSON File
```bash
python simulatedev.py --multi task.json --repo https://github.com/user/repo --workflow custom_coding
```

### Multi-Agent with JSON String
```bash
python simulatedev.py --multi --json '{
  "coding_task_prompt": "Fix all responsive design issues in the CSS, ensure mobile compatibility",
  "agents": [{"role": "Coder", "coding_ide": "cursor", "model": "claude-sonnet-4"}]
}' --repo https://github.com/user/webapp --workflow custom_coding
```

### Interactive Mode
```bash
python simulatedev.py --multi --interactive
```

### Override Repository URL
```bash
python simulatedev.py --multi task.json --repo https://github.com/different/repo --workflow bug_hunting
```

### Skip Pull Request Creation
```bash
python simulatedev.py --multi task.json --repo https://github.com/user/repo --workflow code_optimization --no-pr
```

## Workflow Comparison

| Workflow | Best For | Agent Requirements | Output |
|----------|----------|-------------------|---------|
| `bug_hunting` | Security audits, bug fixes | Single Coder | Detailed bug analysis + fix |
| `code_optimization` | Performance improvements | Single Coder or Multi-agent | Optimization report + implementation |
| `custom_coding` | Custom development tasks | Any configuration | Task-specific implementation |
| No workflow | Complex collaborative projects | Multi-agent recommended | Role-based collaborative output |

## Tips

1. **Repository URLs**: Always include `repo_url` in your JSON for best results
2. **Workflow Selection**: Use predefined workflows for specialized tasks, `custom_coding` for custom prompts
3. **Agent Roles**: For multi-agent tasks without workflows, include Planner → Coder → Tester sequence
4. **Custom Prompts**: Be specific and detailed in your `coding_task_prompt` field for `custom_coding` workflow
5. **Model Selection**: Choose appropriate models for each agent based on their capabilities
6. **Predefined Workflows**: For `bug_hunting` and `code_optimization`, don't include `coding_task_prompt` - the task is already defined

## Migration from Old Format

Old format (still supported for backward compatibility):
```json
{
  "task": "Build an app",
  "agents": [...]
}
```

New format with workflows:
```json
{
  "repo_url": "https://github.com/user/repo",
      "workflow": "custom_coding",
  "coding_task_prompt": "Build a complete web application with...",
  "agents": [...]
}
```

The system maintains backward compatibility by checking for old field names (`task` and `prompt`) when `coding_task_prompt` is not provided. 