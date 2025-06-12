# Use Ubuntu as base image for better GUI support
FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    xvfb \
    x11-utils \
    xauth \
    libx11-dev \
    libxtst6 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libxss1 \
    libgconf-2-4 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxfixes3 \
    libnss3 \
    libcups2 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m -s /bin/bash simulatedev && \
    usermod -aG sudo simulatedev

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to simulatedev user
RUN chown -R simulatedev:simulatedev /app

# Switch to non-root user
USER simulatedev

# Create directories for git configuration and workspace
RUN mkdir -p /home/simulatedev/.config/git && \
    mkdir -p /home/simulatedev/workspace

# Set git configuration (will be overridden by environment variables)
RUN git config --global user.name "SimulateDev Bot" && \
    git config --global user.email "simulatedev@example.com" && \
    git config --global init.defaultBranch main

# Create entrypoint script
COPY --chown=simulatedev:simulatedev docker-entrypoint.sh /home/simulatedev/
RUN chmod +x /home/simulatedev/docker-entrypoint.sh

# Expose any ports if needed (none for this CLI app)
# EXPOSE 8080

# Set the entrypoint
ENTRYPOINT ["/home/simulatedev/docker-entrypoint.sh"]

# Default command
CMD ["python3", "simulatedev.py", "--help"] 