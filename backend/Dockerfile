# ─── Stage 1: build del frontend ────────────────────────────────────────────
# Buildeamos React/Vite acá para que el stage final no necesite Node.
# El dist queda en /frontend/dist y se copia al stage de Python.
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --silent --no-fund --no-audit
COPY frontend/ ./
RUN npm run build


# ─── Stage 2: backend FastAPI ───────────────────────────────────────────────
FROM python:3.12-slim

# Estructura: /app/backend + /app/frontend (matchea el layout del repo)
WORKDIR /app/backend

# Dependencias del sistema mínimas para reportlab + httpx + ssl
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Cache de dependencias Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY backend/app ./app

# Frontend pre-buildeado del stage 1.
# Se copia a /app/frontend/dist para que el path resolution de versiones.py
# encuentre _FRONTEND_DIST correctamente (mismo layout que el repo local).
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

# Volumen para SQLite + adjuntos persistentes
RUN mkdir -p /data && chmod 777 /data
ENV DATABASE_URL=sqlite:////data/ciudad.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
