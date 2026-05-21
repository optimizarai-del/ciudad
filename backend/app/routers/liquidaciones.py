"""
Liquidaciones a propietarios — entrega física del dinero.

Lógica:
  1. Cuando el inquilino paga (Cobranza), el Pago queda con estado=pagado y
     liquidado_propietario=False. La inmobiliaria todavía no le entregó el
     dinero al dueño del inmueble.
  2. Cuando el propietario viene a buscar su parte, en /alquileres/liquidaciones
     se ve la lista de pagos "pendientes de liquidar" agrupados por propietario.
     Al marcarlo como "liquidado", queda registrado quién, cuándo y cuánto
     neto recibió.
  3. Después se puede consultar el historial de liquidaciones por propietario
     (cuáles cobraron y cuáles están pendientes).

  GET    /api/liquidaciones                    — lista de pagos liquidables con su estado
  POST   /api/liquidaciones/{pago_id}/marcar   — marca como liquidado al propietario
  POST   /api/liquidaciones/{pago_id}/revertir — desmarca (corrige error)
  GET    /api/liquidaciones/resumen            — KPIs para el header de la página
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.workspace import apply_workspace_filter as _ws


router = APIRouter(prefix="/api/liquidaciones", tags=["liquidaciones"])


def _calcular_neto(pago: models.Pago, contrato: models.Contrato | None) -> float:
    """Neto que le toca al propietario:
        (alquiler − comisión sobre alquiler)
        + expensas + tasas municipales + otros conceptos cobrados al inquilino

    El propietario paga previamente expensas, tasas, etc. al consorcio/municipio.
    Cuando la inmobiliaria los cobra al inquilino, ese dinero le pertenece al
    propietario íntegro (sin comisión). La comisión sólo se aplica al alquiler.
    """
    alquiler = float(pago.monto_alquiler or 0)
    comision_porc = float(contrato.comision_porc or 0) if contrato else 0.0
    comision = round(alquiler * comision_porc / 100.0, 2)
    # Pasantes cobrados al inquilino (estado='cobrar') → van íntegros al propietario
    pasantes_total = 0.0
    if pago.detalle_conceptos:
        import json
        try:
            conceptos = json.loads(pago.detalle_conceptos) or []
            for c in conceptos:
                estado = c.get("estado") or ("pagado_directo" if c.get("paga") == "propietario" else "cobrar")
                if estado == "cobrar":
                    pasantes_total += float(c.get("monto") or 0)
        except Exception:
            pasantes_total = 0.0
    else:
        # Fallback legacy: campos sueltos en el pago
        pasantes_total = (
            float(pago.monto_expensas or 0)
            + float(pago.monto_municipal or 0)
            + float(pago.monto_otros or 0)
        )
    return round(alquiler - comision + pasantes_total, 2)


def _propietario_dict(c: models.Cliente | None) -> dict:
    if not c:
        return {"id": None, "nombre": "Sin propietario", "documento": None,
                "email": None, "telefono": None}
    nombre = c.razon_social or " ".join([p for p in [c.nombre, c.apellido] if p]).strip()
    return {
        "id": c.id, "nombre": nombre or "Sin nombre",
        "documento": c.documento, "email": c.email, "telefono": c.telefono,
    }


def _split_neto_por_copropietarios(pago: models.Pago, neto_total: float) -> list[dict]:
    """Divide el neto total entre los co-propietarios de la propiedad según
    el porcentaje configurado en la pivote `propiedad_propietarios`.

    Reglas:
    - Si la propiedad tiene 1 solo dueño: 100% para él.
    - Si tiene varios y todos tienen porcentaje seteado: respeta los porcentajes
      (los normaliza si no suman 100, evitando que el operador pague de más).
    - Si ninguno tiene porcentaje: división equitativa.
    - Si algunos sí y otros no: ignora los porcentajes parciales y divide en
      partes iguales (más seguro que mezclar).
    """
    contrato = pago.contrato
    prop = contrato.propiedad if contrato else None
    if not prop:
        return [{
            "cliente_id": None, "nombre": "Sin propietario",
            "porcentaje_efectivo": 100.0, "neto_parte": neto_total,
        }]
    co_props = list(prop.propietarios or [])
    if not co_props:
        # Fallback al legacy propietario_id
        if prop.propietario:
            return [{
                "cliente_id": prop.propietario.id,
                "nombre": (prop.propietario.razon_social or
                           f"{prop.propietario.nombre} {prop.propietario.apellido or ''}".strip()),
                "porcentaje_efectivo": 100.0,
                "neto_parte": neto_total,
            }]
        return [{
            "cliente_id": None, "nombre": "Sin propietario",
            "porcentaje_efectivo": 100.0, "neto_parte": neto_total,
        }]

    if len(co_props) == 1:
        c = co_props[0].cliente
        return [{
            "cliente_id": c.id if c else None,
            "nombre": (c.razon_social or
                       f"{c.nombre} {c.apellido or ''}".strip()) if c else "Sin nombre",
            "porcentaje_efectivo": 100.0,
            "neto_parte": neto_total,
        }]

    # Múltiples co-propietarios
    todos_con_porc = all(pp.porcentaje is not None for pp in co_props)
    suma = sum((pp.porcentaje or 0) for pp in co_props)
    if todos_con_porc and suma > 0:
        # Normalizar a 100 si la suma no es exactamente 100
        factor = 100.0 / suma
        partes = []
        for pp in co_props:
            porc_norm = (pp.porcentaje or 0) * factor
            c = pp.cliente
            partes.append({
                "cliente_id": c.id if c else None,
                "nombre": (c.razon_social or
                           f"{c.nombre} {c.apellido or ''}".strip()) if c else "Sin nombre",
                "porcentaje_efectivo": round(porc_norm, 2),
                "neto_parte": round(neto_total * porc_norm / 100.0, 2),
            })
        return partes

    # Sin porcentajes (o mezclados) → división equitativa
    n = len(co_props)
    porc_cada = 100.0 / n
    parte = round(neto_total / n, 2)
    return [
        {
            "cliente_id": pp.cliente.id if pp.cliente else None,
            "nombre": (pp.cliente.razon_social or
                       f"{pp.cliente.nombre} {pp.cliente.apellido or ''}".strip())
                      if pp.cliente else "Sin nombre",
            "porcentaje_efectivo": round(porc_cada, 2),
            "neto_parte": parte,
        }
        for pp in co_props
    ]


def _serializar_pago(pago: models.Pago) -> dict:
    contrato = pago.contrato
    prop = contrato.propiedad if contrato else None
    propietario = prop.propietario if prop else None
    inquilino = contrato.inquilino if contrato else None
    neto = _calcular_neto(pago, contrato)
    split = _split_neto_por_copropietarios(pago, neto)
    # Refacciones que se descontaron en este pago — las mostramos en el
    # desglose del modal de liquidación para que el operador vea por qué
    # el monto cobrado al inquilino fue menor.
    from sqlalchemy.orm import object_session
    sess = object_session(pago)
    refacciones_aplicadas = []
    if sess:
        refs = sess.query(models.Refaccion).filter_by(pago_id=pago.id).all()
        for r in refs:
            refacciones_aplicadas.append({
                "id": r.id,
                "descripcion": r.descripcion,
                "monto": r.monto,
                "fecha": r.fecha.isoformat() if r.fecha else None,
                "pagador": r.pagador.value if hasattr(r.pagador, "value") else r.pagador,
            })
    return {
        "pago_id": pago.id,
        "periodo": pago.periodo,
        "fecha_pago_inquilino": pago.fecha_pago.isoformat() if pago.fecha_pago else None,
        "monto_total_cobrado": pago.monto_total or 0,
        "monto_alquiler": pago.monto_alquiler or 0,
        "monto_expensas": pago.monto_expensas or 0,
        "monto_municipal": pago.monto_municipal or 0,
        "monto_otros": pago.monto_otros or 0,
        "detalle_conceptos": pago.detalle_conceptos,
        "refacciones_aplicadas": refacciones_aplicadas,
        "comision_porc": float(contrato.comision_porc or 0) if contrato else 0.0,
        "neto_a_pagar": neto,
        # estado de liquidación
        "liquidado": bool(pago.liquidado_propietario),
        "fecha_liquidacion": (
            pago.fecha_liquidacion_propietario.isoformat()
            if pago.fecha_liquidacion_propietario else None
        ),
        "monto_liquidado": pago.monto_liquidado_propietario,
        "notas_liquidacion": pago.notas_liquidacion,
        # contexto
        "contrato_id": contrato.id if contrato else None,
        "contrato_codigo": contrato.codigo if contrato else None,
        "propiedad_id": prop.id if prop else None,
        "propiedad_direccion": prop.direccion if prop else None,
        "propiedad_ciudad": prop.ciudad if prop else None,
        "inquilino_nombre": (
            f"{inquilino.nombre} {inquilino.apellido or ''}".strip()
            if inquilino else None
        ),
        # Propietario principal (legacy) — para compatibilidad con UI vieja
        "propietario": _propietario_dict(propietario),
        # Split entre co-propietarios: cada uno con porcentaje y monto que le toca.
        # Si hay 1 solo, viene una entrada con 100%. Si hay varios, viene el
        # detalle según porcentajes de la pivote.
        "co_propietarios": split,
    }


@router.get("")
def listar(
    estado: Optional[str] = "pendientes",   # pendientes | liquidadas | todas
    propietario_id: Optional[int] = None,
    mes: Optional[str] = None,              # filtro YYYY-MM
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Lista los pagos liquidables (estado=pagado) con su estado de liquidación.

    Por default solo trae los pendientes de entregarle al propietario, que es
    el flujo principal: el propietario llega, lo buscamos por su nombre y
    marcamos lo que le entregamos.
    """
    q = (
        _ws(db.query(models.Pago), models.Pago, user)
          .options(
              joinedload(models.Pago.contrato).joinedload(models.Contrato.propiedad).joinedload(models.Propiedad.propietario),
              joinedload(models.Pago.contrato).joinedload(models.Contrato.inquilino),
          )
          .filter(models.Pago.estado == models.PagoEstado.pagado)
    )
    if estado == "pendientes":
        q = q.filter(models.Pago.liquidado_propietario.is_(False))
    elif estado == "liquidadas":
        q = q.filter(models.Pago.liquidado_propietario.is_(True))
    # 'todas' no filtra

    if mes:
        q = q.filter(models.Pago.periodo == mes)

    if propietario_id:
        # Tenemos que filtrar por propietario via JOINs explícitos
        q = (
            q.join(models.Contrato, models.Pago.contrato_id == models.Contrato.id)
             .join(models.Propiedad, models.Contrato.propiedad_id == models.Propiedad.id)
             .filter(models.Propiedad.propietario_id == propietario_id)
        )

    rows = q.order_by(models.Pago.fecha_pago.desc().nullslast(), models.Pago.id.desc()).all()
    items = [_serializar_pago(p) for p in rows]

    # Agrupado por co-propietario: si una propiedad tiene 2 dueños, el pago
    # aparece en AMBOS grupos con su parte correspondiente. Esto es lo que
    # el operador necesita: "¿cuánto le debo a cada propietario?".
    grupos = {}
    for it in items:
        for co in it["co_propietarios"]:
            pid = co["cliente_id"] or 0
            if pid not in grupos:
                grupos[pid] = {
                    "propietario": {
                        "id": co["cliente_id"],
                        "nombre": co["nombre"],
                        # Datos extra del cliente principal de ese ítem si coincide
                        "documento": (it["propietario"].get("documento")
                                      if it["propietario"]["id"] == co["cliente_id"] else None),
                        "email": (it["propietario"].get("email")
                                  if it["propietario"]["id"] == co["cliente_id"] else None),
                    },
                    "items": [],
                    "total_neto_pendiente": 0,
                    "total_neto_liquidado": 0,
                    "pendientes": 0,
                    "liquidados": 0,
                }
            # Item enriquecido con la parte específica de este co-propietario
            item_co = dict(it)
            item_co["mi_porcentaje"] = co["porcentaje_efectivo"]
            item_co["mi_parte"] = co["neto_parte"]
            grupos[pid]["items"].append(item_co)
            if it["liquidado"]:
                grupos[pid]["liquidados"] += 1
                # Si está liquidado, prorrateamos el monto realmente entregado
                # según el porcentaje (asume que se entregó proporcional)
                entregado_total = it["monto_liquidado"] or it["neto_a_pagar"]
                grupos[pid]["total_neto_liquidado"] += round(
                    entregado_total * co["porcentaje_efectivo"] / 100.0, 2
                )
            else:
                grupos[pid]["pendientes"] += 1
                grupos[pid]["total_neto_pendiente"] += co["neto_parte"]

    grupos_lista = sorted(grupos.values(), key=lambda g: g["total_neto_pendiente"], reverse=True)

    return {
        "items": items,
        "agrupado_por_propietario": grupos_lista,
        "total": len(items),
    }


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """KPIs para el header de la página."""
    q_base = (
        _ws(db.query(models.Pago), models.Pago, user)
          .filter(models.Pago.estado == models.PagoEstado.pagado)
    )
    pagos = (
        q_base
          .options(joinedload(models.Pago.contrato))
          .all()
    )
    pendientes = liquidados = 0
    total_neto_pendiente = 0.0
    total_neto_liquidado = 0.0
    for p in pagos:
        neto = _calcular_neto(p, p.contrato)
        if p.liquidado_propietario:
            liquidados += 1
            total_neto_liquidado += float(p.monto_liquidado_propietario or neto)
        else:
            pendientes += 1
            total_neto_pendiente += neto
    return {
        "pendientes": pendientes,
        "liquidados": liquidados,
        "total_neto_pendiente": round(total_neto_pendiente, 2),
        "total_neto_liquidado": round(total_neto_liquidado, 2),
    }


