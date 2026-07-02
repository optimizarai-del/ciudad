# Análisis de competencia — CIUDAD vs. eSecure · Plato · ZAIGEST

> Software inmobiliario argentino. Comparación de **CIUDAD** (módulos Alquileres + Ventas)
> contra tres competidores directos. Elaborado a partir del análisis en vivo de los
> sitios de los competidores (Playwright) y del inventario real del código de CIUDAD.
>
> **Fecha:** 2026-07 · **Rama analizada:** `ventas/estabilizacion`

---

## 1. Los tres competidores

### eSecure — esecure.com.ar
"El software líder para inmobiliarias". El más **veterano/tradicional**; foco en
**administración de alquileres y cobranzas**. Presume ~268 clientes.

**Servicios:**
- Cobros y liquidaciones **multi-contrato / multi-inmueble**, parciales, multi-forma de pago
- **Punitorios automáticos** · Sistema **"Mora 0"** (notifica a locatarios y garantes)
- **Administración de consorcios** (gastos A/B/C/D, expensas por email, cobranza SIRO Banco Roela)
- CRM / seguimiento de contactos y leads
- Propiedades con **geolocalización Google Maps + Street View**
- **RED eSecure:** compartir propiedades entre inmobiliarias clientes, con % de comisión
- **Sitio web corporativo incluido** + publicación automática en portales
- **Portal del Inquilino** con reclamos (opcional)
- Integraciones opcionales: **Facturación AFIP**, cobranza electrónica **SIRO / Pago Fácil / Rapipago**
- 100% nube, backups redundantes

**Precio:** no público ("Consultar"). Abono mensual + cargo anual de hosting/actualizaciones.

**Lectura:** producto maduro en administración, pero de generación anterior (sin IA, precios ocultos).

---

### Plato — plato.com.ar
"Toda la gestión inmobiliaria en Plato". Un **backoffice modular, conectado y trazable**.
Discurso sobrio y honesto (no promete magia). Estética SaaS moderna.

**Servicios:**
- **Gestión comercial:** propiedades y negocios, pipeline, tareas, responsables, publicaciones
- **Tasaciones con IA** (comparables, rangos de valor)
- **Contratos digitales** con **firma digital** y templates (alquiler/venta/reserva/administración)
- **Documentos verificados:** checklists por tipo de operación (DNI, garantías, títulos, seguros)
- **Liquidaciones:** cobros, comisiones, expensas, reparaciones, historial descargable
- **Postventa y reclamos:** tickets, mantenimiento, aprobaciones, trazabilidad
- **Alertas:** renovación, garantías, seguros, pagos
- **Integraciones:** Tokko, CRMs existentes; puede funcionar como capa operativa

**Precio:** no público (4 planes gated por "Solicitar demo"; hasta 20 / 100 / ilimitadas propiedades / Enterprise con API+SLA).

**Lectura:** el más cercano en filosofía a CIUDAD (modular, trazable, integra Tokko, tasación IA). Debilidad: no muestra precios y la IA se limita a tasaciones.

---

### ZAIGEST — zaigest.com.ar
"No es un CRM, es un sistema operativo que dirige tu inmobiliaria". El más **innovador y mejor
comercializado**. Apuesta central: un **Director IA + 5 Gerentes IA** que dicen qué hacer cada día.

**Gerentes IA (24/7):** Comercial, Captaciones, Contractual, Financiero, Marketing → el **Director IA**
los consolida en un plan del día priorizado.

**Servicios:**
- **OCR de contratos con IA** (foto → inquilino, garante, montos, fechas, cláusulas)
- **Carga de propiedad desde el plano** (IA completa dirección, superficies, nomenclatura)
- **Scoring de morosos** predictivo (score 0–100 antes de firmar)
- **Ajuste automático IPC / ICL / UVA**
- **Cobros MercadoPago** (link de pago + conciliación automática)
- **Facturación ARCA/AFIP** (factura C con el recibo)
- **WhatsApp** Business Cloud API (Meta) automático
- **Tasación con IA** · **Mapa inteligente por zona** (precio/m², rentabilidad)
- **Marketing:** email, redes, campañas WhatsApp, chatbot web, publicación en MercadoLibre
- **Portales** del Propietario y del Inquilino · Web pública con marca propia

