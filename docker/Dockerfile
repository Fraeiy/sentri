FROM python:3.12-slim

LABEL org.opencontainers.image.title="Sentri"
LABEL org.opencontainers.image.description="Monitor Telegram groups and forward messages from selected users"
LABEL org.opencontainers.image.source="https://github.com/Fraeiy/sentri"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SENTRI_DATA_DIR=/data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --upgrade pip && \
    pip install .

RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /data && \
    chown -R appuser:appuser /data /app

USER appuser

VOLUME ["/data"]

ENTRYPOINT ["sentri"]
CMD ["watch"]