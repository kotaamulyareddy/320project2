FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libgtk2.0-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY services/vision_pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/vision_pipeline/ ./

EXPOSE 8001

CMD ["python", "inference_engine.py"]