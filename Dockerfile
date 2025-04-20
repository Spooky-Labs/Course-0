FROM python:3.9-slim

WORKDIR /workspace

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY huggingface.py .
RUN python3 huggingface.py

# Set offline ENV after we download
ENV HF_HUB_OFFLINE=1
# Copy runner script
COPY runner.py ./workspace
COPY symbols.txt ./workspace
COPY ./agent/agent.py /workspace/agent
COPY ./data /workspace/data
RUN chmod -R 777 /workspace

# Security: Run as non-root user
RUN useradd -m appuser
RUN chown -R appuser:appuser /workspace
USER appuser

# Default command (will be overridden at runtime)
CMD ["python", "runner.py"]