**Precio (público):** Starter **$39.000/mes** · Pro **$79.000** · Business **$139.000** · Enterprise **desde $249.000**.
Add-ons y instalación asistida ($290k/$550k/$850k one-shot). Sin permanencia.

**Lectura:** el líder. Ventaja: capa de IA "que dirige" + hiper-adaptación a Argentina. Precios transparentes.

---

## 2. Qué tiene CIUDAD (inventario real del código)

### Módulo Alquileres
- **Ajuste de contratos automático** IPC / ICL / fijo con **tasas en vivo de INDEC + BCRA**, periodicidad
  configurable (1/3/6/12 meses) y trazabilidad por ajuste (`ajuste_contratos.py`, `indices_service.py`)
- **Liquidaciones a propietarios** multi-inmueble, con **co-propietarios y % normalizados** (lógica anti-overpay),
  comisión, gastos, comprobante PDF (inquilino + propietario), **reversión** (`liquidaciones.py`)
- **Cobranza** con estados (pendiente/pagado/vencido/parcial), desglose por conceptos JSON, arrastre de pendientes
- **Refacciones** con descuento automático (paga inquilino → se descuenta del pago; paga propietario → gasto en liquidación)
- **Tasas municipales** con auto-consulta **MSR (Santa Rosa / La Pampa)** (`tasas_msr.py`)
- **Contratos** PDF/DOCX + multi-inquilino/garantes + **import desde PDF/DOC con IA** + alertas 7/30/60 días
- **Comunicaciones:** WhatsApp (Meta Business API) + Telegram (staff) + Email + **recordatorios automáticos**
- **Calculadora** de monto vigente con índices en vivo
- **Historial/auditoría con reversión** (snapshots JSON)
- **Workspace demo/real aislado** (`is_demo`)

### Módulo Ventas (rama `ventas/estabilizacion`)
- **CRM = Pipeline de cliente:** 10 etapas + **temperatura** (caliente/tibio/frío) + **próxima acción obligatoria**
  + **SLA por etapa** + **degradación automática con consulta al líder** (Fases 1-2)
- **Motor de matching explicable** pedido ↔ propiedad (score con razones: precio +40, zona +25, dormitorios +20,
  m² +10, baños +5; umbral 60) (`ventas_matching.py`)
- **Red Tokko en vivo:** login/scraping de la red Tokko por zona, desambiguación, solo Argentina (`ventas_red_tokko.py`)
- **Scraping de portales** (Argenprop/Zonaprop) con cola Redis+RQ
- **Geolocalización precisa por zona:** Google Maps + Nominatim + **constraint de radio** — una búsqueda en
  Santa Rosa nunca ubica una propiedad en Pilar; corrige pines con signo invertido (`ventas_geo.py`)
- **Recomendaciones IA** por cliente (Claude, con fallback a reglas) (`ventas_recomendaciones.py`)
- **NLU** (parseo de pedido desde texto libre) · **Tasación con IA**
- **Fase 3:** métricas del pipeline (embudo acumulado, conversión etapa-a-etapa, valor total y ponderado),
  **vista Líder** (ranking por vendedor), **export CSV/PDF**
- **Mapa grande** con todas las propiedades geolocalizadas · importar → auto mapa + auto matches

---

## 3. Comparación por dominio

Leyenda: ✅ fuerte · ⚠️ parcial · ❌ no tiene

### Inventario de propiedades (oferta)
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Catálogo propio | ✅ | ✅ | ✅ | ✅ |
| Geoloc en mapa | ✅ validada por zona | ✅ | ⚠️ | ✅ |
| Traer inventario de otras inmobiliarias | ✅ Red Tokko vivo + scraping portales | ⚠️ solo RED interna eSecure | ⚠️ sync Tokko propio | ❌ |
| Multi-fuente agregado | ✅ | ❌ | ❌ | ❌ |

