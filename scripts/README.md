# SimulateDev Scripts

This directory contains scripts that extend SimulateDev's capabilities for GitHub workflow automation.

## Available Scripts

### 🐛 **Issue to Task** (`issue_to_task.py`)
Converts GitHub issues into SimulateDev tasks that create pull requests with fixes.

### 🔧 **PR to Task** (`pr_to_task.py`)  
Processes existing pull requests with custom tasks, improving or extending them. Can also automatically address PR review comments and feedback.

### 🧪 **Test Utilities**
- `test_issue_parser.py` - Test issue parsing functionality
- `test_pr_parser.py` - Test PR parsing functionality
- `test_pr_review_comments.py` - Test PR review comments analysis

## Quick Start

```bash
# Fix a GitHub issue
python scripts/issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 --agent cursor

# Improve an existing PR
python scripts/pr_to_task.py --pr-url https://github.com/owner/repo/pull/456 --task "Add error handling" --agent cursor

# Address PR review comments automatically
python scripts/pr_to_task.py --pr-url https://github.com/owner/repo/pull/456 --review-comments --agent cursor

# Test parsing (no SimulateDev execution)
python scripts/test_issue_parser.py https://github.com/owner/repo/issues/123
python scripts/test_pr_review_comments.py https://github.com/owner/repo/pull/456
```

## Issue to Task Script

### Features
- **GitHub Issue Parsing**: Extracts issue details, comments, and metadata
- **Smart Classification**: Categorizes issues (Bug Fix, Feature, Performance, etc.)
- **Task Synthesis**: Converts issue content into comprehensive task prompts
- **New PR Creation**: Creates fresh pull requests with solutions

### Usage

```bash
# Basic usage
python scripts/issue_to_task.py --issue-url <ISSUE_URL> --agent <AGENT>

# Multi-agent workflow
python scripts/issue_to_task.py --issue-url <ISSUE_URL> \
  --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'

# Test mode (no PR creation)
python scripts/issue_to_task.py --issue-url <ISSUE_URL> --agent cursor --no-pr
```

### Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `--issue-url` | GitHub issue URL | ✅ |
| `--agent` | Single AI coding agent (cursor, windsurf, etc.) | ✅* |
| `--coding-agents` | JSON array of multiple agents | ✅* |
| `--no-pr` | Skip creating pull request (for testing) | ❌ |
| `--target-dir` | Target directory for cloning | ❌ |
| `--work-dir` | Working directory for the task | ❌ |

*Either `--agent` or `--coding-agents` must be specified.

### How It Works

1. **Parse Issue URL**: Extracts repository and issue information
2. **Fetch Issue Data**: Uses GitHub API to get issue details and comments  
3. **Classify Issue**: Determines issue type based on labels and content
4. **Synthesize Task**: Creates comprehensive task prompt with full context
5. **Execute SimulateDev**: Runs the custom coding workflow
6. **Create PR**: Automatically creates pull request with the fix

### Issue Classification

Issues are automatically classified as:
- **Bug Fix**: Labels like 'bug', 'error', 'crash' or bug-related keywords
- **Feature Enhancement**: 'feature', 'enhancement', 'improvement' labels
- **Performance Optimization**: Performance, speed, or optimization related
- **Security Fix**: Security-related labels or content
- **Documentation**: Documentation-related issues
- **General Issue**: Fallback category

## PR to Task Script

### Features
- **PR Context Analysis**: Fetches PR description, comments, reviews, and complete diff
- **Branch Management**: Works directly on existing PR branches
- **Smart Change Detection**: Only pushes when modifications are made
- **Custom Task Integration**: Combines PR context with custom task instructions
- **Review Comments Mode**: Automatically analyzes and addresses all PR review feedback
- **Intelligent Commit Messages**: Generates descriptive commit messages based on changes made

### Usage

