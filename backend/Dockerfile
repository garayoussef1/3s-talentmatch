FROM python:3.11-slim

WORKDIR /app

# System dependencies for NLP libs (EasyOCR/OpenCV, pdf2image/poppler, OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
# fr-core-news-md is not on PyPI; install spaCy model via the CLI after spaCy is ready
RUN grep -v "^fr-core-news-md" requirements.txt > /tmp/req_clean.txt && \
    pip install --no-cache-dir -r /tmp/req_clean.txt && \
    python -m spacy download fr_core_news_md

# Copy application code
COPY . .

EXPOSE 8000

# Run migrations then start the server
# Railway injects $PORT; fall back to 8000 for local docker run
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