**Gana CIUDAD.** Único que agrega oferta de terceros y corrige el pin a la zona.

### CRM / gestión de la demanda
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Pipeline de cliente | ✅ 10 etapas + temperatura | ⚠️ | ✅ | ✅ |
| Próxima acción obligatoria | ✅ | ❌ | ❌ | ⚠️ |
| SLA + degradación con consulta al líder | ✅ | ❌ | ❌ | ❌ |
| Matching pedido↔propiedad explicable | ✅ | ❌ | ❌ | ⚠️ |
| Ranking de vendedores | ✅ | ❌ | ⚠️ | ✅ |

**Gana CIUDAD** en rigor operativo; empata con ZAIGEST en "inteligencia".

### Contratos
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Generación PDF/DOCX | ✅ | ✅ | ✅ | ✅ |
| Multi-inquilino + garantes | ✅ | ⚠️ | ✅ | ⚠️ |
| Import PDF/DOC con IA | ✅ | ❌ | ⚠️ | ✅ OCR |
| **Firma digital** | ❌ | ❌ | ✅ | ✅ |
| Carga desde plano | ❌ | ❌ | ❌ | ✅ |

**Empate; ZAIGEST/Plato ganan por firma digital.**

### Cobranza / pagos
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Registro + estados + conceptos | ✅ | ✅ | ✅ | ✅ |
| **Cobro online (pasarela)** | ❌ | ✅ SIRO/Pago Fácil/Rapipago | ❌ | ✅ MercadoPago |
| Mora / punitorios automáticos | ⚠️ manual | ✅ | ⚠️ | ✅ |
| Scoring de morosos | ❌ | ❌ | ❌ | ✅ |

**Pierde CIUDAD.** Dominio más débil.

### Liquidaciones a propietarios
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Comisión + gastos | ✅ | ✅ | ✅ | ✅ |
| Multi-inmueble | ✅ | ✅ | ⚠️ | ✅ |
| Co-propietarios con % normalizados | ✅ | ⚠️ | ❌ | ⚠️ |
| Reversión | ✅ | ⚠️ | ❌ | ⚠️ |

**Gana/empata CIUDAD.**

### Ajustes por índice
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| IPC/ICL/fijo automático | ✅ tasas en vivo INDEC/BCRA | ⚠️ | ⚠️ | ✅ ICL/IPC/UVA |
| Trazabilidad por ajuste | ✅ | ⚠️ | ⚠️ | ✅ |

**Empata con ZAIGEST; gana a Plato/eSecure.** Falta sumar UVA al motor de cálculo.

### Fiscal AFIP/ARCA
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Factura electrónica | ❌ | ✅ opcional | ❌ | ✅ |

**Pierde CIUDAD.** (Ventaja lateral: experiencia AFIP en el proyecto Larrañaga.)

### Portales de autoservicio
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Portal inquilino | ❌ | ✅ | ✅ | ✅ |
| Portal propietario | ❌ | ✅ | ✅ | ✅ |

**Pierde CIUDAD.** Los tres lo tienen.

### Comunicaciones
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| WhatsApp | ✅ Meta API | ⚠️ | ⚠️ | ✅ |
| Telegram (staff) | ✅ | ❌ | ❌ | ❌ |
| Recordatorios automáticos | ✅ | ✅ | ✅ | ✅ |
| Marketing (campañas/chatbot/redes) | ❌ | ⚠️ | ❌ | ✅ |

**Empate operativo; ZAIGEST gana en marketing.**

### IA / inteligencia
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Recomendaciones de acción por cliente | ✅ Claude | ❌ | ❌ | ✅ 5 gerentes |
| NLU (texto libre) | ✅ | ❌ | ❌ | ⚠️ |
| Tasación IA | ✅ | ❌ | ✅ | ✅ |
| OCR / import contrato IA | ✅ | ❌ | ⚠️ | ✅ |

**Empate con ZAIGEST; gana a eSecure/Plato.** Falta empaquetar/narrar la IA.