```bash
# Custom task mode
python scripts/pr_to_task.py --pr-url <PR_URL> --task "<CUSTOM_TASK>" --agent <AGENT>

# Review comments mode - automatically address PR feedback
python scripts/pr_to_task.py --pr-url <PR_URL> --review-comments --agent <AGENT>

# Multi-agent workflow
python scripts/pr_to_task.py --pr-url <PR_URL> --task "<CUSTOM_TASK>" \
  --coding-agents '[{"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},{"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}]'

# Analysis only (no push)
python scripts/pr_to_task.py --pr-url <PR_URL> --task "Review code quality" --agent cursor --no-push
```

### Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `--pr-url` | GitHub PR URL | ✅ |
| `--task` | Custom task description | ✅* |
| `--review-comments` | Automatically address PR review comments | ✅* |
| `--agent` | Single AI coding agent | ✅** |
| `--coding-agents` | JSON array of multiple agents | ✅** |
| `--no-push` | Skip pushing changes (analysis only) | ❌ |
| `--target-dir` | Target directory for cloning | ❌ |
| `--output` | Output file for execution report | ❌ |
| `--no-report` | Skip saving execution report | ❌ |

*Either `--task` or `--review-comments` must be specified.  
**Either `--agent` or `--coding-agents` must be specified.

### How It Works

1. **Parse PR URL**: Extracts repository and PR information
2. **Fetch PR Data**: Gets PR details, comments, reviews, and complete diff
3. **Clone & Checkout**: Clones repo and checks out the PR's head branch
4. **Synthesize Task**: Creates task prompt combining PR context with custom task
5. **Execute SimulateDev**: Runs the custom coding workflow
6. **Smart Push**: Only commits and pushes if changes were actually made

### Custom Task Examples

**Security Review:**
```bash
python scripts/pr_to_task.py --pr-url <PR_URL> \
  --task "Review for security vulnerabilities, add input validation" \
  --agent cursor
```

**Performance Optimization:**
```bash
python scripts/pr_to_task.py --pr-url <PR_URL> \
  --task "Optimize performance, add caching where appropriate" \
  --agent windsurf
```

**Add Tests:**
```bash
python scripts/pr_to_task.py --pr-url <PR_URL> \
  --task "Add comprehensive unit tests and integration tests" \
  --agent cursor
```

**Address Review Comments:**
```bash
python scripts/pr_to_task.py --pr-url <PR_URL> \
  --review-comments \
  --agent cursor
```

## Common Workflows

### 1. **Bug Fixing Pipeline**
```bash
# Step 1: Address the issue
python scripts/issue_to_task.py --issue-url https://github.com/owner/repo/issues/123 --agent cursor

# Step 2: Improve the resulting PR
python scripts/pr_to_task.py --pr-url https://github.com/owner/repo/pull/124 --task "Add tests and error handling" --agent windsurf
```

### 2. **Code Quality Gate**
```bash
# Automatically improve PRs before review
python scripts/pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --task "Review for security and add tests" --agent cursor
```

### 3. **Review Response Automation**
```bash
# Automatically address all review comments
python scripts/pr_to_task.py --pr-url https://github.com/owner/repo/pull/123 --review-comments --agent cursor
```

### 4. **Multi-Agent Collaboration**
```bash
# Complex tasks with specialized roles
python scripts/issue_to_task.py --issue-url https://github.com/owner/repo/issues/456 \
  --coding-agents '[
    {"coding_ide":"cursor","model":"Claude Sonnet 3.5","role":"Planner"},
    {"coding_ide":"windsurf","model":"Claude Sonnet 3.5","role":"Coder"}
  ]'
```

## Script Comparison

| Feature | Issue to Task | PR to Task |
|---------|---------------|------------|
| **Input** | GitHub Issue URL | GitHub PR URL + Custom Task/Review Comments |
| **Context** | Issue + comments | PR + comments + reviews + diff |
| **Output** | New PR with fix | Updates to existing PR branch |
| **Branch Strategy** | Creates new branch | Works on existing PR branch |
| **Change Handling** | Always creates PR | Only pushes if changes made |
| **Best For** | Addressing open issues | Enhancing existing PRs + addressing feedback |

