# Multi-stage production Dockerfile for Pravah
# Stage 1: Builder - compile dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements for better layer caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 2: Runtime - minimal production image
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash pravah && \
    mkdir -p /app/logs /app/data && \
    chown -R pravah:pravah /app

# Copy virtual environment from builder
COPY --from=builder --chown=pravah:pravah /opt/venv /opt/venv

# Copy application code
COPY --chown=pravah:pravah . .

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    REDIS_HOST=redis \
    REDIS_PORT=6379

# Switch to non-root user
USER pravah

# Expose ports
EXPOSE 7000 8000 8600

# Health check - checks if app is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7000/api/health 2>/dev/null || exit 1

# Default command - Flask API with Gunicorn
CMD ["gunicorn", \
     "wsgi:app", \
     "--workers=4", \
     "--worker-class=sync", \
     "--bind=0.0.0.0:7000", \
     "--timeout=120", \
     "--keep-alive=5", \
     "--access-logfile=-", \
     "--error-logfile=-", \
     "--log-level=info"]
