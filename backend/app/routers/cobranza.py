"""
Cobranza:
  GET   /api/cobranza/mensual?mes=YYYY-MM        — lista TODOS los contratos vigentes
                                                    con su pago del mes (existente o "pendiente").
  GET   /api/cobranza/resumen?mes=YYYY-MM        — totales cobrado/pendiente/vencido.
  PATCH /api/cobranza/{pago_id}/cobrar           — marcar pago como cobrado.
  POST  /api/cobranza/{contrato_id}/registrar-pago
        body: {periodo, fecha_pago, monto_alquiler, monto_expensas, monto_impuestos,
               monto_municipal, monto_otros, monto_total, notas}
        → crea/actualiza el Pago, genera 2 comprobantes PDF (inquilino + propietario),
          intenta enviarlos por email y los guarda en la base.
"""
import base64
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.workspace import apply_workspace_filter, workspace_flag
from app.services.pdf_comprobantes import (
    generar_pdf_comprobante_inquilino,
    generar_pdf_comprobante_propietario,
)
from app.services.email_service import enviar_email, smtp_configurado
from app.services import supabase_storage

router = APIRouter(prefix="/api/cobranza", tags=["cobranza"])


def _conceptos_pendientes_arrastrados(db: Session, contrato_id: int, mes_actual: str) -> list[dict]:
    """
    Mira todos los pagos previos del contrato y devuelve los conceptos que
    quedaron en estado 'pendiente' y NO se cobraron/pagaron en períodos
    posteriores. Cada item viene con `label`, `monto`, `desde_periodo` para
    que el frontend muestre de dónde viene el arrastre.
    """
    import json as _json
    pagos = (
        db.query(models.Pago)
        .filter(models.Pago.contrato_id == contrato_id, models.Pago.periodo < mes_actual)
        .order_by(models.Pago.periodo.asc())
        .all()
    )
    # Acumulador por label en minúsculas. Cada concepto puede aparecer
    # `pendiente` en un mes y `cobrar`/`pagado_directo` en otro posterior,
    # en cuyo caso se considera saldado.
    pendientes: dict[str, dict] = {}
    for p in pagos:
        raw = p.detalle_conceptos
        if not raw:
            continue
        try:
            arr = _json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        for c in (arr or []):
            label = (c.get("label") or "").strip()
            if not label:
                continue
            key = label.lower()
            estado = c.get("estado") or _legacy_paga_to_estado(c.get("paga"))
            if estado == "pendiente":
                pendientes[key] = {
                    "label": label,
                    "monto": float(c.get("monto") or 0),
                    "desde_periodo": p.periodo,
                }
            elif estado in ("cobrar", "pagado_directo"):
                # Saldó la deuda — lo sacamos del acumulador.
                pendientes.pop(key, None)
    return list(pendientes.values())


def _legacy_paga_to_estado(paga: str | None) -> str:
    # Compat retro: el modelo viejo era `paga: inquilino|propietario`.
    # `inquilino` significaba "se cobra ahora con el alquiler" → `cobrar`.
    # `propietario` significaba "lo paga el propietario aparte" → `pagado_directo`.
    if paga == "propietario":
        return "pagado_directo"
    return "cobrar"


def _indice_str_safe(c: models.Contrato) -> str:
    v = c.indice_ajuste
    if v is None:
        return "sin_ajuste"
    return v.value if hasattr(v, "value") else str(v)


def _count_ajustes_safe(c: models.Contrato) -> int:
    """Cuenta ajustes aplicados sin romper si la tabla no existe."""
    try:
        return len(c.ajustes or [])
    except Exception:
        return 0


def _last_ajuste_info(c: models.Contrato) -> dict | None:
    """Devuelve los datos del último ajuste registrado, o None si no hay.
    Defensivo: si la tabla ajustes_contrato aún no existe en este deploy,
    devuelve None sin romper la response."""
    try:
        ajustes = list(c.ajustes or [])
        if not ajustes:
            return None
        ultimo = max(ajustes, key=lambda a: (a.fecha or None, a.id))
        return {
            "fecha":          ultimo.fecha.isoformat() if ultimo.fecha else None,
            "porcentaje":     float(ultimo.porcentaje or 0),
            "monto_anterior": float(ultimo.monto_anterior or 0),
            "monto_nuevo":    float(ultimo.monto_nuevo or 0),
            "indice_usado":   ultimo.indice_usado,
        }
    except Exception as e:
        print(f"[_last_ajuste_info] {type(e).__name__}: {e}")
        return None


