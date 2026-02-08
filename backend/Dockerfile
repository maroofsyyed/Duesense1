# Use Python 3.11.9 - GUARANTEED
FROM python:3.11.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip==26.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render will set $PORT environment variable)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Run the application
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}

