# CIUDAD. — Inmuebles · Contratos · Gestión

Plataforma inmobiliaria full-stack para gestión integral de propiedades, contratos de alquiler, boletos de compraventa y calculadora de costos automática.

## 🚀 Inicio rápido

```bash
# 1. Doble-clic en start-backend.bat
# 2. Doble-clic en start-frontend.bat
# 3. Abrir http://localhost:5173
# 4. Login: admin@ciudad.com / ciudad1234
```

## 📦 Stack

| Capa | Tech |
|------|------|
| Frontend | React 18 + Vite 5 + Tailwind CSS 3 |
| Backend  | FastAPI 0.110 + SQLAlchemy 2 + SQLite |
| Auth     | JWT (python-jose + passlib/bcrypt) |
| Diseño   | Inter · paleta blanco/negro/gris · Apple-style |

## 🗂️ Módulos

| Módulo | Descripción |
|--------|-------------|
| **Propiedades** | CRUD de inmuebles (depto, casa, local, campo). Modalidad alquiler/venta. Integración Tokko Broker (campo `tokko_id`). |
| **Contratos** | Alquiler vivienda, alquiler comercial, boleto compraventa. Ajuste por IPC/ICL/fijo con periodicidad configurable. |
| **Clientes** | Propietarios, inquilinos, compradores, vendedores. |
| **Calculadora** | Escribís la dirección → costo total instantáneo (alquiler ajustado + expensas + impuestos + municipal). |
| **Agente IA** | Chat interno con el sistema. Consultas en lenguaje natural. Fase 3: WhatsApp Bot. |
| **Finanzas** | Resumen de ingresos, depósitos y comisiones por contratos vigentes. |
| **Equipo** | Gestión de usuarios y roles del sistema. |

## 🗺️ Roadmap

- **Fase 1 ✅** — Plataforma base funcionando (este repo)
- **Fase 2** — Sync Tokko Broker · Índices INDEC/BCRA reales · PDF de contratos
- **Fase 3** — WhatsApp Bot (Twilio/Meta) + LLM con tool-calling
- **Fase 4** — Liquidaciones automáticas · Recordatorios · Deploy producción

## 🔐 Roles

| Rol | Acceso |
|-----|--------|
| `admin` | Acceso total |
| `operador` | Propiedades, contratos, clientes, calculadora, agente |
| `finanzas` | + módulo finanzas |
| `agente_ia` | Solo calculadora y agente |

## 🛠️ Instalación manual

```bash
# Backend
cd backend
pip install -r requirements.txt
python run.py               # → http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                 # → http://localhost:5173
```

## 📁 Estructura

```
ciudad/
├── backend/               # FastAPI + SQLAlchemy + SQLite
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py      # 8 modelos de dominio
│   │   ├── routers/       # auth, propiedades, clientes, contratos, calculadora, agente, dashboard
│   │   ├── seed.py        # datos demo
│   │   └── security.py    # JWT + bcrypt
│   └── run.py
│
└── frontend/              # React + Vite + Tailwind
    └── src/
        ├── pages/         # Dashboard, Propiedades, Contratos, Clientes, Calculadora, Agente, Finanzas, Equipo
        ├── components/    # HUD, Sidebar, Layout, Logo
        └── context/       # AuthContext
```

---

> **CIUDAD.** — Inmuebles · Contratos · Gestión
