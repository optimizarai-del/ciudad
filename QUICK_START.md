# 🚀 Quick Start — CIUDAD.

## En 30 segundos

```
1. Doble-clic → start-backend.bat
2. Doble-clic → start-frontend.bat
3. Abrir      → http://localhost:5173
4. Login      → admin@ciudad.com / ciudad1234
```

---

## URLs clave

| Servicio | URL |
|----------|-----|
| **App**  | http://localhost:5173 |
| **API**  | http://localhost:8000 |
| **Swagger Docs** | http://localhost:8000/docs |

---

## Módulos disponibles

| Ruta | Módulo | Quién accede |
|------|--------|-------------|
| `/dashboard`   | Panel principal | Todos |
| `/propiedades` | Cartera inmobiliaria | Todos |
| `/contratos`   | Alquileres y boletos | Todos |
| `/clientes`    | Propietarios e inquilinos | Todos |
| `/calculadora` | Cálculo de costos | Todos |
| `/agente`      | Chat IA | Todos |
| `/finanzas`    | Resumen financiero | admin + finanzas |
| `/equipo`      | Gestión de usuarios | admin |

---

## Primeros pasos recomendados

### 1. Cargar propiedades
- Ir a `/propiedades`
- Click **Nueva propiedad**
- Completar: dirección, tipo, modalidad, precios base, expensas e impuestos

### 2. Cargar clientes
- Ir a `/clientes`
- Crear propietarios e inquilinos
- Asignar propietario a cada inmueble

### 3. Crear contratos
- Ir a `/contratos`
- Click **Nuevo contrato**
- Elegir propiedad → inquilino → tipo (alquiler/boleto) → índice ajuste (IPC/ICL/fijo) → periodicidad

### 4. Usar la calculadora
- Ir a `/calculadora`
- Escribir la dirección del inmueble
- Ver al instante: alquiler actualizado + expensas + impuestos + total

---

## Resetear base de datos

```bash
cd backend
del ciudad.db
python run.py        # recrea schema vacío + seed demo
```

---

## Comandos útiles

```bash
# Backend
cd backend
pip install -r requirements.txt
python run.py

# Frontend
cd frontend
npm install
npm run dev
npm run build
```

---

> **CIUDAD.** — Inmuebles · Contratos · Gestión
