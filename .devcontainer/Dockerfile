# Dockerfile
# Base Image: Use an official Python runtime based on Debian Bookworm (similar to Ubuntu)
FROM python:3.13

# --- Environment Variables ---
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Ensures Python output is logged directly, preventing buffering issues
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Silences the nagging "you should upgrade pip" message
ENV PIP_NO_CACHE_DIR=off
# Enables pip caching within the image layer, speeding up rebuilds if deps don't change

# --- System Dependencies ---
# Update package lists, install essential build tools, database clients, curl, and clean up.
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    make \
    git \
    pandoc \
    # Compilers and libraries needed for native extensions
    curl \
    # Needed for downloading the Poetry installer
    postgresql-client \
    # Client library for PostgreSQL
    default-libmysqlclient-dev \
    # Client library development files for MySQL/MariaDB (needed for mysqlclient package)
    --no-install-recommends \
    # Avoid installing optional dependencies to keep the image smaller
    && apt-get clean \
    # Clean up downloaded package files
    && rm -rf /var/lib/apt/lists/*
# Remove package list cache

COPY requirements.txt ./

RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# --- Port Exposure ---
# Document that the application inside the container might listen on port 8000.
# Actual mapping happens in devcontainer.json or docker run/compose command.
EXPOSE 8000

# --- Default Command ---
# Keep the container running indefinitely for development.
# VS Code will attach, and you'll run commands manually in the integrated terminal.
CMD [ "/bin/bash" ]
