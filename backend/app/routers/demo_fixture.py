"""
Datos ficticios para probar la plataforma de punta a punta.

  POST   /api/admin/demo/cargar    crea propietarios, inquilinos, propiedades
                                   de varios tipos, contratos en distintos
                                   estados, pagos, leads y eventos.
  DELETE /api/admin/demo/limpiar   borra todo lo creado por /cargar
                                   (identificado por el marker FIXTURE_TAG).
  GET    /api/admin/demo/estado    cuenta cuántas filas ficticias hay.

Sólo admin. No toca los 4 usuarios reales del sistema.

Las entidades se marcan en su campo `notas` o `descripcion` con el string
`FIXTURE_TAG`. Para limpiar simplemente buscamos por ese marker y borramos
en orden de FK (pagos -> contratos -> propiedades -> clientes -> leads).
"""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.security import get_current_user
from app import models


router = APIRouter(prefix="/api/admin/demo", tags=["admin"])

FIXTURE_TAG = "[DEMO-FIXTURE]"


def _require_admin(user):
    if user.role != models.UserRole.admin:
        raise HTTPException(403, "Solo admin")


def _q_propiedades_demo(db: Session):
    return db.query(models.Propiedad).filter(
        models.Propiedad.descripcion.ilike(f"%{FIXTURE_TAG}%")
    )


def _q_clientes_demo(db: Session):
    return db.query(models.Cliente).filter(
        models.Cliente.notas.ilike(f"%{FIXTURE_TAG}%")
    )


def _q_contratos_demo(db: Session):
    return db.query(models.Contrato).filter(
        models.Contrato.notas.ilike(f"%{FIXTURE_TAG}%")
    )


