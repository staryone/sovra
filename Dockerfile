FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Create data directories
RUN mkdir -p data/chromadb data/training data/logs data/evolution_history data/task_queue

# Run SOVRA Brain
CMD ["python", "-m", "src.main"]