## Requirements

### Environment Setup
```bash
# Install dependencies (from main SimulateDev directory)
pip install -r requirements.txt

# Configure environment variables
cp env.example .env
# Edit .env with your GitHub token and API keys
```

### Required Environment Variables
```bash
# GitHub API access
GITHUB_TOKEN=your_github_token_here

# AI model API keys (depending on agents used)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
```

## Testing

Test scripts without running full SimulateDev workflows:

```bash
# Test issue parsing
python scripts/test_issue_parser.py https://github.com/owner/repo/issues/123

# Test PR parsing  
python scripts/test_pr_parser.py https://github.com/owner/repo/pull/456

# Test PR review comments analysis
python scripts/test_pr_review_comments.py https://github.com/owner/repo/pull/456
```

## Use Cases

### **Development Teams**
- **Automated Bug Fixing**: Process issue backlogs automatically
- **PR Quality Gates**: Improve PRs before merging
- **Code Review Assistance**: Add missing tests, documentation, error handling
- **Standards Enforcement**: Ensure coding standards across all PRs

### **Open Source Maintainers**
- **Community Issue Processing**: Address user-reported bugs and feature requests
- **Contributor PR Enhancement**: Improve community contributions
- **Quality Maintenance**: Maintain consistent code quality at scale

### **CI/CD Integration**
- **Quality Pipelines**: Integrate into CI/CD for automated improvements
- **Security Scanning**: Automatically fix security vulnerabilities
- **Performance Optimization**: Identify and fix performance issues
- **Test Coverage**: Automatically add missing tests

## Troubleshooting

### Common Issues

1. **GitHub API Rate Limits**: Ensure you have a valid `GITHUB_TOKEN`
2. **Private Repositories**: Your GitHub token needs appropriate permissions
3. **Issue/PR Not Found**: Verify URLs are correct and accessible
4. **Agent Execution Fails**: Check AI model API keys are configured

### Debug Mode

Use test scripts to verify parsing without running full workflows:

```bash
# Debug issue parsing
python scripts/test_issue_parser.py https://github.com/owner/repo/issues/123

# Debug PR parsing
python scripts/test_pr_parser.py https://github.com/owner/repo/pull/456

# Debug PR review comments analysis
python scripts/test_pr_review_comments.py https://github.com/owner/repo/pull/456
```

## Integration with SimulateDev

These scripts are fully integrated with SimulateDev's architecture:

- **Same Agent System**: Use all supported coding agents (Cursor, Windsurf, etc.)
- **Same Configuration**: Uses existing `.env` and configuration files
- **Same Orchestration**: Leverages existing workflow orchestration
- **Same Reporting**: Generates execution reports in the same format
- **Same Error Handling**: Follows the same error handling patterns

## Examples

### Real-World Example: Memory Leak Fix

```bash
python scripts/issue_to_task.py \
  --issue-url https://github.com/pipecat-ai/pipecat/issues/1809 \
  --agent cursor
```

This will:
1. ✅ Parse the pipecat repository and issue #1809
2. ✅ Fetch the memory leak issue details and comments
3. ✅ Classify it as a "Bug Fix" issue  
4. ✅ Generate a comprehensive task prompt (19K+ characters)
5. ✅ Execute SimulateDev with Cursor to investigate and fix the memory leak
6. ✅ Create a pull request with the solution
7. ✅ Open the PR URL in a web browser

### Batch Processing

```bash
# Process multiple issues
for issue in 123 456 789; do
  python scripts/issue_to_task.py --issue-url https://github.com/owner/repo/issues/$issue --agent cursor
done
```

## Contributing

When adding new scripts to this directory:

1. **Follow Naming Convention**: `[purpose]_to_task.py` for main scripts
2. **Include Test Script**: `test_[purpose]_parser.py` for validation
3. **Update This README**: Add your script to the available scripts section

These scripts demonstrate how to extend SimulateDev with GitHub integration and serve as templates for additional automation scripts. 