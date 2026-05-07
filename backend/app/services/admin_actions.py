"""
Acciones administrativas que el agente de Telegram puede invocar.

Cada función:
  - Toma una `db: Session` y argumentos primitivos (str/int/float/list).
  - Ejecuta la acción en la base.
  - Devuelve un dict con `ok` + datos legibles para que el agente arme la respuesta.

NO toca el flujo público de leads. Estas son acciones DE STAFF.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models


# ────────────────────────────────────────────────────────────────────
# Búsquedas / lecturas
# ────────────────────────────────────────────────────────────────────

def buscar_propiedad(db: Session, query: str, limit: int = 10) -> dict:
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "Falta texto de búsqueda"}
    rows = (
        db.query(models.Propiedad)
        .filter(or_(
            models.Propiedad.direccion.ilike(f"%{q}%"),
            models.Propiedad.codigo.ilike(f"%{q}%"),
            models.Propiedad.ciudad.ilike(f"%{q}%"),
            models.Propiedad.tokko_id == q,
        ))
        .limit(limit).all()
    )
    return {
        "ok": True,
        "total": len(rows),
        "propiedades": [
            {
                "id": p.id,
                "codigo": p.codigo,
                "direccion": p.direccion,
                "ciudad": p.ciudad,
                "tipo": p.tipo.value if hasattr(p.tipo, "value") else p.tipo,
                "modalidad": p.modalidad.value if hasattr(p.modalidad, "value") else p.modalidad,
                "estado": p.estado.value if hasattr(p.estado, "value") else p.estado,
                "precio_alquiler": p.precio_alquiler or 0,
                "precio_venta": p.precio_venta or 0,
                "tasas_municipales": (p.tasa_municipal or 0) + (p.impuesto_inmobiliario or 0),
                "expensas": p.expensas or 0,
            }
            for p in rows
        ],
    }


def info_propiedad(db: Session, identificador: str | int) -> dict:
    """Resuelve por id, código o dirección (la mejor coincidencia)."""
    p = None
    if isinstance(identificador, int) or (isinstance(identificador, str) and identificador.isdigit()):
        p = db.query(models.Propiedad).filter_by(id=int(identificador)).first()
    if not p:
        p = (
            db.query(models.Propiedad)
            .filter(or_(
                models.Propiedad.codigo == str(identificador),
                models.Propiedad.direccion.ilike(f"%{identificador}%"),
            ))
            .first()
        )
    if not p:
        return {"ok": False, "error": f"Propiedad no encontrada: {identificador}"}

    propietario = p.propietario
    contrato = (
        db.query(models.Contrato)
        .filter(models.Contrato.propiedad_id == p.id, models.Contrato.estado == models.ContratoEstado.vigente)
        .first()
    )
    return {
        "ok": True,
        "propiedad": {
            "id": p.id, "codigo": p.codigo, "direccion": p.direccion,
            "ciudad": p.ciudad, "provincia": p.provincia,
            "tipo": p.tipo.value if hasattr(p.tipo, "value") else p.tipo,
            "modalidad": p.modalidad.value if hasattr(p.modalidad, "value") else p.modalidad,
            "estado": p.estado.value if hasattr(p.estado, "value") else p.estado,
            "precio_alquiler": p.precio_alquiler or 0,
            "precio_venta": p.precio_venta or 0,
            "expensas": p.expensas or 0,
            "tasas_municipales": (p.tasa_municipal or 0) + (p.impuesto_inmobiliario or 0),
            "ambientes": p.ambientes,
            "superficie_m2": p.superficie_m2,
        },
        "propietario": {
            "id": propietario.id,
            "nombre": " ".join([x for x in [propietario.nombre, propietario.apellido] if x]) or propietario.razon_social,
            "email": propietario.email,
            "telefono": propietario.telefono,
        } if propietario else None,
        "contrato_vigente": {
            "id": contrato.id,
            "codigo": contrato.codigo,
            "monto_inicial": contrato.monto_inicial,
            "fecha_inicio": str(contrato.fecha_inicio) if contrato.fecha_inicio else None,
            "fecha_fin": str(contrato.fecha_fin) if contrato.fecha_fin else None,
        } if contrato else None,
    }


def info_contrato(db: Session, identificador: str | int) -> dict:
    c = None
    if isinstance(identificador, int) or (isinstance(identificador, str) and str(identificador).isdigit()):
        c = db.query(models.Contrato).filter_by(id=int(identificador)).first()
    if not c:
        c = db.query(models.Contrato).filter_by(codigo=str(identificador)).first()
    if not c:
        return {"ok": False, "error": f"Contrato no encontrado: {identificador}"}
    prop = c.propiedad
    inq = c.inquilino
    return {
        "ok": True,
        "contrato": {
            "id": c.id, "codigo": c.codigo,
            "tipo": c.tipo.value if hasattr(c.tipo, "value") else c.tipo,
            "estado": c.estado.value if hasattr(c.estado, "value") else c.estado,
            "monto_inicial": c.monto_inicial,
            "fecha_inicio": str(c.fecha_inicio) if c.fecha_inicio else None,
            "fecha_fin": str(c.fecha_fin) if c.fecha_fin else None,
            "comision_porc": c.comision_porc,
            "indice_ajuste": c.indice_ajuste.value if hasattr(c.indice_ajuste, "value") else c.indice_ajuste,
            "propiedad": prop.direccion if prop else None,
            "inquilino": " ".join([x for x in [inq.nombre, inq.apellido] if x]) if inq else None,
        },
    }


def listar_pendientes_cobro(db: Session, mes: Optional[str] = None) -> dict:
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"
    contratos = db.query(models.Contrato).filter(
        models.Contrato.estado == models.ContratoEstado.vigente
    ).all()
    pendientes = []
    total_pendiente = 0
    for c in contratos:
        pago = (
            db.query(models.Pago)
            .filter(models.Pago.contrato_id == c.id, models.Pago.periodo == mes)
            .first()
        )
        if pago and pago.estado == models.PagoEstado.pagado:
            continue
        prop = c.propiedad
        inq = c.inquilino
        monto = (pago.monto_total if pago else None) or (c.monto_inicial or 0)
        total_pendiente += monto
        pendientes.append({
            "contrato_id": c.id,
            "contrato_codigo": c.codigo,
            "propiedad": prop.direccion if prop else "",
            "inquilino": " ".join([x for x in [inq.nombre, inq.apellido] if x]) if inq else "",
            "monto": monto,
            "estado": pago.estado.value if pago and hasattr(pago.estado, "value") else "pendiente",
        })
    return {"ok": True, "mes": mes, "total_pendientes": len(pendientes),
            "monto_total_pendiente": total_pendiente, "items": pendientes}


def resumen_dashboard(db: Session) -> dict:
    total_props = db.query(models.Propiedad).count()
    disp = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.disponible).count()
    ocup = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.ocupada).count()
    contratos_vig = db.query(models.Contrato).filter_by(estado=models.ContratoEstado.vigente).count()
    clientes = db.query(models.Cliente).count()
    propietarios = db.query(models.Cliente).filter_by(rol=models.ClienteRol.propietario).count()
    leads_nuevos = db.query(models.Lead).filter_by(estado=models.LeadEstado.nuevo).count()
    return {
        "ok": True,
        "propiedades_total": total_props,
        "propiedades_disponibles": disp,
        "propiedades_ocupadas": ocup,
        "contratos_vigentes": contratos_vig,
        "clientes_total": clientes,
        "propietarios": propietarios,
        "leads_nuevos": leads_nuevos,
    }


# ────────────────────────────────────────────────────────────────────
# Acciones masivas (las modificaciones que pidió el usuario)
# ────────────────────────────────────────────────────────────────────

def _resolver_propiedad(db: Session, ref) -> Optional[models.Propiedad]:
    """`ref` puede ser id, código o substring de dirección."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
        p = db.query(models.Propiedad).filter_by(id=int(ref)).first()
        if p: return p
    s = str(ref).strip()
    p = db.query(models.Propiedad).filter(models.Propiedad.codigo == s).first()
    if p: return p
    return db.query(models.Propiedad).filter(models.Propiedad.direccion.ilike(f"%{s}%")).first()