@router.post("/{pago_id}/marcar")
def marcar_liquidado(
    pago_id: int,
    data: dict = Body(default={}),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Marca un pago como liquidado al propietario.

    Body opcional:
      - fecha: YYYY-MM-DD (default hoy)
      - monto: float — neto realmente entregado (default = calculado)
      - notas: str
    """
    pago = _ws(db.query(models.Pago), models.Pago, user).filter_by(id=pago_id).first()
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    if pago.estado != models.PagoEstado.pagado:
        raise HTTPException(400, "Este pago todavía no fue cobrado al inquilino, no se puede liquidar al propietario.")
    if pago.liquidado_propietario:
        raise HTTPException(409, "Este pago ya estaba marcado como liquidado.")

    # Parsear fecha custom
    fecha_str = data.get("fecha")
    try:
        fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
    except Exception:
        raise HTTPException(400, "fecha inválida (esperado YYYY-MM-DD)")

    # Monto: si no viene, lo calculamos
    monto = data.get("monto")
    if monto is None:
        monto = _calcular_neto(pago, pago.contrato)
    try:
        monto = float(monto)
    except Exception:
        raise HTTPException(400, "monto inválido")

    pago.liquidado_propietario = True
    pago.fecha_liquidacion_propietario = fecha
    pago.monto_liquidado_propietario = monto
    notas = (data.get("notas") or "").strip()
    if notas:
        pago.notas_liquidacion = notas

    # Log de evento (auditoría)
    contrato = pago.contrato
    prop = contrato.propiedad if contrato else None
    propietario = prop.propietario if prop else None
    nombre_prop = (
        propietario.razon_social
        or f"{propietario.nombre} {propietario.apellido or ''}".strip()
    ) if propietario else "Sin propietario"
    ev = models.Evento(
        tipo=models.EventoTipo.pago,
        titulo=f"Liquidación al propietario — {nombre_prop}",
        descripcion=(
            f"Pago #{pago.id} · período {pago.periodo} · neto $ {monto:,.0f} · "
            f"fecha {fecha.isoformat()}"
        ),
        contrato_id=pago.contrato_id,
        propiedad_id=prop.id if prop else None,
        user_id=user.id if user else None,
        es_critico=False,
    )
    db.add(ev)
    db.commit(); db.refresh(pago)
    return _serializar_pago(pago)


@router.post("/{pago_id}/revertir")
def revertir_liquidado(
    pago_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Desmarca un pago como liquidado (corregir error)."""
    pago = _ws(db.query(models.Pago), models.Pago, user).filter_by(id=pago_id).first()
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    if not pago.liquidado_propietario:
        raise HTTPException(409, "Este pago no estaba marcado como liquidado.")

    pago.liquidado_propietario = False
    pago.fecha_liquidacion_propietario = None
    pago.monto_liquidado_propietario = None
    # Mantenemos notas_liquidacion como histórico

    db.commit(); db.refresh(pago)
    return _serializar_pago(pago)
