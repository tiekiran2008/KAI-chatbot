# ==============================================================================
# Production-Grade Backend Dockerfile
# ==============================================================================
FROM python:3.11-slim as builder

# Setup environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Install system compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first to optimize docker layers caching
COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# --- Final Runner Stage ---
FROM python:3.11-slim as runner

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install runtime dependencies (e.g. libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy backend source code files
COPY app/ ./app/

# Create directory for ChromaDB persistence volume
RUN mkdir -p /app/chroma_db

# Expose port and configure health checks
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/chat || exit 1

# Start the application server with multi-core Gunicorn wrapper
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
