# Docker Setup for SimulateDev

This guide explains how to run SimulateDev using Docker, which provides a consistent environment and eliminates the need to install dependencies locally.

## Quick Start

### 1. Prerequisites

- Docker installed on your system
- Docker Compose (usually included with Docker Desktop)
- Your API keys (Anthropic and Google)

### 2. Environment Setup

Create a `.env` file in the project root with your API keys:

```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your actual API keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GITHUB_TOKEN=your_github_token_here
GIT_USER_NAME="Your Name"
GIT_USER_EMAIL="your.email@example.com"
```

### 3. Build and Run

```bash
# Build the Docker image
docker-compose build

# Run SimulateDev with a coding task
docker-compose run --rm simulatedev python3 simulatedev.py \
  --task "Fix responsive design issues" \
  --repo https://github.com/user/repo \
  --workflow general_coding
```

## Usage Examples

### Basic Usage

```bash
# Show help
docker-compose run --rm simulatedev

# Run a simple coding task
docker-compose run --rm simulatedev python3 simulatedev.py \
  --task "Add error handling to API endpoints" \
  --repo https://github.com/user/webapp \
  --workflow general_coding

# Bug hunting workflow
docker-compose run --rm simulatedev python3 simulatedev.py \
  --task "Find security vulnerabilities" \
  --repo https://github.com/user/webapp \
  --workflow bug_hunting
```

### Multi-Agent Tasks

```bash
# Multi-agent collaboration
docker-compose run --rm simulatedev python3 simulatedev.py \
  --task "Build REST API with tests" \
  --repo https://github.com/user/webapp \
  --workflow general_coding \
  --coding-agents '[
    {"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},
    {"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"},
    {"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Tester"}
  ]'
```

### Interactive Development

```bash
# Start a development container with shell access
docker-compose run --rm simulatedev-dev

# Inside the container, you can run commands directly
python3 simulatedev.py --help
```

## Docker Architecture

### Container Features

- **Base Image**: Ubuntu 22.04 for better GUI support
- **Virtual Display**: Xvfb for GUI automation (pyautogui, etc.)
- **Non-root User**: Runs as `simulatedev` user for security
- **Persistent Storage**: Workspace directory mounted for results
- **Git Configuration**: Automatic git setup with your credentials

### Key Components

1. **Dockerfile**: Main container definition with all dependencies
2. **docker-entrypoint.sh**: Startup script that configures X11 and environment
3. **docker-compose.yml**: Service definitions with environment variables
4. **.dockerignore**: Excludes unnecessary files from build context

## Advanced Configuration

### Custom Resource Limits

Edit `docker-compose.yml` to adjust memory and CPU limits:

```yaml
deploy:
  resources:
    limits:
      memory: 4G      # Increase for complex tasks
      cpus: '2.0'     # Use more CPU cores
```

### Volume Mounts

The default setup includes these volume mounts:

```yaml
volumes:
  # Workspace for persistent results
  - ./workspace:/home/simulatedev/workspace
  
  # SSH keys for private repositories
  - ~/.ssh:/home/simulatedev/.ssh:ro
  
  # Git configuration persistence
  - ./docker-volumes/git-config:/home/simulatedev/.gitconfig
```

### Environment Variables

All environment variables from `env.example` are supported:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude Computer Use and IDE analysis API key |
| `GITHUB_TOKEN` | No | For creating pull requests |
| `GIT_USER_NAME` | No | Git commit author name |
| `GIT_USER_EMAIL` | No | Git commit author email |
| `AGENT_TIMEOUT_SECONDS` | No | Task timeout (default: 600) |

## Troubleshooting

### Common Issues

#### 1. X11 Display Errors

If you see display-related errors:

```bash
# Check if Xvfb is running inside container
docker-compose run --rm simulatedev ps aux | grep Xvfb

# Restart the container
docker-compose down && docker-compose up
```

#### 2. Permission Issues

```bash
# Fix workspace permissions
sudo chown -R $USER:$USER ./workspace

# Rebuild with no cache
docker-compose build --no-cache
```

#### 3. API Key Issues

```bash
# Verify environment variables are loaded
docker-compose run --rm simulatedev env | grep API_KEY

# Check .env file exists and has correct format
cat .env
```

#### 4. Git Authentication

For private repositories:

```bash
# Ensure SSH keys are properly mounted
docker-compose run --rm simulatedev ls -la /home/simulatedev/.ssh

# Test git access
docker-compose run --rm simulatedev git ls-remote https://github.com/user/private-repo
```

### Debug Mode

Run with debug output:

```bash
# Enable verbose logging
docker-compose run --rm simulatedev python3 simulatedev.py \
  --task "Your task" \
  --repo https://github.com/user/repo \
  --workflow general_coding \
  --verbose
```

### Container Shell Access

```bash
# Get shell access to running container
docker-compose run --rm simulatedev /bin/bash

# Or use the development profile
docker-compose --profile dev run --rm simulatedev-dev
```

## Performance Optimization

### Build Optimization

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker-compose build

# Build with specific target (if multi-stage)
docker-compose build --target production
```

### Runtime Optimization

```bash
# Increase shared memory for GUI applications
docker-compose run --rm --shm-size=2g simulatedev [command]

# Use host network for better performance (less secure)
docker-compose run --rm --network host simulatedev [command]
```

## Security Considerations

1. **API Keys**: Never commit `.env` file to version control
2. **SSH Keys**: Mounted read-only for security
3. **Non-root User**: Container runs as `simulatedev` user
4. **Network Isolation**: Uses bridge network by default
5. **Resource Limits**: Prevents resource exhaustion

## Cleanup

```bash
# Remove containers and images
docker-compose down --rmi all --volumes

# Clean up Docker system
docker system prune -a

# Remove workspace data (careful!)
rm -rf ./workspace ./docker-volumes
```

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: SimulateDev Task
on:
  workflow_dispatch:
    inputs:
      task:
        description: 'Coding task to execute'
        required: true
      repo:
        description: 'Target repository'
        required: true

jobs:
  simulate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run SimulateDev
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          docker-compose run --rm simulatedev python3 simulatedev.py \
            --task "${{ github.event.inputs.task }}" \
            --repo "${{ github.event.inputs.repo }}" \
            --workflow general_coding
```

This Docker setup provides a robust, isolated environment for running SimulateDev with all necessary dependencies and GUI support. 