def _nombre_cliente(c: models.Cliente | None) -> str:
    if not c:
        return ""
    if c.razon_social:
        return c.razon_social
    return " ".join([p for p in [c.nombre, c.apellido] if p]) or ""


@router.get("/mensual")
def cobranza_mensual(mes: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Devuelve, para el mes pedido, una entrada por cada contrato vigente.
    Si ya hay un Pago para ese período devuelve sus datos; si no, marca estado='pendiente'.

    Optimización de queries:
      Antes: 5 queries por contrato (N+1) → con 100 contratos = 500+ queries.
      Ahora: 4 queries TOTALES sin importar cuántos contratos haya:
        1. Contratos vigentes con propiedad+propietario+inquilino cargados en JOIN.
        2. Todos los Pagos del mes actual para esos contratos (IN clause).
        3. Todos los Pagos previos (para conceptos arrastrados) en una sola query.
        4. Todas las Refacciones pendientes del inquilino en una sola query.
      Los conceptos arrastrados se calculan en Python (sin queries adicionales).
    """
    import json as _json

    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    # ── Query 1: contratos vigentes con todas las relaciones necesarias ──────
    contratos = (
        apply_workspace_filter(db.query(models.Contrato), models.Contrato, user)
        .filter(models.Contrato.estado == models.ContratoEstado.vigente)
        .options(
            joinedload(models.Contrato.propiedad)
            .joinedload(models.Propiedad.propietario),
            joinedload(models.Contrato.inquilino),
        )
        .all()
    )

    if not contratos:
        return []

    # ── Aplicar ajustes pendientes (lazy) ────────────────────────────────────
    # Cada vez que se carga el mes de cobranza, revisamos si algún contrato
    # tiene ajustes pendientes según su índice (IPC/ICL/fijo) y periodicidad,
    # y los aplicamos antes de armar el listado. Así el monto sugerido del
    # alquiler siempre refleja el valor ajustado al período actual.
    try:
        from app.services.ajuste_contratos import aplicar_ajustes_pendientes_bulk
        creados = aplicar_ajustes_pendientes_bulk(db, contratos)
        if creados:
            db.commit()
    except Exception as e:
        print(f"[cobranza] aplicar_ajustes_pendientes_bulk falló: {e}")
        db.rollback()

    cids = [c.id for c in contratos]

    # ── Query 2: pagos del mes actual para todos los contratos ───────────────
    # Tomamos el más reciente por contrato (mayor id).
    pagos_mes: dict[int, models.Pago] = {}
    for p in (
        db.query(models.Pago)
        .filter(models.Pago.contrato_id.in_(cids), models.Pago.periodo == mes)
        .order_by(models.Pago.id.asc())   # asc → el último en el dict gana (mayor id)
        .all()
    ):
        pagos_mes[p.contrato_id] = p

    # ── Query 3: pagos previos para calcular conceptos arrastrados ───────────
    prior_pagos: dict[int, list] = {}
    for p in (
        db.query(models.Pago)
        .filter(models.Pago.contrato_id.in_(cids), models.Pago.periodo < mes)
        .order_by(models.Pago.periodo.asc())
        .all()
    ):
        prior_pagos.setdefault(p.contrato_id, []).append(p)

    # ── Query 4: refacciones pendientes del inquilino para todos contratos ───
    refs_map: dict[int, list] = {}
    for r in (
        db.query(models.Refaccion)
        .filter(
            models.Refaccion.contrato_id.in_(cids),
            models.Refaccion.pagador == models.RefaccionPagador.inquilino,
            models.Refaccion.estado == models.RefaccionEstado.pendiente,
        )
        .order_by(models.Refaccion.fecha.asc())
        .all()
    ):
        refs_map.setdefault(r.contrato_id, []).append(r)

    # ── Calcular conceptos arrastrados en Python (sin queries adicionales) ───
    def _conceptos_desde_pagos(pagos: list) -> list[dict]:
        pendientes: dict[str, dict] = {}
        for p in pagos:
            raw = p.detalle_conceptos
            if not raw:
                continue
            try:
                arr = _json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue
            for c in (arr or []):
                label = (c.get("label") or "").strip()
                if not label:
                    continue
                key = label.lower()
                estado = c.get("estado") or _legacy_paga_to_estado(c.get("paga"))
                if estado == "pendiente":
                    pendientes[key] = {
                        "label": label,
                        "monto": float(c.get("monto") or 0),
                        "desde_periodo": p.periodo,
                    }
                elif estado in ("cobrar", "pagado_directo"):
                    pendientes.pop(key, None)
        return list(pendientes.values())

    # ── Armar resultado en Python (sin más queries) ──────────────────────────
    result = []
    for c in contratos:
        prop = c.propiedad          # ya cargado con joinedload
        inq  = c.inquilino          # ya cargado con joinedload
        propietario = prop.propietario if prop else None  # ya cargado en JOIN

        pago               = pagos_mes.get(c.id)
        conceptos_pendientes = _conceptos_desde_pagos(prior_pagos.get(c.id, []))
        refs_pend          = refs_map.get(c.id, [])

        # Monto vigente: último ajuste registrado, o monto_inicial si no hay
        # ajustes. La lazy de arriba ya creó los que correspondan.
        from app.services.ajuste_contratos import monto_vigente
        alquiler_sug = monto_vigente(c) or float((prop.precio_alquiler if prop else 0) or 0)
        tasas_sug    = float((prop.tasa_municipal if prop else 0) or 0) + float((prop.impuesto_inmobiliario if prop else 0) or 0)
        expensas_sug = float((prop.expensas if prop else 0) or 0)

        refs_pend_data = [
            {"id": r.id, "fecha": r.fecha.isoformat() if r.fecha else None,
             "descripcion": r.descripcion, "monto": r.monto}
            for r in refs_pend
        ]
        refs_total = sum((r.monto or 0) for r in refs_pend)

        if pago:
            estado     = pago.estado.value if hasattr(pago.estado, "value") else pago.estado
            monto_total = pago.monto_total or 0
            fecha_venc  = pago.fecha_vencimiento.isoformat() if pago.fecha_vencimiento else None
            fecha_pago  = pago.fecha_pago.isoformat() if pago.fecha_pago else None
        else:
            estado      = "pendiente"
            monto_total = round(alquiler_sug + expensas_sug + tasas_sug, 2)
            fecha_venc  = None
            fecha_pago  = None

        result.append({
            "pago_id":                  pago.id if pago else None,
            "contrato_id":              c.id,
            "contrato_codigo":          c.codigo or f"#{c.id}",
            "propiedad_id":             prop.id if prop else None,
            "propiedad":                prop.direccion if prop else "",
            "propiedad_ciudad":         prop.ciudad if prop else "",
            "numero_referencia":        prop.numero_referencia if prop else None,
            "inquilino_id":             inq.id if inq else None,
            "inquilino":                _nombre_cliente(inq) or "Sin inquilino",
            "inquilino_email":          inq.email if inq else None,
            "inquilino_telefono":       inq.telefono if inq else None,
            "propietario_id":           propietario.id if propietario else None,
            "propietario":              _nombre_cliente(propietario) or "Sin propietario",
            "propietario_email":        propietario.email if propietario else None,
            "comision_porc":            c.comision_porc or 0,
            "monto_total":              monto_total,
            "monto_alquiler_sug":       round(alquiler_sug, 2),
            "monto_alquiler_base":      float(c.monto_inicial or 0),
            "indice_ajuste":            _indice_str_safe(c),
            "ajustes_aplicados":        _count_ajustes_safe(c),
            "ultimo_ajuste":            _last_ajuste_info(c),
            "monto_expensas_sug":       round(expensas_sug, 2),
            "monto_tasas_sug":          round(tasas_sug, 2),
            "conceptos_pendientes":     conceptos_pendientes,
            "refacciones_pendientes":   refs_pend_data,
            "refacciones_descuento_sug": round(refs_total, 2),
            "fecha_vencimiento":        fecha_venc,
            "fecha_pago":               fecha_pago,
            "estado":                   estado,
            "periodo":                  mes,
        })

    return result


@router.patch("/{pago_id}/cobrar")
def marcar_cobrado(pago_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pago = db.query(models.Pago).get(pago_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    pago.estado = models.PagoEstado.pagado
    pago.fecha_pago = date.today()
    db.commit()
    return {"ok": True, "fecha_pago": pago.fecha_pago.isoformat()}


@router.get("/resumen")
def resumen_cobranza(mes: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Suma cobrado/pendiente/vencido del mes.
    Importante: los contratos vigentes que aún no tienen Pago registrado para
    el período cuentan como `pendiente` (con el monto esperado calculado a
    partir del contrato + costos de la propiedad). Si no fuera así, un mes
    sin pagos cargados se reportaba erróneamente como "100% cobrado".
    """
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    contratos = apply_workspace_filter(db.query(models.Contrato), models.Contrato, user).filter(
        models.Contrato.estado == models.ContratoEstado.vigente
    ).all()

    cobrado = pendiente = vencido = 0.0
    pagos_count = 0

    for c in contratos:
        pago = (
            db.query(models.Pago)
            .filter(models.Pago.contrato_id == c.id, models.Pago.periodo == mes)
            .order_by(models.Pago.id.desc())
            .first()
        )
        if pago:
            pagos_count += 1
            monto = pago.monto_total or 0
            if pago.estado == models.PagoEstado.pagado:
                cobrado += monto
            elif pago.estado == models.PagoEstado.vencido:
                vencido += monto
            else:
                pendiente += monto
        else:
            # Sin pago registrado → estimación del esperado para que la barra
            # de cobranza tenga base real.
            prop = c.propiedad
            base = float(c.monto_inicial or (prop.precio_alquiler if prop else 0) or 0)
            tasas = (prop.tasa_municipal if prop else 0) + (prop.impuesto_inmobiliario if prop else 0)
            extras = (prop.expensas if prop else 0) + (tasas or 0)
            pendiente += round(base + (extras or 0), 2)

    total = cobrado + pendiente + vencido

    return {
        "mes": mes,
        "cobrado": cobrado,
        "pendiente": pendiente,
        "vencido": vencido,
        "total_esperado": total,
        "porcentaje_cobrado": round((cobrado / total * 100) if total > 0 else 0, 1),
        "contratos_activos": len(contratos),
        "pagos_count": pagos_count,
    }


# ────────────────────────────────────────────────────────────────────
# Registrar pago + comprobantes
# ────────────────────────────────────────────────────────────────────

class RegistrarPagoIn(BaseModel):
    periodo: Optional[str] = None             # YYYY-MM
    fecha_pago: Optional[date] = None
    monto_alquiler: float = 0
    # Legacy: si vienen estos campos individuales se asume `paga=inquilino`.
    # El frontend nuevo manda `conceptos` (lista granular).
    monto_expensas: float = 0
    monto_impuestos: float = 0
    monto_municipal: float = 0
    monto_otros: float = 0
    # NUEVO: lista de conceptos extra con quién paga cada uno.
    # [{"label": "Luz", "monto": 15000, "paga": "inquilino"|"propietario"}, ...]
    # Si paga el inquilino, suma al total cobrado. Si paga el propietario,
    # queda informativo en el comprobante pero no se cobra.
    conceptos: list[dict] = []
    monto_descuento_refacciones: float = 0     # se resta del total
    refacciones_aplicadas: list[int] = []       # IDs a marcar como aplicadas
    monto_pagado_transferencia: float = 0      # parte abonada por transferencia (se resta del cobro en caja)
    monto_total: Optional[float] = None
    notas: Optional[str] = None


def _crear_comprobante(db: Session, pago: models.Pago, tipo: models.ComprobanteTipo,
                       nombre: str, email: Optional[str],
                       pdf_bytes: bytes, monto_total: float,
                       monto_comision: float = 0, monto_neto: float = 0,
                       enviar_mail: bool = True,
                       asunto: str = "", cuerpo: str = "") -> models.Comprobante:
    # Subir el PDF a Supabase Storage si está habilitado; fallback a blob en DB.
    storage_path = None
    pdf_b64 = None
    if pdf_bytes:
        if supabase_storage.enabled():
            sp = supabase_storage.gen_path(f"pago-{pago.id}", f"{tipo.value}.pdf")
            ok, info = supabase_storage.upload(
                supabase_storage.BUCKET_COMPROBANTES, sp, pdf_bytes, "application/pdf",
            )
            if ok:
                storage_path = info
            else:
                print(f"[cobranza] Storage upload falló: {info} — fallback base64")
                pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
        else:
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    comp = models.Comprobante(
        pago_id=pago.id,
        tipo=tipo,
        destinatario_nombre=nombre,
        destinatario_email=email,
        monto_total=monto_total,
        monto_comision=monto_comision,
        monto_neto=monto_neto,
        pdf_blob=pdf_b64,
        storage_path=storage_path,
    )
    db.add(comp)
    db.flush()  # obtener id antes del envío

    if enviar_mail and email and smtp_configurado():
        ok, msg = enviar_email(
            email, asunto, cuerpo, pdf_bytes, f"comprobante-{tipo.value}-{comp.id}.pdf"
        )
        comp.enviado_email = ok
        comp.fecha_envio = datetime.utcnow() if ok else None
        comp.error_envio = None if ok else msg
    else:
        comp.enviado_email = False
        comp.error_envio = "SMTP no configurado" if not smtp_configurado() else "Sin email destinatario"
    return comp


@router.post("/{contrato_id}/registrar-pago")
def registrar_pago(
    contrato_id: int,
    data: RegistrarPagoIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return _registrar_pago_impl(contrato_id, data, db, user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[cobranza.registrar_pago] {type(e).__name__}: {e}")
        raise HTTPException(400, f"No se pudo registrar el pago: {type(e).__name__}: {str(e)[:300]}")


def _registrar_pago_impl(
    contrato_id: int,
    data: RegistrarPagoIn,
    db: Session,
    user,
):
    contrato = apply_workspace_filter(db.query(models.Contrato), models.Contrato, user).filter_by(id=contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")
    propiedad = contrato.propiedad
    inquilino = contrato.inquilino
    propietario = propiedad.propietario if propiedad else None

    # Período
    fecha_pago = data.fecha_pago or date.today()
    periodo = data.periodo or f"{fecha_pago.year}-{fecha_pago.month:02d}"

    # Conceptos granulares. Si el frontend manda `conceptos`, eso es la fuente
    # de verdad. Si no, reconstruimos desde los campos legacy (que asumen que
    # todo paga el inquilino).
    descuento_refs = float(data.monto_descuento_refacciones or 0)
    tasas_municipales = float(data.monto_impuestos or 0) + float(data.monto_municipal or 0)
    conceptos_list = []
    ESTADOS_VALIDOS = ("cobrar", "pagado_directo", "pendiente")
    if data.conceptos:
        for c in data.conceptos:
            label = (c.get("label") or "").strip()
            try: monto = float(c.get("monto") or 0)
            except Exception: monto = 0
            # Soporta tanto el modelo nuevo (`estado`) como el viejo (`paga`).
            estado = c.get("estado") or _legacy_paga_to_estado(c.get("paga"))
            if estado not in ESTADOS_VALIDOS:
                estado = "cobrar"
            if label and monto != 0:
                conceptos_list.append({"label": label, "monto": monto, "estado": estado})
    else:
        # Reconstruir desde legacy (todo se cobra ahora)
        if data.monto_expensas:
            conceptos_list.append({"label": "Expensas", "monto": float(data.monto_expensas), "estado": "cobrar"})
        if tasas_municipales:
            conceptos_list.append({"label": "Tasas municipales", "monto": tasas_municipales, "estado": "cobrar"})
        if data.monto_otros:
            conceptos_list.append({"label": "Otros conceptos", "monto": float(data.monto_otros), "estado": "cobrar"})

    # Items para cobrar al inquilino (alquiler + conceptos en estado=cobrar).
    # Esa plata se reenvía al propietario para que pague los servicios (es
    # de paso, no afecta su neto).
    items_cobrar = [("Alquiler", float(data.monto_alquiler or 0))]
    for c in conceptos_list:
        if c["estado"] == "cobrar":
            items_cobrar.append((c["label"], c["monto"]))
    items_no_cero = [(l, v) for l, v in items_cobrar if v and v > 0]
    if descuento_refs > 0:
        items_no_cero.append(("Descuento refacciones", -descuento_refs))
    monto_total = (
        data.monto_total if data.monto_total is not None
        else sum(v for _, v in items_no_cero)
    )

    # Informativos: conceptos que el inquilino ya pagó directo al ente
    # (no se cobran acá, no van al propietario, solo se asientan).
    items_pagado_directo = [
        (c["label"], c["monto"]) for c in conceptos_list if c["estado"] == "pagado_directo"
    ]
    # Informativos: conceptos pendientes que pasan al próximo período.
    items_pendientes = [
        (c["label"], c["monto"]) for c in conceptos_list if c["estado"] == "pendiente"
    ]
    # Compat con el resto del flujo / PDFs (antes era items_propietario_paga).
    items_propietario_paga = items_pagado_directo

    # Crear o actualizar el pago
    pago = (
        db.query(models.Pago)
        .filter(models.Pago.contrato_id == contrato.id, models.Pago.periodo == periodo)
        .first()
    )
    if pago is None:
        pago = models.Pago(contrato_id=contrato.id, periodo=periodo, is_demo=workspace_flag(user))
        db.add(pago)
    pago.fecha_pago = fecha_pago
    pago.monto_alquiler = data.monto_alquiler
    # Sincronizar legacy desde conceptos (suma monto donde paga=inquilino)
    sumas_inq = {"expensas": 0.0, "municipal": 0.0, "otros": 0.0}
    for c in conceptos_list:
        if c["estado"] != "cobrar":
            continue
        low = c["label"].lower()
        if "expensa" in low:
            sumas_inq["expensas"] += c["monto"]
        elif "munic" in low or "tasa" in low or "abl" in low:
            sumas_inq["municipal"] += c["monto"]
        else:
            sumas_inq["otros"] += c["monto"]
    pago.monto_expensas = sumas_inq["expensas"]
    pago.monto_impuestos = 0
    pago.monto_municipal = sumas_inq["municipal"]
    pago.monto_otros = sumas_inq["otros"]
    pago.monto_total = monto_total
    pago.monto_pagado_transferencia = float(data.monto_pagado_transferencia or 0)
    pago.estado = models.PagoEstado.pagado
    pago.notas = data.notas
    # Guardar el JSON granular (incluye quién paga cada uno)
    import json as _json
    pago.detalle_conceptos = _json.dumps(conceptos_list, ensure_ascii=False)
    db.flush()

    # Marcar las refacciones del inquilino como aplicadas a este pago.
    # Validamos que pertenezcan al contrato y estén pendientes para evitar
    # vincular cualquier ID arbitrario.
    refs_aplicadas_count = 0
    if data.refacciones_aplicadas:
        refs = (
            db.query(models.Refaccion)
            .filter(
                models.Refaccion.id.in_(data.refacciones_aplicadas),
                models.Refaccion.contrato_id == contrato.id,
                models.Refaccion.estado == models.RefaccionEstado.pendiente,
            )
            .all()
        )
        for r in refs:
            r.estado = models.RefaccionEstado.aplicada
            r.pago_id = pago.id
            refs_aplicadas_count += 1
        db.flush()

    # Comisión inmobiliaria: se calcula SOLO sobre el alquiler, no sobre los
    # gastos pasantes (expensas, tasas, otros). El propietario percibe
    # alquiler − comisión; las demás partidas las cobra el inquilino y se
    # derivan a quien corresponda (consorcio, municipio, etc).
    monto_alquiler = float(data.monto_alquiler or 0)
    comision_pct = float(contrato.comision_porc or 0)
    comision = round(monto_alquiler * comision_pct / 100.0, 2)
    items_pasantes = [(l, v) for l, v in items_no_cero if l != "Alquiler"]
    # Expensas, tasas, etc. cobrados al inquilino van íntegros al propietario
    # (los abonó previamente). La comisión sólo se aplica al alquiler.
    pasantes_total = sum(v for _, v in items_pasantes)
    neto = round(monto_alquiler - comision + pasantes_total, 2)

    nombre_inq = _nombre_cliente(inquilino) or "Inquilino/a"
    nombre_pro = _nombre_cliente(propietario) or "Propietario/a"
    prop_ctx = {
        "direccion": propiedad.direccion if propiedad else "—",
        "ciudad": propiedad.ciudad if propiedad else "—",
        "codigo": propiedad.codigo if propiedad else None,
    }
    contrato_ctx = {"id": contrato.id, "codigo": contrato.codigo}

    # PDF inquilino
    pdf_inq = generar_pdf_comprobante_inquilino({
        "numero": f"REC-{periodo}-{contrato.id:04d}",
        "fecha_pago": fecha_pago,
        "periodo": periodo,
        "propiedad": prop_ctx,
        "contrato": contrato_ctx,
        "inquilino": {
            "nombre_completo": nombre_inq,
            "documento": inquilino.documento if inquilino else None,
            "email": inquilino.email if inquilino else None,
            "telefono": inquilino.telefono if inquilino else None,
        },
        "items": items_no_cero or [("Pago del período", monto_total)],
        # Conceptos que el inquilino pagó directamente al ente (informativo)
        "items_pagado_directo": items_pagado_directo,
        "total": monto_total,
    })

    # PDF propietario — incluye desglose de lo cobrado al inquilino y la
    # liquidación calculada sobre el alquiler.
    pdf_pro = generar_pdf_comprobante_propietario({
        "numero": f"LIQ-{periodo}-{contrato.id:04d}",
        "fecha_pago": fecha_pago,
        "periodo": periodo,
        "propiedad": prop_ctx,
        "contrato": contrato_ctx,
        "propietario": {
            "nombre_completo": nombre_pro,
            "documento": propietario.documento if propietario else None,
            "email": propietario.email if propietario else None,
            "telefono": propietario.telefono if propietario else None,
        },
        "inquilino": {"nombre_completo": nombre_inq},
        "items_cobrados": items_no_cero or [("Pago del período", monto_total)],
        "items_pasantes": items_pasantes,
        # Conceptos que el inquilino pagó directamente (figuran en pagado, no en rendir)
        "items_pagado_directo": items_pagado_directo,
        "monto_alquiler": monto_alquiler,
        "monto_cobrado_total": monto_total,
        "comision_porc": comision_pct,
        "monto_comision": comision,
        "monto_neto": neto,
    })

    # Crear comprobantes
    cuerpo_inq = (
        f"Hola {nombre_inq},\n\n"
        f"Adjuntamos el recibo del pago correspondiente al período {periodo} "
        f"por la propiedad {prop_ctx['direccion']}.\n\n"
        f"Total abonado: $ {monto_total:,.2f}\n\n"
        f"¡Gracias!\nCIUDAD."
    )
    cuerpo_pro = (
        f"Hola {nombre_pro},\n\n"
        f"Te enviamos la liquidación del período {periodo} correspondiente a "
        f"{prop_ctx['direccion']}.\n\n"
        f"Total cobrado al inquilino: $ {monto_total:,.2f}\n"
        f"Alquiler base: $ {monto_alquiler:,.2f}\n"
        f"Comisión ({comision_pct}% sobre alquiler): $ {comision:,.2f}\n"
        f"Neto a transferir: $ {neto:,.2f}\n\n"
        f"CIUDAD."
    )

    comp_inq = _crear_comprobante(
        db, pago, models.ComprobanteTipo.inquilino,
        nombre_inq, inquilino.email if inquilino else None,
        pdf_inq, monto_total,
        asunto=f"Recibo CIUDAD. — {periodo}", cuerpo=cuerpo_inq,
    )
    comp_pro = _crear_comprobante(
        db, pago, models.ComprobanteTipo.propietario,
        nombre_pro, propietario.email if propietario else None,
        pdf_pro, monto_total, monto_comision=comision, monto_neto=neto,
        asunto=f"Liquidación CIUDAD. — {periodo}", cuerpo=cuerpo_pro,
    )
    db.commit()

    return {
        "ok": True,
        "pago_id": pago.id,
        "periodo": periodo,
        "monto_total": monto_total,
        "comision": comision,
        "neto_propietario": neto,
        "smtp_configurado": smtp_configurado(),
        "refacciones_aplicadas": refs_aplicadas_count,
        "descuento_refacciones": descuento_refs,
        "comprobantes": [
            {
                "id": comp_inq.id,
                "tipo": "inquilino",
                "destinatario": nombre_inq,
                "email": inquilino.email if inquilino else None,
                "enviado_email": comp_inq.enviado_email,
                "error": comp_inq.error_envio,
            },
            {
                "id": comp_pro.id,
                "tipo": "propietario",
                "destinatario": nombre_pro,
                "email": propietario.email if propietario else None,
                "enviado_email": comp_pro.enviado_email,
                "error": comp_pro.error_envio,
            },
        ],
    }