@router.get("/estado")
def estado(db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_admin(user)
    return {
        "tag": FIXTURE_TAG,
        "clientes_demo": _q_clientes_demo(db).count(),
        "propiedades_demo": _q_propiedades_demo(db).count(),
        "contratos_demo": _q_contratos_demo(db).count(),
        "pagos_demo": (
            db.query(models.Pago)
              .join(models.Contrato, models.Pago.contrato_id == models.Contrato.id)
              .filter(models.Contrato.notas.ilike(f"%{FIXTURE_TAG}%"))
              .count()
        ),
    }


@router.delete("/limpiar")
def limpiar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_admin(user)

    contratos = _q_contratos_demo(db).all()
    contrato_ids = [c.id for c in contratos]

    pagos_borrados = 0
    if contrato_ids:
        pagos_borrados = (
            db.query(models.Pago)
              .filter(models.Pago.contrato_id.in_(contrato_ids))
              .delete(synchronize_session=False)
        )
        # AjusteContrato también cae al borrar el contrato (cascade en el modelo),
        # pero borramos manualmente por las dudas.
        db.query(models.AjusteContrato).filter(
            models.AjusteContrato.contrato_id.in_(contrato_ids)
        ).delete(synchronize_session=False)

    # Refacciones del fixture — las identificamos por el contrato_id
    # (todas las que apuntan a contratos demo) o por la propiedad_id.
    refacciones_borradas = 0
    if contrato_ids:
        refacciones_borradas = (
            db.query(models.Refaccion)
            .filter(models.Refaccion.contrato_id.in_(contrato_ids))
            .delete(synchronize_session=False)
        )

    contratos_borrados = _q_contratos_demo(db).delete(synchronize_session=False)

    # Adjuntos de propiedades demo (legacy; los nuevos viven en Storage y
    # quedan huérfanos — se podrían limpiar con un job aparte).
    props = _q_propiedades_demo(db).all()
    prop_ids = [p.id for p in props]
    if prop_ids:
        db.query(models.PropiedadAdjunto).filter(
            models.PropiedadAdjunto.propiedad_id.in_(prop_ids)
        ).delete(synchronize_session=False)

    propiedades_borradas = _q_propiedades_demo(db).delete(synchronize_session=False)
    clientes_borrados = _q_clientes_demo(db).delete(synchronize_session=False)

    db.commit()
    return {
        "ok": True,
        "pagos_borrados": pagos_borrados,
        "contratos_borrados": contratos_borrados,
        "propiedades_borradas": propiedades_borradas,
        "clientes_borrados": clientes_borrados,
    }


@router.post("/cargar")
def cargar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Crea un dataset realista para probar la plataforma.

    Si ya existe data demo previa, primero se limpia (idempotente)."""
    _require_admin(user)

    # Idempotencia: si ya hay fixture cargado, limpiar y rehacer.
    if _q_clientes_demo(db).count() > 0 or _q_propiedades_demo(db).count() > 0:
        limpiar(db=db, user=user)

    hoy = date.today()

    # ─── PROPIETARIOS ──────────────────────────────────────────────────────
    propietarios = [
        models.Cliente(
            nombre="Carlos", apellido="Mendoza",
            documento="20-12345678-3", email="carlos.mendoza.demo@ciudad.com",
            telefono="+54 9 11 4500-1001",
            rol=models.ClienteRol.propietario,
            notas=f"{FIXTURE_TAG} 2 propiedades en alquiler",
        ),
        models.Cliente(
            nombre="Lucía", apellido="Fernández",
            documento="27-23456789-4", email="lucia.fernandez.demo@ciudad.com",
            telefono="+54 9 11 4500-1002",
            rol=models.ClienteRol.propietario,
            notas=f"{FIXTURE_TAG} Galpón comercial",
        ),
        models.Cliente(
            nombre="Inversiones Pampa", apellido="SRL",
            razon_social="Inversiones Pampa SRL",
            documento="30-71456789-5", email="contacto.pampa.demo@ciudad.com",
            telefono="+54 9 11 4500-1003",
            rol=models.ClienteRol.propietario,
            notas=f"{FIXTURE_TAG} Persona jurídica",
        ),
    ]
    for c in propietarios:
        db.add(c)
    db.flush()  # obtener IDs

    # ─── INQUILINOS ────────────────────────────────────────────────────────
    inquilinos = [
        models.Cliente(
            nombre="Martina", apellido="López",
            documento="35-87654321-2", email="martina.lopez.demo@ciudad.com",
            telefono="+54 9 11 4500-2001",
            rol=models.ClienteRol.inquilino,
            notas=f"{FIXTURE_TAG} Inquilina activa",
        ),
        models.Cliente(
            nombre="Federico", apellido="Gómez",
            documento="33-76543210-1", email="federico.gomez.demo@ciudad.com",
            telefono="+54 9 11 4500-2002",
            rol=models.ClienteRol.inquilino,
            notas=f"{FIXTURE_TAG} Contrato vencido",
        ),
        models.Cliente(
            nombre="Sofía", apellido="Ríos",
            documento="38-65432109-0", email="sofia.rios.demo@ciudad.com",
            telefono="+54 9 11 4500-2003",
            rol=models.ClienteRol.inquilino,
            notas=f"{FIXTURE_TAG} Borrador firmado pendiente",
        ),
        models.Cliente(
            nombre="Estudio Notarial", apellido="Ríos & Asoc.",
            razon_social="Estudio Notarial Ríos & Asoc.",
            documento="30-71987654-2", email="estudio.rios.demo@ciudad.com",
            telefono="+54 9 11 4500-2004",
            rol=models.ClienteRol.inquilino,
            notas=f"{FIXTURE_TAG} Inquilino comercial",
        ),
    ]
    for c in inquilinos:
        db.add(c)
    db.flush()

    p_carlos, p_lucia, p_pampa = propietarios
    i_martina, i_fede, i_sofia, i_estudio = inquilinos

    # ─── PROPIEDADES (cubrimos los 6 tipos) ────────────────────────────────
    propiedades = [
        models.Propiedad(
            direccion="Av. Santa Fe 2450, 4°B",
            ciudad="CABA", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.departamento,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.ocupada,
            superficie_m2=65, ambientes=3,
            precio_alquiler=350_000, expensas=85_000, tasa_municipal=18_000,
            propietario_id=p_carlos.id,
            descripcion=f"{FIXTURE_TAG} Departamento 3 amb. luminoso, balcón a la calle.",
        ),
        models.Propiedad(
            direccion="Juncal 1850",
            ciudad="CABA", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.casa,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=180, ambientes=5,
            precio_alquiler=620_000, expensas=0, tasa_municipal=35_000,
            propietario_id=p_carlos.id,
            descripcion=f"{FIXTURE_TAG} Casa 5 ambientes con jardín y pileta.",
        ),
        models.Propiedad(
            direccion="Av. Corrientes 3500 PB",
            ciudad="CABA", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.local,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.ocupada,
            superficie_m2=120, ambientes=2,
            precio_alquiler=480_000, expensas=22_000, tasa_municipal=28_000,
            propietario_id=p_pampa.id,
            descripcion=f"{FIXTURE_TAG} Local comercial sobre avenida, alto tránsito.",
        ),
        models.Propiedad(
            direccion="Viamonte 1200 — Piso 6",
            ciudad="CABA", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.oficina,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=95, ambientes=4,
            precio_alquiler=540_000, expensas=120_000, tasa_municipal=25_000,
            propietario_id=p_pampa.id,
            descripcion=f"{FIXTURE_TAG} Oficina en microcentro, 4 despachos + recepción.",
        ),
        models.Propiedad(
            direccion="Camino General Belgrano km 12",
            ciudad="Florencio Varela", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.galpon,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.reservada,
            superficie_m2=850, ambientes=0,
            precio_alquiler=950_000, expensas=0, tasa_municipal=42_000,
            propietario_id=p_lucia.id,
            descripcion=f"{FIXTURE_TAG} Galpón industrial, altura 8m, portón camionero.",
        ),
        models.Propiedad(
            direccion="Ruta 8 km 78 — Lote 4",
            ciudad="Pilar", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.campo,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=50_000, ambientes=0,
            precio_alquiler=180_000, expensas=0, tasa_municipal=15_000,
            propietario_id=p_pampa.id,
            descripcion=f"{FIXTURE_TAG} 5 ha sembradas, alambrado perimetral.",
        ),
    ]
    for p in propiedades:
        db.add(p)
    db.flush()

    pr_depto, pr_casa, pr_local, pr_oficina, pr_galpon, pr_campo = propiedades

    # ─── CONTRATOS ─────────────────────────────────────────────────────────
    contratos = [
        # 1. Vigente, alquiler vivienda — Martina en el depto de Carlos
        models.Contrato(
            tipo=models.ContratoTipo.alquiler_vivienda,
            estado=models.ContratoEstado.vigente,
            propiedad_id=pr_depto.id,
            inquilino_id=i_martina.id,
            fecha_inicio=hoy - timedelta(days=180),
            fecha_fin=hoy + timedelta(days=550),
            monto_inicial=350_000,
            deposito=350_000,
            indice_ajuste=models.IndiceAjuste.ipc,
            periodicidad_meses=6,
            comision_porc=4.0,
            notas=f"{FIXTURE_TAG} Contrato vigente — 6 meses de antigüedad.",
        ),
        # 2. Vencido, alquiler vivienda — Federico en casa de Carlos
        models.Contrato(
            tipo=models.ContratoTipo.alquiler_vivienda,
            estado=models.ContratoEstado.vencido,
            propiedad_id=pr_casa.id,
            inquilino_id=i_fede.id,
            fecha_inicio=hoy - timedelta(days=820),
            fecha_fin=hoy - timedelta(days=90),
            monto_inicial=500_000,
            deposito=500_000,
            indice_ajuste=models.IndiceAjuste.icl,
            periodicidad_meses=3,
            comision_porc=5.0,
            notas=f"{FIXTURE_TAG} Venció hace 3 meses — pendiente renovación.",
        ),
        # 3. Vigente, alquiler comercial — Estudio en local av. Corrientes
        models.Contrato(
            tipo=models.ContratoTipo.alquiler_comercial,
            estado=models.ContratoEstado.vigente,
            propiedad_id=pr_local.id,
            inquilino_id=i_estudio.id,
            fecha_inicio=hoy - timedelta(days=300),
            fecha_fin=hoy + timedelta(days=730),
            monto_inicial=480_000,
            deposito=960_000,
            indice_ajuste=models.IndiceAjuste.ipc,
            periodicidad_meses=4,
            comision_porc=6.0,
            notas=f"{FIXTURE_TAG} Contrato comercial 3 años.",
        ),
        # 4. Borrador, alquiler oficina — Sofía Ríos
        models.Contrato(
            tipo=models.ContratoTipo.alquiler_comercial,
            estado=models.ContratoEstado.borrador,
            propiedad_id=pr_oficina.id,
            inquilino_id=i_sofia.id,
            fecha_inicio=hoy + timedelta(days=15),
            fecha_fin=hoy + timedelta(days=15 + 730),
            monto_inicial=540_000,
            deposito=1_080_000,
            indice_ajuste=models.IndiceAjuste.ipc,
            periodicidad_meses=4,
            comision_porc=6.0,
            notas=f"{FIXTURE_TAG} Pendiente firma — borrador para revisar.",
        ),
        # 5. Boleto de compraventa
        models.Contrato(
            tipo=models.ContratoTipo.boleto_compraventa,
            estado=models.ContratoEstado.borrador,
            propiedad_id=pr_galpon.id,
            inquilino_id=i_estudio.id,  # comprador
            fecha_inicio=hoy + timedelta(days=30),
            fecha_fin=hoy + timedelta(days=30),
            monto_inicial=250_000_000,
            deposito=25_000_000,  # seña
            indice_ajuste=models.IndiceAjuste.sin_ajuste,
            periodicidad_meses=12,
            comision_porc=3.0,
            notas=f"{FIXTURE_TAG} Boleto C/V galpón — seña abonada.",
        ),
    ]
    for k in contratos:
        db.add(k)
    db.flush()

    c_martina, c_fede, c_estudio, c_sofia, c_boleto = contratos

    # ─── PAGOS ─────────────────────────────────────────────────────────────
    # Contrato vigente de Martina: 6 meses de pagos
    for mes in range(6, 0, -1):
        fecha = hoy - timedelta(days=mes * 30)
        periodo = f"{fecha.year}-{fecha.month:02d}"
        cobrado = mes != 1  # último mes pendiente
        estado_pago = models.PagoEstado.pagado if cobrado else models.PagoEstado.pendiente
        db.add(models.Pago(
            contrato_id=c_martina.id,
            periodo=periodo,
            fecha_vencimiento=fecha,
            fecha_pago=fecha if cobrado else None,
            monto_alquiler=350_000,
            monto_expensas=85_000,
            monto_impuestos=0,
            monto_municipal=18_000,
            monto_total=453_000,
            estado=estado_pago,
            notas=f"{FIXTURE_TAG}",
        ))

    # Contrato del Estudio: 10 meses, todos cobrados salvo el último
    for mes in range(10, 0, -1):
        fecha = hoy - timedelta(days=mes * 30)
        periodo = f"{fecha.year}-{fecha.month:02d}"
        cobrado = mes != 1
        estado_pago = models.PagoEstado.pagado if cobrado else models.PagoEstado.pendiente
        db.add(models.Pago(
            contrato_id=c_estudio.id,
            periodo=periodo,
            fecha_vencimiento=fecha,
            fecha_pago=fecha if cobrado else None,
            monto_alquiler=480_000,
            monto_expensas=22_000,
            monto_impuestos=0,
            monto_municipal=28_000,
            monto_total=530_000,
            estado=estado_pago,
            notas=f"{FIXTURE_TAG}",
        ))

    # Pagos del contrato de Fede (vencido) — 3 últimos en atraso
    for mes in range(15, 12, -1):
        fecha = hoy - timedelta(days=mes * 30)
        periodo = f"{fecha.year}-{fecha.month:02d}"
        db.add(models.Pago(
            contrato_id=c_fede.id,
            periodo=periodo,
            fecha_vencimiento=fecha,
            fecha_pago=None,
            monto_alquiler=500_000,
            monto_expensas=0,
            monto_impuestos=0,
            monto_municipal=35_000,
            monto_total=535_000,
            estado=models.PagoEstado.vencido,
            notas=f"{FIXTURE_TAG} En mora",
        ))

    # ─── REFACCIONES ───────────────────────────────────────────────────────
    # Mezcla realista: algunas que paga el inquilino (se descontarán del próximo
    # cobro) y otras que paga el propietario (van a liquidación).
    refacciones = [
        models.Refaccion(
            propiedad_id=pr_depto.id,
            contrato_id=c_martina.id,
            fecha=hoy - timedelta(days=10),
            descripcion="Reparación termotanque",
            monto=85_000,
            pagador=models.RefaccionPagador.inquilino,
            estado=models.RefaccionEstado.pendiente,
            notas=f"{FIXTURE_TAG} El inquilino llamó al técnico y pagó cash. Se descuenta del próximo alquiler.",
        ),
        models.Refaccion(
            propiedad_id=pr_depto.id,
            contrato_id=c_martina.id,
            fecha=hoy - timedelta(days=22),
            descripcion="Cambio de cerradura puerta principal",
            monto=42_000,
            pagador=models.RefaccionPagador.inquilino,
            estado=models.RefaccionEstado.pendiente,
            notas=f"{FIXTURE_TAG} Cerrajero llamado por urgencia.",
        ),
        models.Refaccion(
            propiedad_id=pr_local.id,
            contrato_id=c_estudio.id,
            fecha=hoy - timedelta(days=15),
            descripcion="Pintura completa fachada",
            monto=320_000,
            pagador=models.RefaccionPagador.propietario,
            estado=models.RefaccionEstado.pendiente,
            notas=f"{FIXTURE_TAG} Acordado con el propietario — sale de la liquidación.",
        ),
        models.Refaccion(
            propiedad_id=pr_casa.id,
            contrato_id=None,
            fecha=hoy - timedelta(days=45),
            descripcion="Reparación cañería baño principal",
            monto=180_000,
            pagador=models.RefaccionPagador.propietario,
            estado=models.RefaccionEstado.aplicada,
            notas=f"{FIXTURE_TAG} Ya facturado en liquidación de marzo.",
        ),
        models.Refaccion(
            propiedad_id=pr_oficina.id,
            contrato_id=None,
            fecha=hoy - timedelta(days=5),
            descripcion="Reparación aire acondicionado",
            monto=65_000,
            pagador=models.RefaccionPagador.propietario,
            estado=models.RefaccionEstado.pendiente,
            notas=f"{FIXTURE_TAG} Pre-firma, lo descuenta del depósito.",
        ),
    ]
    for r in refacciones:
        db.add(r)

    db.commit()

    return {
        "ok": True,
        "creado": {
            "propietarios": len(propietarios),
            "inquilinos": len(inquilinos),
            "propiedades": len(propiedades),
            "contratos": len(contratos),
            "pagos": 6 + 10 + 3,
            "refacciones": len(refacciones),
        },
        "tag": FIXTURE_TAG,
        "como_limpiar": "DELETE /api/admin/demo/limpiar",
    }
