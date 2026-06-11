"""
Motor de match pedido ↔ propiedad (Fase 3, plan sección 8).

Reglas:
  - Hard rule: el tipo debe coincidir (si ambos están definidos). Si no, descarta.
  - Soft rules (suman score):
      precio dentro del rango con ±10% de tolerancia: +40
      dormitorios_propiedad >= dormitorios_pedido:     +20
      zona coincide (barrio_id o texto):                +25
      m² >= m² mínimo:                                  +10
      baños suficientes:                                +5
  - Threshold de notificación/almacenamiento: 60 (configurable).

Triggers:
  - Al crear/actualizar una propiedad → evaluar contra todos los pedidos activos.
  - Al crear/actualizar un pedido → evaluar contra todas las propiedades disponibles.

Persistencia: tabla ventas_matches, único por (pedido_id, propiedad_id). Si un
par deja de matchear (cae bajo el threshold), se elimina el match salvo que ya
haya sido marcado como mostrado.
"""
import json

from sqlalchemy.orm import Session

from app import models_ventas as mv

THRESHOLD = 60

ESTADOS_PEDIDO_ACTIVO = ("nuevo", "contactado", "en_seguimiento", "esperando_respuesta", "negociando")


def _val(x):
    return x.value if hasattr(x, "value") else x


def evaluar_match(pedido: mv.VentasPedido, prop: mv.VentasPropiedad):
    """Devuelve (score, razones) o (0, []) si no aplica la hard rule."""
    # Hard rule: tipo
    pt, rt = _val(pedido.tipo), _val(prop.tipo)
    if pt and rt and pt != rt:
        return 0, []

    score = 0
    razones = []

    # Precio: la propiedad no debe superar el máximo + 10% de tolerancia
    if prop.precio_usd and pedido.precio_max_usd:
        tope = pedido.precio_max_usd * 1.10
        piso = (pedido.precio_min_usd or 0) * 0.90
        if piso <= prop.precio_usd <= tope:
            score += 40
            razones.append({"motivo": "precio en rango", "puntos": 40})

    # Dormitorios
    if pedido.dormitorios_min and prop.dormitorios and prop.dormitorios >= pedido.dormitorios_min:
        score += 20
        razones.append({"motivo": f"{prop.dormitorios} dorm (≥{pedido.dormitorios_min})", "puntos": 20})

    # Zona: por barrio_id o por texto
    zona_ok = False
    if pedido.barrio_id and prop.barrio_id and pedido.barrio_id == prop.barrio_id:
        zona_ok = True
    elif pedido.zona and (prop.ciudad or prop.direccion):
        z = pedido.zona.lower()
        if z in (prop.ciudad or "").lower() or z in (prop.direccion or "").lower():
            zona_ok = True
    if zona_ok:
        score += 25
        razones.append({"motivo": "zona coincide", "puntos": 25})

    # Superficie mínima
    if pedido.superficie_min_m2 and prop.superficie_m2 and prop.superficie_m2 >= pedido.superficie_min_m2:
        score += 10
        razones.append({"motivo": f"{prop.superficie_m2} m² (≥{pedido.superficie_min_m2})", "puntos": 10})

    # Baños
    if pedido.banos_min and prop.banos and prop.banos >= pedido.banos_min:
        score += 5
        razones.append({"motivo": f"{prop.banos} baños", "puntos": 5})

    return score, razones


def _upsert_match(db, pedido, prop, score, razones):
    existente = (db.query(mv.VentasMatch)
                 .filter_by(pedido_id=pedido.id, propiedad_id=prop.id).first())
    if score >= THRESHOLD:
        if existente:
            # No reabrir un match descartado; solo actualizar score/razones.
            existente.score = score
            existente.razones_json = json.dumps(razones, ensure_ascii=False)
            return existente, False
        m = mv.VentasMatch(
            pedido_id=pedido.id, propiedad_id=prop.id, vendedor_id=pedido.vendedor_id,
            score=score, razones_json=json.dumps(razones, ensure_ascii=False),
            estado=mv.MatchEstado.pendiente, notificado=False,
        )
        db.add(m)
        return m, True
    else:
        # Ya no matchea: borrar salvo que esté mostrado (histórico útil).
        if existente and existente.estado != mv.MatchEstado.mostrado:
            db.delete(existente)
        return None, False


def evaluar_propiedad(db: Session, prop: mv.VentasPropiedad) -> int:
    """Evalúa una propiedad contra todos los pedidos activos. Devuelve nuevos."""
    nuevos = 0
    pedidos = (db.query(mv.VentasPedido)
               .filter(mv.VentasPedido.estado.in_(ESTADOS_PEDIDO_ACTIVO)).all())
    for ped in pedidos:
        score, razones = evaluar_match(ped, prop)
        _, creado = _upsert_match(db, ped, prop, score, razones)
        if creado:
            nuevos += 1
    db.flush()
    return nuevos


def evaluar_pedido(db: Session, pedido: mv.VentasPedido) -> int:
    """Evalúa un pedido contra todas las propiedades disponibles. Devuelve nuevos."""
    nuevos = 0
    props = (db.query(mv.VentasPropiedad)
             .filter(mv.VentasPropiedad.estado == mv.VPropiedadEstado.disponible).all())
    for prop in props:
        score, razones = evaluar_match(pedido, prop)
        _, creado = _upsert_match(db, pedido, prop, score, razones)
        if creado:
            nuevos += 1
    db.flush()
    return nuevos
