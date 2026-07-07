# Deploy — CIUDAD Ventas (app nueva)

Guía para levantar **CIUDAD Ventas** en un servidor como aplicación nueva e
independiente. Está pensada para dejarlo andando con **un solo comando**.

---

## 1. Qué se despliega

Un stack de 2 servicios (más 2 opcionales para el scraping):

```
                    ┌─────────────────────────────────────────┐
   navegador  ─────►│  frontend (nginx, :80)                  │
                    │   • sirve la SPA de React                │
                    │   • reverse-proxy  /api /auth /health ──┼──► backend (FastAPI :8000)
                    └─────────────────────────────────────────┘         │
                                                                         ├─ SQLite (/data) o Postgres/Supabase
   (opcional, scraping)                                                  │
   worker (RQ) ──► redis ◄──────────────────────────────────────────────┘
```

Como nginx hace de reverse-proxy del API, **el navegador habla siempre con el
mismo origen**: no hay CORS que configurar ni `VITE_API_URL` que setear.

---

## 2. Requisitos

- Un servidor Linux con **Docker** y **Docker Compose v2** (`docker compose`).
- Un dominio apuntando al servidor (ej. `ventas.tudominio.com`) — opcional pero
  recomendado. Sin dominio, funciona igual por IP:puerto.

---

## 3. Configuración (único paso obligatorio)

```bash
cp backend/.env.example backend/.env
```

Editá `backend/.env`. **Lo mínimo para arrancar:**

| Variable | Qué poner |
|---|---|
| `SECRET_KEY` | Un secreto propio. Generalo: `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `DATABASE_URL` | `sqlite:////data/ciudad.db` (simple, persistente en el volumen) **o** la URL de Postgres/Supabase |
| `CORS_ORIGINS` | No hace falta tocar (el proxy es mismo-origen). Dejalo por defecto |

**Recomendado para producción** (activan las funciones clave):

| Variable | Habilita |
|---|---|
| `ANTHROPIC_API_KEY` | Agentes IA, NLU de pedidos, recomendaciones, carga de propiedades por PDF |
| `GOOGLE_MAPS_API_KEY` | Geolocalización precisa + constraint por zona en el mapa |
| `TELEGRAM_BOT_TOKEN` | Bot de leads + notificaciones a vendedores |
| `TOKKO_USER` / `TOKKO_PASS` | Red Tokko en vivo por zona |
| `VENTAS_JOB_TOKEN` | Protege el cron de jobs diarios de Ventas |
| `INSTAGRAM_VERIFY_TOKEN` / `WHATSAPP_VERIFY_TOKEN` | Webhooks de captación (ver §7) |

> Si usás **Postgres/Supabase**, seteá también `CIUDAD_DB_SCHEMA=ciudad`. Las
> tablas se crean solas al primer arranque (no hay migraciones que correr).

---

## 4. Deploy con Docker Compose (recomendado)

Desde la raíz del repo:

```bash
# Deploy mínimo (backend + frontend)
docker compose up -d --build

# Con worker de scraping en background (Redis + RQ)
docker compose --profile scraping up -d --build
```

Listo. La app queda en **`http://<servidor>/`** (puerto 80).

Para cambiar el puerto público, seteá `PUBLIC_PORT` (ej. `PUBLIC_PORT=8080 docker compose up -d`).

Comandos útiles:

```bash
docker compose logs -f backend      # ver logs del API
docker compose ps                   # estado de los servicios
docker compose down                 # frenar (los datos quedan en el volumen)
docker compose up -d --build        # redeploy tras un git pull
```

---

## 5. Verificación post-deploy

```bash
curl http://<servidor>/health
# → {"status":"ok","brand":"CIUDAD — Negocios Inmobiliarios",...}
```

1. Abrí `http://<servidor>/` → tenés que ver el login de CIUDAD.
2. El **primer arranque siembra** usuarios/datos demo (ver `app/mock_data`/seeds).
   Entrá con el admin del seed y **cambiá la contraseña**.
3. En el menú **Ventas** deberías ver: Dashboard, **Ejecutivo** (gerencia), CRM,
   Pedidos, Clientes, Propiedades, Red Tokko, Webs, Mapas, Operaciones, Matches,
   Tareas, Contactos, Notificaciones, Configuración.

---

## 6. Jobs diarios (cron)

El módulo Ventas expone un endpoint idempotente para correr los trabajos diarios
(seguimiento, degradación de temperatura, notificaciones). Programá un cron en el
servidor (o en Easypanel) que lo pegue una vez por día:

```bash
curl -X POST "http://<servidor>/api/ventas-crm/jobs/run-daily?token=$VENTAS_JOB_TOKEN"
```

> El token es el de `VENTAS_JOB_TOKEN`. Si lo dejás vacío, el endpoint no exige
> token (protegé por red).

---

## 7. Captación multicanal (Instagram / WhatsApp)

Los webhooks ya están montados y crean leads en el CRM automáticamente. Para
conectarlos, registrá estas URLs en Meta / YCloud (verify token = el de `.env`):

| Canal | URL a registrar | Verify token |
|---|---|---|
| Instagram DMs | `https://<dominio>/api/ventas-crm/webhooks/instagram` | `INSTAGRAM_VERIFY_TOKEN` |
| WhatsApp | `https://<dominio>/api/ventas-crm/webhooks/whatsapp` | `WHATSAPP_VERIFY_TOKEN` |
| Formulario web | `https://<dominio>/api/ventas-crm/webhooks/web` (POST, sin token) | — |

El código funciona sin credenciales: el endpoint existe y queda listo. En cuanto
pegás el token y conectás la cuenta, cada mensaje entrante entra como lead nuevo
(asignado al vendedor con menos carga, con nota + notificación).

---

## 8. Alternativa: Easypanel

Si desplegás en **Easypanel**, tenés dos caminos:

- **Compose app**: subí el repo y usá el `docker-compose.yml` de la raíz.
- **Dos servicios App**:
  1. Backend → build context `backend/`, Dockerfile incluido, puerto 8000,
     volumen en `/data`, variables del `.env`. **No** setees `SERVE_FRONTEND`.
  2. Frontend → build context `frontend/`, Dockerfile incluido, build-arg
     `VITE_API_URL=https://api.<tudominio>` (subdominio del backend), puerto 80.

El `docker-compose.yml` es el camino más simple para una app nueva.

---

## 9. Notas

- **Persistencia**: los datos viven en el volumen `ciudad_data` (SQLite +
  adjuntos). Con Postgres/Supabase, el volumen solo guarda adjuntos.
- **Scraping**: sin `REDIS_URL`, el sync corre síncrono dentro del request (ok
  para bajo volumen). Para background, usá el perfil `scraping`. Los portales
  con anti-bot fuerte pueden requerir el motor Playwright (pendiente de endurecer).
- **HTTPS**: ponelo con el reverse-proxy del server (Traefik/Caddy/Easypanel) o
  un nginx delante. El uvicorn ya corre con `--proxy-headers`.
- Este deploy incluye **todo el sistema** (Ventas + Alquileres), porque es el
  mismo código base. El menú se filtra por rol.