### Localismo argentino
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Índices oficiales en vivo | ✅ INDEC/BCRA/dólar | ⚠️ | ⚠️ | ✅ |
| Tasa municipal auto (Santa Rosa/LP) | ✅ MSR | ❌ | ❌ | ❌ |
| Consorcios | ❌ | ✅ | ❌ | ❌ |

**Ganás en hiper-localismo pampeano; eSecure gana en consorcios.**

### Arquitectura / operación
| | CIUDAD | eSecure | Plato | ZAIGEST |
|---|---|---|---|---|
| Auditoría con reversión | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Workspace demo/real aislado | ✅ | ❌ | ❌ | ❌ |
| API pública documentada | ⚠️ interna | ❌ | ✅ | ✅ |

**Ganás en auditoría reversible y modo demo; ellos en API pública.**

---

## 4. Scorecard

| Dominio | Ganador |
|---|---|
| Inventario / oferta | 🟢 CIUDAD |
| CRM / demanda | 🟢 CIUDAD (empate IA con ZAIGEST) |
| Liquidaciones | 🟢 CIUDAD |
| Ajustes por índice | 🟡 CIUDAD = ZAIGEST |
| IA | 🟡 CIUDAD = ZAIGEST |
| Localismo | 🟡 mixto (MSR vs. consorcios) |
| Auditoría / demo | 🟢 CIUDAD |
| Contratos | 🔴 ZAIGEST/Plato (firma digital) |
| Cobranza / pagos | 🔴 eSecure/ZAIGEST |
| Fiscal AFIP | 🔴 eSecure/ZAIGEST |
| Portales autoservicio | 🔴 todos |
| Marketing | 🔴 ZAIGEST |

---

## 5. Lectura estratégica

CIUDAD **no compite de igual a igual**: los tres son software para administrar *tu propia* cartera;
CIUDAD además **busca oportunidades de negocio** (agrega inventario ajeno + matchea demanda + pipeline
con inteligencia). Está en otra categoría por ese eje.

- **Donde somos claramente mejores:** oferta multi-fuente + geoloc correcta, matching explicable,
  disciplina del pipeline, liquidaciones finas, auditoría reversible, modo demo.
- **Empatamos con el líder (ZAIGEST):** IA de recomendaciones, ajustes por índice, tasación.
- **Donde perdemos (y define muchas ventas):** cobro online (MercadoPago), AFIP/ARCA, portales de
  autoservicio. Son *checklist items* que el comprador espera — 3 features, no 3 productos.

**Movimiento ganador:** cerrar esos 3 huecos transaccionales (ventaja en AFIP por Larrañaga) y
**empaquetar/narrar la IA** como hace ZAIGEST (las piezas ya existen; falta el relato).

---

## 6. Roadmap de brechas (prioridad)

| # | Brecha | Impacto competitivo | Esfuerzo | Prioridad |
|---|---|---|---|---|
| 1 | **Cobro online MercadoPago** (link + conciliación) | Alto (lo espera todo comprador) | Medio | 🔴 P0 |
| 2 | **Portal del inquilino / propietario** | Alto (reduce llamados, muy vendible) | Medio-Alto | 🔴 P0 |
| 3 | **Factura electrónica AFIP/ARCA** | Alto | Medio (ventaja Larrañaga) | 🟠 P1 |
| 4 | **Firma digital de contratos** | Medio | Medio | 🟠 P1 |
| 5 | **Empaquetar la IA como "gerentes/asistentes"** | Alto (percepción/venta) | Bajo (ya existe la lógica) | 🟠 P1 |
| 6 | **Mora / punitorios automáticos** | Medio | Bajo | 🟡 P2 |
| 7 | **Scoring de morosos** | Medio | Medio | 🟡 P2 |
| 8 | **Marketing (campañas/chatbot)** | Medio | Alto | 🟡 P2 |
| 9 | **UVA en el motor de ajuste** | Bajo | Bajo | 🟢 P3 |
| 10 | **Consorcios** | Bajo (otro segmento) | Alto | 🟢 P3 |
