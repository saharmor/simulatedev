# SimulateDev
Run cutting-edge AI coding IDEs such as Cursor, Devin, and Claude Code via code.

SimulateDev is an automation tool that runs AI coding agents (Cursor, Devin, Claude Code) on any GitHub repository with custom prompts and automatically creates pull requests with the changes. It supports both **single-agent** and **multi-agent collaborative workflows**.

## Features

- **Multi-Agent Collaboration**: Planner → Coder → Tester workflows with specialized roles
- **Multiple Coding IDEs/Agents**: Works with Cursor, Windsurf, Claude, and more (future: Devin, Factory, Codex)
- **Automated Workflow**: Clone → Analyze → Implement → Test → Create PR
- **Custom Prompts**: Send any coding task to your preferred AI agent(s)
- **Visual UI Detection**: Uses Claude Computer Use for precise UI interaction
- **Local Execution**: Runs coding agents on your local machine (future: cloud execution)

## How It Works

```mermaid
graph LR
    A[GitHub Repo] --> B[Clone Repository]
    B --> C[Check Permissions]
    C --> D{Has Push Access?}
    D -->|Yes| E[Open AI IDE]
    D -->|No| F[Fork Repository]
    F --> G[Update Remote Origin]
    G --> E[Open AI IDE]
    E --> H[Send Prompt]
    H --> I[Wait for Completion]
    I --> J[Extract Results]
    J --> K[Create Branch & Commit]
    K --> L{Using Fork?}
    L -->|Yes| M[Push to Fork & Create Cross-Repo PR]
    L -->|No| N[Push & Create PR]
    M --> O[Done!]
    N --> O[Done!]
```

1. **Clone**: Downloads the specified GitHub repository
2. **Smart Workflow**: If no push access, automatically forks the repository
3. **Launch**: Opens your chosen AI coding agent (Cursor/Windsurf/etc.)
4. **Prompt**: Sends your custom coding task to the agent
5. **Monitor**: Watches the IDE interface to detect completion
6. **Commit**: Creates a new branch with the changes
7. **PR**: Creates pull request

## Quick Start

### Prerequisites

