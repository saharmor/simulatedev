# SimulateDev Docker Makefile
# Provides convenient commands for Docker operations

.PHONY: help build run dev clean test

# Default target
help:
	@echo "SimulateDev Docker Commands:"
	@echo ""
	@echo "  make build     - Build the Docker image"
	@echo "  make run       - Run SimulateDev (shows help)"
	@echo "  make dev       - Start development container with shell"
	@echo "  make test      - Run a test task"
	@echo "  make clean     - Clean up Docker resources"
	@echo "  make logs      - Show container logs"
	@echo ""
	@echo "Environment variables:"
	@echo "  TASK          - Coding task description"
	@echo "  REPO          - GitHub repository URL"
	@echo "  WORKFLOW      - Workflow type (general_coding, bug_hunting, code_optimization)"
	@echo ""
	@echo "Examples:"
	@echo "  make run TASK='Fix responsive design' REPO='https://github.com/user/repo'"
	@echo "  make test"

# Build the Docker image
build:
	@echo "Building SimulateDev Docker image..."
	docker-compose build

# Run SimulateDev with parameters
run:
	@if [ -z "$(TASK)" ] || [ -z "$(REPO)" ]; then \
		echo "Running SimulateDev help..."; \
		docker-compose run --rm simulatedev; \
	else \
		echo "Running SimulateDev task: $(TASK)"; \
		docker-compose run --rm simulatedev python3 simulatedev.py \
			--task "$(TASK)" \
			--repo "$(REPO)" \
			--workflow "$(or $(WORKFLOW),general_coding)"; \
	fi

# Start development container
dev:
	@echo "Starting development container..."
	docker-compose --profile dev run --rm simulatedev-dev

# Run a test task
test:
	@echo "Running test task..."
	docker-compose run --rm simulatedev python3 simulatedev.py \
		--task "Add comprehensive error handling to main functions" \
		--repo "https://github.com/saharmor/gemini-multimodal-playground" \
		--workflow general_coding

# Clean up Docker resources
clean:
	@echo "Cleaning up Docker resources..."
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -f

# Show logs
logs:
	docker-compose logs -f

# Build with no cache
rebuild:
	@echo "Rebuilding Docker image with no cache..."
	docker-compose build --no-cache

# Check environment
check-env:
	@echo "Checking environment configuration..."
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Copy env.example to .env and configure your API keys."; \
		exit 1; \
	fi
	@echo "✅ .env file found"
	@docker-compose run --rm simulatedev env | grep -E "(ANTHROPIC_API_KEY)" | sed 's/=.*/=***/' || echo "❌ API keys not configured"

# Interactive shell in running container
shell:
	@echo "Opening shell in SimulateDev container..."
	docker-compose run --rm simulatedev /bin/bash

# Show container status
status:
	@echo "Docker container status:"
	docker-compose ps

# Pull latest base images
update:
	@echo "Pulling latest base images..."
	docker-compose pull
	docker pull ubuntu:22.04

# Export image for sharing
export:
	@echo "Exporting SimulateDev image..."
	docker save simulatedev:latest | gzip > simulatedev-docker.tar.gz
	@echo "Image exported to simulatedev-docker.tar.gz"

# Import image from file
import:
	@echo "Importing SimulateDev image..."
	@if [ ! -f simulatedev-docker.tar.gz ]; then \
		echo "❌ simulatedev-docker.tar.gz not found"; \
		exit 1; \
	fi
	gunzip -c simulatedev-docker.tar.gz | docker load
	@echo "✅ Image imported successfully" 