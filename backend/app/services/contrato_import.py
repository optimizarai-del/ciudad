"""
Importación de contratos desde PDF con IA (Anthropic Claude).

Flujo:
1. El frontend manda el PDF como multipart/form-data.
2. Lo pasamos en base64 a Claude con un prompt que pide extraer:
   - Datos del propietario (locador)
   - Datos del inquilino (locatario)
   - Datos del inmueble (dirección, tipo, etc.)
   - Datos del contrato (tipo, fechas, monto, depósito, comisión, ajuste)
3. Claude devuelve JSON estructurado.
4. El endpoint /preview lo retorna sin guardar; el frontend muestra el form
   prellenado para que el operador revise.
5. /confirmar recibe el JSON revisado y crea las entidades en orden
   (clientes → propiedad → contrato), reutilizando registros existentes
   por DNI o por dirección.

Requiere ANTHROPIC_API_KEY en el entorno.
"""
import base64
import json
import os
import re
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.workspace import workspace_flag


SYSTEM_PROMPT = """Sos un asistente que extrae datos estructurados de contratos
inmobiliarios argentinos (alquileres y boletos de compraventa). Tu única salida
es JSON válido, sin markdown ni texto adicional.

Esquema de respuesta:
{
  "tipo": "alquiler_vivienda" | "alquiler_comercial" | "boleto_compraventa" | "sena_alquiler",
  "estado": "borrador" | "vigente" | "vencido" | "rescindido" | "reservado",
  "fecha_inicio": "YYYY-MM-DD" | null,
  "fecha_fin": "YYYY-MM-DD" | null,
  "monto_inicial": <number> | null,
  "deposito": <number> | null,
  "indice_ajuste": "ipc" | "icl" | "fijo" | "sin_ajuste",
  "periodicidad_meses": <number, default 6>,
  "porcentaje_fijo": <number> | null,
  "comision_porc": <number> | null,
  "notas": <string breve resumiendo cláusulas relevantes>,

  "propietario": {
    "nombre": <string>,
    "apellido": <string> | null,
    "razon_social": <string> | null,
    "documento": <DNI o CUIT con guiones si los hay> | null,
    "email": <string> | null,
    "telefono": <string> | null
  },
  "inquilino": {
    "nombre": <string>,
    "apellido": <string> | null,
    "razon_social": <string> | null,
    "documento": <string> | null,
    "email": <string> | null,
    "telefono": <string> | null
  },
  "propiedad": {
    "direccion": <string>,
    "ciudad": <string> | null,
    "provincia": <string> | null,
    "tipo": "departamento" | "casa" | "local" | "oficina" | "galpon" | "campo",
    "modalidad": "alquiler" | "venta" | "ambas",
    "superficie_m2": <number> | null,
    "ambientes": <number> | null,
    "descripcion": <string breve> | null,
    "precio_alquiler": <number> | null,
    "expensas": <number> | null,
    "tasa_municipal": <number> | null
  }
}

Reglas:
- Si no podés determinar un campo, devolvé null (NO inventes).
- Montos en pesos argentinos como número, sin símbolos ni miles. Ejemplo: 350000.
- Las fechas siempre en formato ISO YYYY-MM-DD. Si el contrato dice "1 de enero
  de 2026", devolvé "2026-01-01".
- Si el contrato menciona un ajuste por IPC pero no aclara periodicidad,
  asumí 6 meses.
- "monto_inicial" es el valor del primer mes del alquiler (o el precio total
  si es boleto de compraventa).
- Para los nombres: separá nombre y apellido si vienen juntos. Si es una
  empresa, usá `razon_social` y dejá `nombre`/`apellido` vacíos.
- Si encontrás CUIT/CUIL en formato XX-XXXXXXXX-X mantené los guiones.
"""