def _bulk_update_campo(db: Session, updates: list[dict], campo: str) -> dict:
    """
    updates = [{"propiedad": "<id|codigo|direccion>", "monto": 12345.0}, ...]
    """
    if not updates:
        return {"ok": False, "error": "Lista vacía"}
    ok_items, fallidos = [], []
    for u in updates:
        ref = u.get("propiedad") or u.get("direccion") or u.get("id") or u.get("codigo")
        monto = u.get("monto", u.get("valor"))
        if ref is None or monto is None:
            fallidos.append({"input": u, "razon": "Falta propiedad o monto"})
            continue
        try:
            monto = float(monto)
        except (TypeError, ValueError):
            fallidos.append({"input": u, "razon": "Monto inválido"})
            continue
        p = _resolver_propiedad(db, ref)
        if not p:
            fallidos.append({"input": u, "razon": "Propiedad no encontrada"})
            continue
        anterior = getattr(p, campo) or 0
        setattr(p, campo, monto)
        # Si actualizamos tasa_municipal, blanqueamos el campo legacy.
        if campo == "tasa_municipal":
            p.impuesto_inmobiliario = 0
        ok_items.append({
            "id": p.id, "codigo": p.codigo, "direccion": p.direccion,
            "anterior": anterior, "nuevo": monto,
        })
    db.commit()
    return {
        "ok": True,
        "actualizadas": len(ok_items),
        "fallidas": len(fallidos),
        "items": ok_items,
        "errores": fallidos,
    }


def actualizar_tasas_municipales(db: Session, updates: list[dict]) -> dict:
    """Actualiza el campo unificado `tasa_municipal` para una lista de propiedades."""
    return _bulk_update_campo(db, updates, "tasa_municipal")


def actualizar_alquileres(db: Session, updates: list[dict]) -> dict:
    return _bulk_update_campo(db, updates, "precio_alquiler")


def actualizar_expensas(db: Session, updates: list[dict]) -> dict:
    return _bulk_update_campo(db, updates, "expensas")


def cambiar_estado_propiedad(db: Session, identificador, nuevo_estado: str) -> dict:
    p = _resolver_propiedad(db, identificador)
    if not p:
        return {"ok": False, "error": f"Propiedad no encontrada: {identificador}"}
    valido = [e.value for e in models.PropiedadEstado]
    if nuevo_estado not in valido:
        return {"ok": False, "error": f"Estado inválido. Válidos: {', '.join(valido)}"}
    anterior = p.estado.value if hasattr(p.estado, "value") else p.estado
    p.estado = nuevo_estado
    db.commit()
    return {"ok": True, "id": p.id, "direccion": p.direccion,
            "anterior": anterior, "nuevo": nuevo_estado}


# Mapa nombre → fn para el dispatcher del agente
TOOLS = {
    "buscar_propiedad": buscar_propiedad,
    "info_propiedad": info_propiedad,
    "info_contrato": info_contrato,
    "listar_pendientes_cobro": listar_pendientes_cobro,
    "resumen_dashboard": resumen_dashboard,
    "actualizar_tasas_municipales": actualizar_tasas_municipales,
    "actualizar_alquileres": actualizar_alquileres,
    "actualizar_expensas": actualizar_expensas,
    "cambiar_estado_propiedad": cambiar_estado_propiedad,
}
