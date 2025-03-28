FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy runner script
COPY runner.py /app
COPY agent/agent.py /app/agent
COPY ./data /app/data

# Security: Run as non-root user
RUN useradd -m appuser
USER appuser

# These will be mounted at runtime
# VOLUME ["/app/agent", "/app/data", "/app/results"]

# Default command (will be overridden at runtime)
CMD ["python", "runner.py"]