# Multi-stage build for OCR microservice
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies (if needed by Datalab SDK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/

# Create temp directory for OCR processing
RUN mkdir -p /tmp/ocr-processing

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app

# Run as non-root user for security (optional but recommended)
RUN useradd -m -u 1000 ocruser && \
    chown -R ocruser:ocruser /app /tmp/ocr-processing
USER ocruser

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the application
CMD ["python", "-m", "src.main"]
