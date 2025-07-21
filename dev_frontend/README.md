# SimulateDev API Test Frontend

Simple HTML frontend for testing the SimulateDev FastAPI backend locally.

## Quick Start

1. **Start the FastAPI server** (from the `api/` directory):
   ```bash
   cd api
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Open the test frontend**:
   ```bash
   open dev_frontend/index.html
   ```
   Or simply double-click `index.html` in Finder.

## Features

### 🔧 System & Health
- Test basic health endpoint
- Get system configuration

### 🤖 Agents  
- List available coding agents (Cursor, Windsurf, Claude Code)
- Validate agent configurations

### 📱 GitHub Integration
- Parse GitHub issue URLs
- Get user info (requires GitHub token)
- List repositories (requires GitHub token)

### ⚡ Task Execution
- Execute SimulateDev tasks
- Monitor task status and progress
- View execution logs
- Cancel running tasks
- List all tasks

## GitHub Token

For GitHub-related endpoints, you'll need a personal access token:

1. Go to https://github.com/settings/tokens
2. Generate a new token with `repo` scope
3. Paste it into the "GitHub Token" field in the frontend

## Notes

- This is a **development-only** frontend for testing
- All API calls go to `http://localhost:8000/api`
- Responses are displayed in JSON format
- Error handling shows detailed error messages

## Cleanup

This entire `dev_frontend/` directory can be safely deleted once you're done testing. 