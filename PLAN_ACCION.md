# 🗺️ CIUDAD. — Plan de acción

> **Inmuebles · Contratos · Gestión**
> Plataforma integral para gestión inmobiliaria (alquileres, ventas, propietarios e inquilinos).

---

## 🎯 Necesidades del negocio

1. **Contratos de alquiler** — departamentos, casas, locales comerciales.
2. **Boletos de compraventa** — casas, departamentos, campos, locales.
3. **Gestión de alquileres** — propiedades activas, inquilinos, vencimientos.
4. **Gestión de ventas** — sincronizado con **Tokko Broker** desde una sola interfaz.
5. **Calculadora de costos automática** — escribir dirección → calcula alquiler + ajuste IPC/ICL + impuestos + municipales + expensas. Sin cálculos manuales.
6. **Agente IA interno (WhatsApp)** — consultas y operaciones desde mensajería.

---

## 🧱 Modelo de datos núcleo

| Entidad | Propósito |
|---------|-----------|
| **User** | Usuarios + roles (admin, operador, finanzas, agente_ia) |
| **Propiedad** | Inmueble (tipo: departamento\|casa\|local\|campo · modalidad: alquiler\|venta · tokko_id opcional) |
| **Cliente** | Persona física/jurídica (rol: propietario\|inquilino\|comprador\|vendedor) |
| **Contrato** | Alquiler o boleto compraventa — liga propiedad + partes |
| **AjusteContrato** | Periodicidad (3/6/12 meses) + índice (IPC, ICL, fijo) |
| **Pago** | Mensualidad / expensas / impuestos / municipales |
| **Evento** | Activity log (vencimiento, pago, ajuste, alta, baja) |
| **ConsultaIA** | Log del agente WhatsApp (input, intent, respuesta) |

---

## 🛣️ Fases

### Fase 1 — v0 ✅ (esta entrega)
- Scaffold backend FastAPI + SQLite + JWT
- Scaffold frontend React + Vite + Tailwind paleta CIUDAD
- CRUD: Propiedades, Clientes, Contratos
- Calculadora de costos (cálculo local, demo)
- Vista Agente IA (UI placeholder, sin bot real aún)
- Seed con datos demo
- Launchers `.bat` Windows

### Fase 2 — Integraciones
- **Tokko Broker API** — sync de propiedades en venta (pull periódico + webhook)
- **Índices reales** — scraper/feed INDEC para IPC, BCRA para ICL
- **PDF de contratos** — plantillas legales (alquiler vivienda, alquiler comercial, boleto CV)

### Fase 3 — Agente IA
- Webhook WhatsApp (Twilio o Meta Cloud API)
- Tool-calling LLM contra la API interna (`consultar_propiedad`, `calcular_alquiler`, `crear_evento`, etc.)
- Memoria de conversación por número de teléfono
- Permisos por rol (qué puede hacer cada agente)

### Fase 4 — Operaciones avanzadas
- Liquidaciones a propietarios automáticas (alquiler − comisión − gastos)
- Recordatorios de vencimiento (email + WhatsApp)
- Dashboard financiero (cobrado vs pendiente, mora, proyección)
- Carga de fotos y documentos por propiedad

---

## 📐 Diseño visual

Mismo ADN del template RCA (Apple keynote minimalista) con paleta propia CIUDAD:

| Color | Hex | Uso |
|-------|-----|-----|
| **Noche profundo** | `#0F1A2E` | Texto principal, primary |
| **Cobre** | `#B8893A` | Accent, eyebrows |
| **Cobre oscuro** | `#8F6A2A` | Accent dark |
| **Cuero** | `#8B5A2B` | Warning |
| **Marfil** | `#F1ECE3` | Surfaces |
| **Crema** | `#FAF8F3` | Background |

Tipografía Inter, hero titles 5-6xl con punto final, cards rounded-3xl, botones pill, glass top-nav.

---

## 🚀 Cómo correr la v0

```bash
# Doble-clic
start-backend.bat
start-frontend.bat

# Manual
cd backend && python run.py        # → http://localhost:8000
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

**Demo:** `admin@ciudad.com` / `ciudad1234`