def parsear_contrato_pdf(pdf_bytes: bytes, filename: str = "contrato.pdf") -> dict:
    """Llama a Claude con el PDF y devuelve el dict parseado.

    Lanza ValueError si no hay API key o si la respuesta no es JSON válido.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no está configurada en el servidor.")

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    msg = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL_IMPORT", "claude-sonnet-4-5"),
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extraé los datos estructurados de este contrato "
                            "inmobiliario según el esquema indicado en las "
                            "instrucciones. Devolvé SOLO el JSON, sin texto extra."
                        ),
                    },
                ],
            }
        ],
    )

    # Concatenar bloques de texto
    out = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")

    # Claude a veces envuelve en ```json … ``` — limpiar
    out = out.strip()
    if out.startswith("```"):
        out = re.sub(r"^```(?:json)?\s*", "", out)
        out = re.sub(r"\s*```\s*$", "", out)

    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude no devolvió JSON parseable: {e}. Respuesta: {out[:500]}")

    # Asegurar las claves obligatorias
    data.setdefault("propietario", {})
    data.setdefault("inquilino", {})
    data.setdefault("propiedad", {})
    return data


def _buscar_cliente_existente(
    db: Session, datos: dict, rol: str, is_demo: bool
) -> Optional[models.Cliente]:
    """Busca por documento (preferido) o por nombre+apellido si no hay doc."""
    doc = (datos.get("documento") or "").strip()
    q = db.query(models.Cliente).filter(models.Cliente.is_demo == is_demo)
    if doc:
        match = q.filter(models.Cliente.documento == doc).first()
        if match:
            return match
    razon = (datos.get("razon_social") or "").strip()
    if razon:
        match = q.filter(models.Cliente.razon_social.ilike(razon)).first()
        if match:
            return match
    nombre = (datos.get("nombre") or "").strip()
    apellido = (datos.get("apellido") or "").strip()
    if nombre and apellido:
        match = q.filter(
            models.Cliente.nombre.ilike(nombre),
            models.Cliente.apellido.ilike(apellido),
        ).first()
        if match:
            return match
    return None


def _buscar_propiedad_existente(
    db: Session, datos: dict, is_demo: bool
) -> Optional[models.Propiedad]:
    dir_norm = (datos.get("direccion") or "").strip()
    if not dir_norm:
        return None
    q = db.query(models.Propiedad).filter(models.Propiedad.is_demo == is_demo)
    # Igualdad case-insensitive
    match = q.filter(models.Propiedad.direccion.ilike(dir_norm)).first()
    return match


def crear_desde_parsed(db: Session, datos: dict, user) -> dict:
    """Crea/reutiliza propietario, inquilino, propiedad y contrato a partir
    del JSON extraído. Devuelve un resumen de lo que hizo (ids + flags
    'reutilizado' por entidad).

    No hace commit final hasta tener todo armado para ser transaccional.
    """
    is_demo = workspace_flag(user)
    resumen = {
        "propietario": {"id": None, "reutilizado": False},
        "inquilino":   {"id": None, "reutilizado": False},
        "propiedad":   {"id": None, "reutilizado": False},
        "contrato":    {"id": None, "codigo": None},
    }

    # 1. Propietario
    prop_data = datos.get("propietario") or {}
    propietario = _buscar_cliente_existente(db, prop_data, "propietario", is_demo)
    if propietario:
        resumen["propietario"] = {"id": propietario.id, "reutilizado": True}
    else:
        if not (prop_data.get("nombre") or prop_data.get("razon_social")):
            raise ValueError("Falta el nombre del propietario para poder importar.")
        propietario = models.Cliente(
            nombre=prop_data.get("nombre") or (prop_data.get("razon_social") or "Propietario"),
            apellido=prop_data.get("apellido"),
            razon_social=prop_data.get("razon_social"),
            documento=prop_data.get("documento"),
            email=prop_data.get("email"),
            telefono=prop_data.get("telefono"),
            rol=models.ClienteRol.propietario,
            notas="[IMPORTADO desde PDF]",
            is_demo=is_demo,
        )
        db.add(propietario); db.flush()
        resumen["propietario"] = {"id": propietario.id, "reutilizado": False}

    # 2. Inquilino
    inq_data = datos.get("inquilino") or {}
    inquilino = None
    if (inq_data.get("nombre") or inq_data.get("razon_social") or inq_data.get("documento")):
        inquilino = _buscar_cliente_existente(db, inq_data, "inquilino", is_demo)
        if inquilino:
            resumen["inquilino"] = {"id": inquilino.id, "reutilizado": True}
        else:
            inquilino = models.Cliente(
                nombre=inq_data.get("nombre") or (inq_data.get("razon_social") or "Inquilino"),
                apellido=inq_data.get("apellido"),
                razon_social=inq_data.get("razon_social"),
                documento=inq_data.get("documento"),
                email=inq_data.get("email"),
                telefono=inq_data.get("telefono"),
                rol=models.ClienteRol.inquilino,
                notas="[IMPORTADO desde PDF]",
                is_demo=is_demo,
            )
            db.add(inquilino); db.flush()
            resumen["inquilino"] = {"id": inquilino.id, "reutilizado": False}

    # 3. Propiedad
    propd = datos.get("propiedad") or {}
    if not propd.get("direccion"):
        raise ValueError("Falta la dirección de la propiedad para poder importar.")
    propiedad = _buscar_propiedad_existente(db, propd, is_demo)
    if propiedad:
        resumen["propiedad"] = {"id": propiedad.id, "reutilizado": True}
        # Reasignar propietario si la propiedad no tenía uno y ahora sí
        if not propiedad.propietario_id:
            propiedad.propietario_id = propietario.id
    else:
        tipo = propd.get("tipo") or "departamento"
        modalidad = propd.get("modalidad") or "alquiler"
        try:
            tipo_enum = models.PropiedadTipo(tipo)
        except ValueError:
            tipo_enum = models.PropiedadTipo.departamento
        try:
            mod_enum = models.PropiedadModalidad(modalidad)
        except ValueError:
            mod_enum = models.PropiedadModalidad.alquiler
        propiedad = models.Propiedad(
            direccion=propd["direccion"],
            ciudad=propd.get("ciudad"),
            provincia=propd.get("provincia"),
            tipo=tipo_enum,
            modalidad=mod_enum,
            estado=models.PropiedadEstado.ocupada if inquilino else models.PropiedadEstado.disponible,
            superficie_m2=propd.get("superficie_m2"),
            ambientes=propd.get("ambientes"),
            descripcion=(propd.get("descripcion") or "") + " [IMPORTADO desde PDF]",
            precio_alquiler=propd.get("precio_alquiler") or 0,
            expensas=propd.get("expensas") or 0,
            tasa_municipal=propd.get("tasa_municipal") or 0,
            propietario_id=propietario.id,
            is_demo=is_demo,
        )
        db.add(propiedad); db.flush()
        resumen["propiedad"] = {"id": propiedad.id, "reutilizado": False}

    # 4. Contrato
    tipo_c = datos.get("tipo") or "alquiler_vivienda"
    estado_c = datos.get("estado") or "vigente"
    indice_c = datos.get("indice_ajuste") or "ipc"
    try:
        tipo_enum = models.ContratoTipo(tipo_c)
    except ValueError:
        tipo_enum = models.ContratoTipo.alquiler_vivienda
    try:
        estado_enum = models.ContratoEstado(estado_c)
    except ValueError:
        estado_enum = models.ContratoEstado.vigente
    try:
        indice_enum = models.IndiceAjuste(indice_c)
    except ValueError:
        indice_enum = models.IndiceAjuste.ipc

    from app.routers.contratos import _generar_codigo
    codigo = _generar_codigo(db, is_demo)

    from datetime import date as _date
    def _parse_date(s):
        if not s:
            return None
        try:
            return _date.fromisoformat(s)
        except Exception:
            return None

    contrato = models.Contrato(
        codigo=codigo,
        tipo=tipo_enum,
        estado=estado_enum,
        propiedad_id=propiedad.id,
        inquilino_id=inquilino.id if inquilino else None,
        fecha_inicio=_parse_date(datos.get("fecha_inicio")),
        fecha_fin=_parse_date(datos.get("fecha_fin")),
        monto_inicial=datos.get("monto_inicial") or 0,
        deposito=datos.get("deposito") or 0,
        indice_ajuste=indice_enum,
        periodicidad_meses=datos.get("periodicidad_meses") or 6,
        porcentaje_fijo=datos.get("porcentaje_fijo") or 0,
        comision_porc=datos.get("comision_porc") or 0,
        notas=(datos.get("notas") or "") + "\n[IMPORTADO desde PDF]",
        is_demo=is_demo,
    )
    db.add(contrato)
    db.commit()
    db.refresh(contrato)
    resumen["contrato"] = {"id": contrato.id, "codigo": contrato.codigo}
    return resumen
