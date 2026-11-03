FROM python:3.12.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 appgroup \
    && useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==25.0.1 \
    && pip install --no-cache-dir -r requirements.txt

COPY pipeline ./pipeline
RUN chown -R 10001:10001 /app

USER 10001:10001

ENTRYPOINT ["python", "-m", "pipeline.run"]
