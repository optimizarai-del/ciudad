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

## 3. Configuración

Las variables se leen del **entorno del deploy**: en Easypanel se cargan en la
pestaña *Environment* del servicio Compose; en un server propio, con un archivo
`.env` en la raíz (o `export`). Todas tienen default razonable — la única que
conviene setear sí o sí es `SECRET_KEY`.

**Lo mínimo para arrancar:**

| Variable | Qué poner |
|---|---|
| `SECRET_KEY` | Un secreto propio. Generalo: `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `DATABASE_URL` | *(opcional)* default `sqlite:////data/ciudad.db` (persistente en el volumen) **o** la URL de Postgres/Supabase |

> No hace falta tocar CORS: el frontend y el API van por el mismo origen.

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

Desde la raíz del repo (server propio: descomentá el bloque `ports:` del
frontend en `docker-compose.yml` para publicar el puerto 80):

```bash
# Deploy mínimo (backend + frontend)
docker compose up -d --build

# Con worker de scraping en background (Redis + RQ)
docker compose -f docker-compose.yml -f docker-compose.scraping.yml up -d --build
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

## 8. Deploy en Easypanel (recomendado: servicio Compose)

1. En el proyecto, **+ Servicio → Compose**. Nombre: `ventas-ciudad`.
2. **Origen (Git)**: repo `optimizarai-del/ciudad`, rama `ventas-ciudad`,
   archivo `docker-compose.yml`.
3. **Environment**: seteá `SECRET_KEY` (un string aleatorio). El resto es opcional.
4. **Desplegar** y esperar a que buildeen las dos imágenes (backend + frontend).
5. **Dominios**: agregá un dominio al servicio **`frontend`**, puerto **80**
   (Easypanel ofrece un subdominio `*.easypanel.host` gratis).
6. Abrí el dominio → login de CIUDAD.

> El servicio `frontend` usa `expose` (no publica puertos del host) para no
> chocar con el proxy de Easypanel; el dominio enruta al puerto 80 del contenedor.

**Alternativa (dos servicios App)**: backend (context `backend/`, sin
`SERVE_FRONTEND`, volumen `/data`, dominio propio) + frontend (context
`frontend/`, build-arg `VITE_API_URL=https://<dominio-backend>`, dominio
público). En este modo hay que setear `CORS_ORIGINS` = dominio del frontend en
el backend. El Compose es más simple porque evita el CORS y el doble dominio.

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
