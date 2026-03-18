
# Dockerfile



#
# Multi-stage build: use two stages:
#   1. "builder"  — installs Python dependencies into a venv
#   2. "runtime"  — copies only the venv + app code (no build tools)
# This keeps the final image lean (~200MB vs ~600MB).


# ── Stage 1: builder
# python:3.11-slim is an official Python image based on Debian Bookworm slim.
# "slim" strips documentation and locales, saving ~50MB vs the full image.
FROM python:3.11-slim AS builder

# Set the working directory inside the container.
WORKDIR /app

# Install OS-level build dependencies needed to compile some Python packages
# (geopandas needs GDAL; pandas needs gcc for certain extensions).
# --no-install-recommends prevents apt from pulling in suggested packages.
# clean the apt cache in the same RUN layer to avoid bloating the image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        gdal-bin \
        libgdal-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment inside the container.
# Using a venv (rather than installing globally) makes it easy to copy
# just the installed packages to the next stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements.txt first.
# Because Docker caches layers, if requirements.txt hasn't changed,
# the pip install layer is reused — even if app code has changed.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime 
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only the runtime OS libraries 
RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv from the builder stage (all installed packages)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application code
# .dockerignore prevents unwanted files from being copied
COPY . .

# Create the directory for the SQLite database and FAA CSV files.
# These will be mounted as Docker volumes so data persists between container restarts.
RUN mkdir -p /app/data/faa_csv /app/data/shapefiles

# The Flask app listens on this port inside the container.
EXPOSE 5050

# Environment variables with safe defaults.
ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5050 \
    FLASK_DEBUG=false \
    PYTHONUNBUFFERED=1
#   PYTHONUNBUFFERED=1 ensures Python output (print/logging) is sent to the
#   container logs immediately, not buffered.

# Healthcheck: Docker will ping /api/stats every 30s.
# If it fails 3 times in a row, the container is marked "unhealthy"
# and Docker Compose can restart it automatically.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/api/stats')"

# The command that runs when the container starts.

#   -w 2        : 2 worker processes
#   -b 0.0.0.0  : listen on all interfaces inside the container
#   app:create_app() : call create_app() from app.py to get the Flask app
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5050", "app:create_app()"]