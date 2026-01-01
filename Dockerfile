# Reducto Batch Processor
# Build: docker build -t reducto-batch .
# Run:   docker run -d --env-file .env -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output reducto-batch /app/input

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (for potential PDF processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY upload.py .
COPY split.py .
COPY extract.py .
COPY validator.py .

# Create output directories
RUN mkdir -p split_results extract_urls extract_results validation_results

# Default command - process files from /app/input folder
# Override by passing folder path as argument: docker run ... reducto-batch /path/to/folder
ENTRYPOINT ["python", "main.py"]
CMD ["input"]

