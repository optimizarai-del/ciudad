"""
Seed del sandbox DEMO (idempotente).

Crea todo lo necesario para que el login demo caiga en una plataforma poblada,
SIN tocar la data real:

  1. Usuario `admin_demo@ciudad.demo` / `demo1234` (role admin_demo).
  2. Datos demo de ALQUILERES (clientes, propiedades, contratos, pagos, leads)
     — reutiliza el fixture existente (routers/demo_fixture), todo con is_demo=True.
  3. Datos demo de VENTAS (vendedores, clientes con pipeline, propiedades,
     pedidos, operaciones y matches), todo con is_demo=True.

Aislamiento: el usuario admin_demo ve SOLO is_demo=True; los usuarios reales ven
SOLO is_demo=False (ver services/workspace.py y el filtro _demo del CRM de Ventas).

Se dispara en el arranque si DEMO_SEED_ENABLED=true (ver main.py). Es idempotente:
si el sandbox ya está sembrado, no duplica nada.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app import models, models_ventas as mv
from app.security import hash_pw


DEMO_EMAIL = "admin_demo@ciudad.demo"
DEMO_PASS = "demo1234"

# Orden de etapas activas para reconstruir un embudo realista con eventos.
_ETAPAS = [
    "nuevo_lead", "en_calificacion", "calificado_activo", "presentacion_opciones",
    "en_visitas", "oferta_negociacion", "reserva_sena", "escritura_cierre",
]


# ───────────────────────── usuario demo ─────────────────────────

def _asegurar_usuario_demo(db) -> models.User:
    u = db.query(models.User).filter_by(email=DEMO_EMAIL).first()
    if u:
        u.role = models.UserRole.admin_demo
        u.is_active = True
        u.password_hash = hash_pw(DEMO_PASS)
        return u
    u = models.User(
        nombre="Acceso Demo", email=DEMO_EMAIL,
        password_hash=hash_pw(DEMO_PASS),
        role=models.UserRole.admin_demo, is_active=True,
    )
    db.add(u); db.flush()
    return u


def _usuario_demo_extra(db, nombre: str, email: str) -> models.User:
    u = db.query(models.User).filter_by(email=email).first()
    if u:
        return u
    u = models.User(nombre=nombre, email=email, password_hash=hash_pw(DEMO_PASS),
                    role=models.UserRole.ventas, is_active=True)
    db.add(u); db.flush()
    return u


# ───────────────────────── alquileres demo ─────────────────────────

def _sembrar_alquileres(db, admin_user) -> bool:
    """Reutiliza el fixture existente. Devuelve True si sembró."""
    from app.routers import demo_fixture
    ya = db.query(models.Cliente).filter(
        models.Cliente.notas.ilike(f"%{demo_fixture.FIXTURE_TAG}%")).count()
    if ya > 0:
        return False
    # cargar() exige un user admin (bypass del Depends: le pasamos uno real).
    demo_fixture.cargar(db=db, user=admin_user)
    return True


# ───────────────────────── ventas demo ─────────────────────────

def _vendedor_demo(db, user, nombre, es_admin) -> mv.VentasVendedor:
    v = db.query(mv.VentasVendedor).filter_by(user_id=user.id).first()
    if v:
        v.is_demo = True
        return v
    v = mv.VentasVendedor(user_id=user.id, nombre=nombre, es_admin=es_admin,
                          is_demo=True, activo=True)
    db.add(v); db.flush()
    return v


def _cliente(db, vendedor, nombre, etapa, temp, perfil, presup_min, presup_max,
             zona, origen, es_operado=False):
    idx = _ETAPAS.index(etapa) if etapa in _ETAPAS else 0
    ahora = datetime.utcnow()
    c = mv.VentasCliente(
        is_demo=True, vendedor_id=vendedor.id, nombre=nombre,
        telefono="+54 2954 " + str(400000 + abs(hash(nombre)) % 99999),
        email=nombre.lower().replace(" ", ".") + ".demo@ciudad.demo",
        origen=origen, etapa=etapa, temperatura=temp,
        perfil_comprador=perfil, tipo_operacion="venta_propia",
        presupuesto_min_usd=presup_min, presupuesto_max_usd=presup_max,
        zona_interes=zona, es_operado=es_operado,
        etapa_desde=ahora - timedelta(days=idx * 4 + 2),
        ultimo_contacto_at=ahora - timedelta(days=1),
        proxima_accion_tipo="llamada",
        proxima_accion_fecha=ahora + timedelta(days=2),
        proxima_accion_contexto="Seguimiento demo",
    )
    db.add(c); db.flush()
    # Eventos de etapa (embudo): camina de nuevo_lead hasta la etapa actual.
    base = ahora - timedelta(days=idx * 4 + 4)
    prev = None
    for i in range(idx + 1):
        db.add(mv.VentasClienteEvento(
            cliente_id=c.id, vendedor_id=vendedor.id, tipo="etapa",
            de=prev, a=_ETAPAS[i], detalle="Avance demo", automatico=False,
            created_at=base + timedelta(days=i * 3)))
        prev = _ETAPAS[i]
    return c


def _propiedad(db, vendedor, titulo, tipo, precio, dorm, banos, sup, ciudad,
               lat, lng, estado="disponible"):
    p = mv.VentasPropiedad(
        is_demo=True, cargada_por=vendedor.id, titulo=titulo,
        tipo=mv.VPropiedadTipo(tipo), estado=mv.VPropiedadEstado(estado),
        fuente=mv.VPropiedadFuente.propia, direccion=titulo, ciudad=ciudad,
        lat=lat, lng=lng, precio_usd=precio, superficie_m2=sup,
        dormitorios=dorm, banos=banos,
        descripcion="Propiedad de demostración en " + ciudad,
    )
    db.add(p); db.flush()
    return p


def _pedido(db, vendedor, cliente, tipo, precio_max, zona, dorm_min):
    ped = mv.VentasPedido(
        is_demo=True, cliente_id=cliente.id, vendedor_id=vendedor.id,
        estado=mv.PedidoEstado.en_seguimiento, prioridad=mv.PedidoPrioridad.alta,
        tipo=mv.VPropiedadTipo(tipo), zona=zona, precio_max_usd=precio_max,
        dormitorios_min=dorm_min, detalle="Búsqueda demo",
    )
    db.add(ped); db.flush()
    return ped


def _sembrar_ventas(db, admin_demo_user) -> bool:
    """Devuelve True si sembró data de ventas demo."""
    ya = db.query(mv.VentasVendedor).filter_by(is_demo=True).count()
    if ya > 0:
        return False

    # Vendedores demo (el admin_demo + dos comerciales para el ranking).
    v_lider = _vendedor_demo(db, admin_demo_user, "Equipo Demo", es_admin=True)
    u_ana = _usuario_demo_extra(db, "Ana Vendedora", "ana.demo@ciudad.demo")
    u_bruno = _usuario_demo_extra(db, "Bruno Vendedor", "bruno.demo@ciudad.demo")
    v_ana = _vendedor_demo(db, u_ana, "Ana Vendedora", es_admin=False)
    v_bruno = _vendedor_demo(db, u_bruno, "Bruno Vendedor", es_admin=False)

    # Santa Rosa (La Pampa) como zona base del demo.
    SR = "Santa Rosa"
    LAT, LNG = -36.6167, -64.2833

    # Clientes con pipeline variado (alimenta embudo, temperatura, riesgo, valor).
    clientes = [
        _cliente(db, v_ana, "Laura Giménez", "escritura_cierre", "caliente",
                 "contado", 90000, 130000, SR, "instagram", es_operado=True),
        _cliente(db, v_ana, "Marcos Ferreyra", "oferta_negociacion", "caliente",
                 "credito", 70000, 95000, SR, "whatsapp"),
        _cliente(db, v_bruno, "Sofía Aguirre", "en_visitas", "tibio",
                 "inversor", 110000, 160000, SR, "web"),
        _cliente(db, v_bruno, "Diego Rossi", "presentacion_opciones", "tibio",
                 "contado", 60000, 85000, "Toay", "referido"),
        _cliente(db, v_ana, "Carla Núñez", "calificado_activo", "caliente",
                 "credito", 80000, 100000, SR, "instagram"),
        _cliente(db, v_bruno, "Tomás Vera", "en_calificacion", "tibio",
                 "oportunista", 50000, 70000, SR, "whatsapp"),
        _cliente(db, v_ana, "Julieta Paz", "nuevo_lead", "tibio",
                 None, None, None, SR, "web"),
        _cliente(db, v_bruno, "Ramiro Sosa", "frio_espera", "frio",
                 "espera_vender", 40000, 60000, SR, "referido"),
    ]

    # Propiedades demo.
    props = [
        _propiedad(db, v_lider, "Casa 3 dorm B° Fitte", "casa", 128000, 3, 2, 140, SR, LAT, LNG),
        _propiedad(db, v_lider, "Departamento centro 2 amb", "departamento", 74000, 1, 1, 55, SR, LAT + 0.01, LNG - 0.01),
        _propiedad(db, v_lider, "Lote 300m² Zona Norte", "lote", 42000, None, None, 300, SR, LAT + 0.02, LNG + 0.01),
        _propiedad(db, v_lider, "Casa 2 dorm Toay", "casa", 82000, 2, 1, 95, "Toay", LAT - 0.05, LNG - 0.06),
        _propiedad(db, v_lider, "Local comercial San Martín", "local", 155000, None, 1, 120, SR, LAT + 0.005, LNG),
        _propiedad(db, v_lider, "Casa 4 dorm B° España", "casa", 165000, 4, 3, 210, SR, LAT - 0.01, LNG + 0.02),
    ]

    # Pedidos (búsquedas activas) → generan matches contra las propiedades demo.
    from app.services import ventas_matching
    peds = [
        _pedido(db, v_ana, clientes[1], "casa", 95000, SR, 2),
        _pedido(db, v_bruno, clientes[2], "casa", 160000, SR, 3),
        _pedido(db, v_bruno, clientes[3], "casa", 85000, "Toay", 2),
        _pedido(db, v_ana, clientes[4], "departamento", 100000, SR, 1),
    ]
    for ped in peds:
        try:
            ventas_matching.evaluar_pedido(db, ped)
        except Exception as e:
            print(f"[seed_demo] matching demo fallback: {e}")

    # Operaciones: una cerrada (con comisión) y una con seña.
    hoy = date.today()
    db.add(mv.VentasOperacion(
        is_demo=True, propiedad_id=props[3].id, cliente_id=clientes[0].id,
        vendedor_id=v_ana.id, estado=mv.OperacionEstado.cerrada,
        monto_cierre_usd=82000, fecha_cierre=hoy - timedelta(days=12),
        comision_pct=3.0, comision_monto_usd=2460.0))
    db.add(mv.VentasOperacion(
        is_demo=True, propiedad_id=props[0].id, cliente_id=clientes[1].id,
        vendedor_id=v_ana.id, estado=mv.OperacionEstado.sena,
        monto_cierre_usd=128000, comision_pct=3.0, comision_monto_usd=3840.0))

    return True


# ───────────────────────── entrypoint ─────────────────────────

def sembrar_demo() -> dict:
    """Crea/asegura el sandbox demo. Idempotente. Crea su propia sesión."""
    from app.database import SessionLocal
    db = SessionLocal()
    resumen = {"usuario_demo": DEMO_EMAIL, "alquileres": False, "ventas": False}
    try:
        # 1) usuario demo
        _asegurar_usuario_demo(db)
        db.commit()

        # 2) alquileres (necesita un admin real para el fixture)
        admin = db.query(models.User).filter_by(role=models.UserRole.admin).first()
        if admin:
            try:
                resumen["alquileres"] = _sembrar_alquileres(db, admin)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[seed_demo] alquileres fallback: {e}")

        # 3) ventas
        try:
            admin_demo = db.query(models.User).filter_by(email=DEMO_EMAIL).first()
            resumen["ventas"] = _sembrar_ventas(db, admin_demo)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[seed_demo] ventas fallback: {e}")

        print(f"[seed_demo] {resumen}")
        return resumen
    finally:
        db.close()
