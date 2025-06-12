# Docker Setup Testing Guide

This guide helps you test the SimulateDev Docker setup step-by-step, as if you just cloned the repository.

## Prerequisites

- Docker installed on your system
- Docker Compose (usually included with Docker Desktop)
- Your Anthropic API key

## Step-by-Step Testing Process

### 1. Clone the Repository

```bash
git clone https://github.com/saharmor/simulatedev.git
cd simulatedev
```

### 2. Verify Required Files

Check that all Docker files are present:

```bash
ls -la Dockerfile docker-compose.yml docker-entrypoint.sh DOCKER.md Makefile
```

You should see all these files listed.

### 3. Set Up Environment

```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your actual API key
# Replace 'your_anthropic_api_key_here' with your real API key
nano .env  # or use your preferred editor
```

Your `.env` file should look like:
```env
ANTHROPIC_API_KEY=your_actual_api_key_here
GITHUB_TOKEN=your_github_token_here  # Optional
GIT_USER_NAME="Your Name"
GIT_USER_EMAIL="your.email@example.com"
```

### 4. Create Required Directories

```bash
# Create workspace directory for persistent storage
mkdir -p workspace
```

### 5. Test Docker Build

```bash
# Build the Docker image
make build

# Or use docker compose directly
docker compose build
```

Expected output: Build should complete successfully without errors.

### 6. Test Basic Container Functionality

```bash
# Test that the container starts and shows help
docker compose run --rm simulatedev

# Or test with a simple command
docker run --rm -e ANTHROPIC_API_KEY=your_key simulatedev:latest python3 -c "print('Container works!')"
```

### 7. Test Your Specific Task

Replace `your_key` with your actual API key:

```bash
docker compose run --rm simulatedev python3 simulatedev.py \
  --task "Use windsurf as the coder and cursor as the planner to add a caching mechanism to optimize data access" \
  --repo https://github.com/saharmor/cursor-view \
  --workflow general_coding \
  --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'
```

### 8. Test Makefile Commands

```bash
# Test the make commands
make help
make check-env
make status
```

## Common Issues and Solutions

### Issue 1: "docker-compose: command not found"

**Solution**: Use `docker compose` (with space) instead:
```bash
docker compose build
docker compose run --rm simulatedev
```

### Issue 2: Volume Mount Errors

**Solution**: Ensure the workspace directory exists:
```bash
mkdir -p workspace
```

### Issue 3: X11 Authentication Errors

This is expected in the current version. The container should still work for basic functionality, but GUI operations may fail.

### Issue 4: API Key Not Set

**Solution**: Make sure your `.env` file has the correct API key:
```bash
cat .env | grep ANTHROPIC_API_KEY
```

## Expected Test Results

✅ **Success Indicators:**
- Docker build completes without errors
- Container starts and shows help message
- Basic Python commands work inside container
- Environment variables are loaded correctly

⚠️ **Known Limitations:**
- GUI operations may fail due to X11 setup (this is expected)
- Some volume mounts may need adjustment for your system

## Next Steps

If all tests pass, your Docker setup is ready for publication! Consider:

1. Adding more comprehensive error handling for GUI operations
2. Improving X11 setup for better GUI support
3. Adding more example tasks to the documentation

## Troubleshooting

If you encounter issues:

1. Check Docker is running: `docker --version`
2. Verify your API key is set: `cat .env`
3. Check container logs: `docker compose logs`
4. Try running with verbose output: `docker compose run --rm simulatedev python3 simulatedev.py --help`

For more help, see [DOCKER.md](DOCKER.md) for detailed documentation. 