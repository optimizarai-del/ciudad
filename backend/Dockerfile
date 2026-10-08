# ─── Backend CIUDAD — FastAPI ───────────────────────────────────────────────
# Single-stage build. El frontend buildeado vive dentro del repo en
# backend/app/static/ (pre-construido con `npm run build` + script de copia),
# así no necesitamos Node en el container ni cambiar el build context en
# Easypanel — sigue siendo `backend/` como antes.

FROM python:3.12-slim

WORKDIR /app

# Sin apt-get a proposito. Antes se instalaba build-essential + curl: 74
# paquetes, 87.8 MB de descarga, 351 MB en disco y 402 SEGUNDOS de build, para
# compilar exactamente nada — todas las deps de requirements.txt publican wheels
# manylinux para cp312 (verificado con `pip download --only-binary=:all:`), y
# los logs de build no muestran ni un "Building wheel for". reportlab y httpx
# son puro Python; psycopg2-binary ya viene compilado.
# Si alguna vez entra una dep sin wheel, el pip install va a fallar con un
# mensaje claro: ahi se decide, en vez de pagar el compilador en cada deploy.

# Cache de dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app (incluye app/static/ con el frontend pre-buildeado)
COPY app ./app

# Volumen para SQLite + adjuntos persistentes
RUN mkdir -p /data && chmod 777 /data
ENV DATABASE_URL=sqlite:////data/ciudad.db

EXPOSE 8000

# urllib en vez de curl: evita tener que instalar curl (y con eso, todo el apt-get).
#
# --start-period=120s: sin esto el healthcheck cuenta desde el segundo 0, y con
# interval=30s x retries=3 la app tenia 90s para responder /health o Swarm la
# declaraba unhealthy y la reemplazaba A MITAD DEL ARRANQUE. Importar 50 paquetes
# (SQLAlchemy, reportlab, pillow, lxml, cryptography, anthropic) en un VPS de
# 2 vCPU compartidos puede pasarse de 90s. Durante el start-period los fallos
# no cuentan; despues la vigilancia es la de siempre.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=120s \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
