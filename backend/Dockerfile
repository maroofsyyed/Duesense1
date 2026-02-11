# DueSense Backend Dockerfile
# Production-ready Python 3.11.9 with MongoDB Atlas SSL support
# Uses Bullseye for OpenSSL 1.1.1 compatibility with MongoDB Atlas

FROM python:3.11.9-bullseye

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for SSL/TLS and health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libssl-dev \
        ca-certificates \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Verify OpenSSL version (should show 1.1.1.x for MongoDB Atlas compatibility)
RUN echo "=== OpenSSL Version ===" && openssl version && \
    echo "=== Python Version ===" && python --version

# Copy requirements first (for Docker layer caching)
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Verify critical packages are installed correctly
RUN echo "=== Verifying Critical Packages ===" && \
    python -c "import certifi; print(f'Certifi CA Bundle: {certifi.where()}')" && \
    python -c "import pymongo; print(f'PyMongo version: {pymongo.__version__}')" && \
    python -c "import ssl; print(f'SSL version: {ssl.OPENSSL_VERSION}')" && \
    python -c "import httpx; print(f'HTTPX version: {httpx.__version__}')"

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Render sets PORT env variable)
EXPOSE 10000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Run the application
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000} --log-level info"]