- **macOS** (SimulateDev currently only works on Mac)
- Python 3.8+
- Git installed and configured
- One of the supported AI IDEs installed:
  - [Cursor](https://cursor.com/)
  - [Windsurf](https://windsurf.ai/)
  - Claude Code
- API keys (see Setup section)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/simulatedev.git
   cd simulatedev
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

4. **Configure your API keys in `.env`:**
   ```env
   ANTHROPIC_API_KEY=your_anthropic_key_here
   GITHUB_TOKEN=your_github_token_here  # Optional, for PR creation
   ```

### 🌐 Web Interface (Recommended)

For the easiest way to get started, use the **interactive web interface** to generate CLI commands:

```bash
open simulatedev_ui.html
```

The web interface provides:
- **Easy Configuration**: Visual forms for all settings and options
- **Step-by-Step Guide**: Clear instructions for each step
- **Command Generation**: Automatically generates the correct CLI command
- **Multi-Agent Setup**: Simple interface for complex multi-agent workflows


## Usage

SimulateDev offers three main ways to run coding tasks:

### 1. 🚀 Quick Start with Predefined Workflows (Recommended)

Use built-in workflows for common coding tasks - no custom prompts needed:

```bash
python simulatedev.py --workflow <workflow_name> --repo <repo_url> --agent <agent_name>
```

**Available Workflows:**

| Workflow | Description | When to Use |
|----------|-------------|-------------|
| `bugs` | Find and fix bugs and security issues | Code has known issues or needs security audit |
| `optimize` | Performance optimizations and improvements | App is slow or needs better performance |
| `refactor` | Code quality improvements and refactoring | Code works but needs better structure/maintainability |
| `low-hanging` | Quick wins and easy improvements | Want fast, low-risk improvements |
| `custom` | Custom coding tasks with your own prompt | Need specific functionality or have custom requirements (see [Custom Single-Agent Tasks](#-custom-single-agent-tasks) section below) |


**Examples:**
```bash
# Hunt for bugs and security issues
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor

# Find performance optimization opportunities  
python simulatedev.py --workflow optimize --repo https://github.com/user/repo --agent windsurf

# Improve code quality and maintainability
python simulatedev.py --workflow refactor --repo https://github.com/user/repo --agent cursor

# Find easy wins and quick improvements
python simulatedev.py --workflow low-hanging --repo https://github.com/user/repo --agent windsurf
```

### 2. 🎯 Custom Single-Agent Tasks

For specific coding tasks with your own custom coding prompt:

```bash
python simulatedev.py --workflow custom --task "<your_custom_task>" --repo <repo_url> --agent <agent_name>
```

**Examples:**
```bash
# Fix responsive design issues with Cursor
python simulatedev.py --workflow custom --task "Fix responsive table design for mobile devices" --repo https://github.com/user/repo --agent cursor

# Add error handling with Windsurf  
python simulatedev.py --workflow custom --task "Add comprehensive error handling to API endpoints" --repo https://github.com/user/repo --agent windsurf

# Custom analysis task
python simulatedev.py --workflow custom --task "Analyze codebase for inconsistencies and create a report" --repo https://github.com/user/repo --agent cursor
```

### 3. 🤝 Multi-Agent Collaboration

For complex tasks requiring multiple specialized agents working together:

```bash
# Multi-agent custom coding with inline JSON
python simulatedev.py --workflow custom --task "<your_custom_task>" --repo <repo_url> --coding-agents '<json_config>'
```

**Multi-Agent JSON Format:**
```json
[
  {"coding_ide": "claude_code", "model": "claude-4-sonnet", "role": "Planner"},
  {"coding_ide": "cursor", "model": "claude-4-sonnet", "role": "Coder"},
  {"coding_ide": "windsurf", "model": "claude-4-sonnet", "role": "Tester"}
]
```

**Supported Roles:**
- **Planner**: Creates implementation plans and breaks down complex tasks
- **Coder**: Implements the solution based on the plan
- **Tester**: Tests and validates the implementation

**Example:**
```bash
python simulatedev.py --workflow custom --task "Add support for Firefox browser automation" --repo https://github.com/browserbase/stagehand --coding-agents '[
  {"coding_ide": "claude_code", "model": "claude-4-sonnet", "role": "Planner"},
  {"coding_ide": "cursor", "model": "claude-4-sonnet", "role": "Coder"},
  {"coding_ide": "windsurf", "model": "claude-4-sonnet", "role": "Tester"}
]'
```

### Additional Options

```bash
# Skip pull request creation (testing only)
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor --no-pr

# Keep existing repository directory (don't delete before cloning)
python simulatedev.py --workflow bugs --repo https://github.com/user/repo --agent cursor --no-delete-existing-repo-env
```

## Configuration

### Environment Variables

All configuration is managed through environment variables in your `.env` file:

| Variable | Purpose | Required | Default | Notes |
|----------|---------|----------|---------|-------|
| `ANTHROPIC_API_KEY` | UI element detection and IDE state analysis | Yes | - | [Get key](https://console.anthropic.com/) |
| `GITHUB_TOKEN` | Pull request creation | Optional | - | [Get token](https://github.com/settings/tokens) |
| `AGENT_TIMEOUT_SECONDS` | Agent execution timeout | Optional | 600 | 30-7200 seconds (0.5-120 minutes) |
| `GIT_USER_NAME` | Git commit author | Optional | Auto-detected from GitHub | Set to override GitHub account name |
| `GIT_USER_EMAIL` | Git commit email | Optional | Auto-detected from GitHub | Set to override GitHub account email |


### Timeout Configuration

The `AGENT_TIMEOUT_SECONDS` setting controls how long SimulateDev waits for agents to complete tasks:

**Guidelines:**
- **Simple tasks** (bug fixes, small features): 300-600 seconds (5-10 minutes)
- **Medium tasks** (refactoring, optimizations): 600-1200 seconds (10-20 minutes)  
- **Complex tasks** (large features, major changes): 1200-3600 seconds (20-60 minutes)
- **Very complex tasks**: Up to 7200 seconds (2 hours)

The timeout is automatically validated and clamped to reasonable bounds (30 seconds minimum, 2 hours maximum).

### Supported AI Agents

| Agent | Status | Notes |
|-------|--------|-------|
| Cursor | Supported | Full integration |
| Windsurf | Supported | Full integration |  
| Claude Code | Supported (Headless) | Full integration |


## Troubleshooting

### Common Issues and Solutions

#### IDE Window Focus Issues
If you see warnings about IDE windows not being visible/focused, SimulateDev will:
- **Play a beep sound** to alert you
- **Skip the current monitoring cycle** and retry
- **Continue monitoring** once the correct window is focused

**Solution**: Make sure the correct IDE window with your project is visible and focused.

#### Input Field Detection Issues
If Claude cannot locate the IDE's input field, SimulateDev will:
- **Play a beep sound** to alert you
- **Retry the operation** after you address the issue
- **Provide clear error messages** about what went wrong

**Common causes**:
- IDE interface has changed or is in an unexpected state
- Wrong IDE window is focused
- IDE is not fully loaded or ready

#### Timeout Configuration
If tasks are timing out, adjust the timeout in your `.env` file:
```env
# Increase timeout for complex tasks (in seconds)
AGENT_TIMEOUT_SECONDS=3600  # 1 hour
```

#### Repository Access Issues
If you see "Failed to clone repository" errors:
- Check that the repository URL is correct and accessible
- By default, existing repository directories are deleted before cloning (use `--no-delete-existing-repo-env` to keep existing directories)
- Ensure you have proper GitHub access permissions

### Error Handling Improvements
SimulateDev now provides consistent error handling across all scenarios:
- **Beep sounds** for attention-requiring issues
- **Clear error messages** with specific guidance
- **Automatic retries** for transient issues
- **Graceful degradation** when possible

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] Add web agents (Devin, Factory, Codex)
- [ ] Cloud execution (Daytona, E2B)
- [ ] Live monitoring of coding task
- [ ] Budgeting tools for better spend control
