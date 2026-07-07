# Small, production-sensible image for the FastAPI app.
FROM python:3.12-slim

# Don't write .pyc files; flush stdout so logs reach CloudWatch promptly.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY main.py .

# Run as a non-root user (security best practice).
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# The container listens on 8000; the ALB target group and ECS map to this port.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
