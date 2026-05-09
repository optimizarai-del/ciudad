# ─── Backend CIUDAD — FastAPI ───────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas para reportlab + httpx + ssl
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Cache de dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY app ./app

# Volumen para SQLite + adjuntos persistentes
RUN mkdir -p /data && chmod 777 /data
ENV DATABASE_URL=sqlite:////data/ciudad.db

EXPOSE 8000

# Healthcheck simple — Easypanel lo respeta para ruteo
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
