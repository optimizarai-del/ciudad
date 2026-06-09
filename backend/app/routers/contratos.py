from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services.pdf_service import generar_pdf_contrato
from app.services.contrato_docx import generar_docx
from app.services import supabase_storage
from app.services.workspace import apply_workspace_filter, workspace_flag
from app.services import contrato_import
from app.services import historial

router = APIRouter(prefix="/api/contratos", tags=["contratos"])


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _scope(db: Session, user):
    return apply_workspace_filter(db.query(models.Contrato), models.Contrato, user)


def _generar_codigo(db: Session, is_demo: bool) -> str:
    """Genera un código único para el contrato con formato CONT-YYYY-NNNN.

    La numeración es por año y por workspace (real vs demo). Si por algún
    motivo el código candidato ya existe (colisión por race condition o
    importación manual), recorre hasta encontrar uno libre.
    """
    year = datetime.utcnow().year
    prefix = f"CONT-{year}-"
    base = db.query(models.Contrato).filter(
        models.Contrato.is_demo == is_demo,
        models.Contrato.codigo.like(f"{prefix}%"),
    ).count()
    # Probamos secuencialmente desde base+1; en el peor caso recorremos un
    # rango razonable, luego caemos a un fallback con timestamp.
    for i in range(base + 1, base + 1000):
        candidato = f"{prefix}{i:04d}"
        existe = db.query(models.Contrato).filter_by(codigo=candidato).first()
        if not existe:
            return candidato
    return f"{prefix}{int(datetime.utcnow().timestamp())}"


@router.get("/", response_model=List[schemas.ContratoOut])
def listar(
    incluir_archivados: bool = False,
    propietario_id: Optional[int] = None,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Eager-load defensivo de inquilinos. Si la tabla pivote aún no existe
    # en este deploy, el selectinload puede tirar error — lo capturamos y
    # caemos al query sin options así no rompe el listar de contratos.
    from sqlalchemy.orm import selectinload, joinedload
    q = _scope(db, user)
    try:
        q = q.options(
            selectinload(models.Contrato.inquilinos)
                .joinedload(models.ContratoInquilino.cliente),
            selectinload(models.Contrato.garantes),
        )
    except Exception as e:
        print(f"[contratos.listar] selectinload inquilinos/garantes falló (fallback sin eager): {e}")

    if not incluir_archivados:
        q = q.filter(models.Contrato.archivado.is_(False))
    if propietario_id:
        # Contratos donde la propiedad pertenece al propietario (legacy o M2M)
        prop_ids = {
            p.id for p in db.query(models.Propiedad).filter_by(propietario_id=propietario_id).all()
        }
        m2m_ids = {
            row.propiedad_id for row in
            db.query(models.PropiedadPropietario).filter_by(cliente_id=propietario_id).all()
        }
        prop_ids |= m2m_ids
        if prop_ids:
            q = q.filter(models.Contrato.propiedad_id.in_(prop_ids))
        else:
            return []
    q = q.order_by(models.Contrato.id.desc())
    if limit:
        q = q.limit(limit)
    return q.all()


def _sync_inquilinos(db: Session, contrato: models.Contrato,
                     inquilinos_data: list[dict], is_demo: bool) -> None:
    """Sincroniza las filas pivote `contrato_inquilinos` del contrato a partir
    de la lista que mandó el frontend. Cada item puede:
      - Apuntar a un cliente existente con `cliente_id`
      - Crear uno nuevo con nombre/documento/etc.
      - Si manda `documento` y existe un cliente con ese documento en el
        mismo workspace, lo reutiliza (evita duplicados).

    El primer item marcado como `es_principal=True` (o el primero de la
    lista si nadie lo está) se setea también como `contrato.inquilino_id`
    para mantener compatibilidad con código legacy.

    Borra todas las filas previas del contrato y las recrea — pensado para
    POST (crear) y PATCH (editar) por igual.
    """
    # Limpiar filas previas si es un edit. Defensivo: si la tabla pivote
    # aún no existe (deploy a medio aplicar la migración), seguir adelante.
    # Usamos SAVEPOINT para que un fallo acá no rompa la transacción padre.
    try:
        with db.begin_nested():
            for ci in list(contrato.inquilinos or []):
                db.delete(ci)
    except Exception as e:
        print(f"[_sync_inquilinos] limpiar previos falló (savepoint revertido): {e}")

    if not inquilinos_data:
        contrato.inquilino_id = None
        return

    principal_cli_id: Optional[int] = None

    for idx, item in enumerate(inquilinos_data):
        cli = None
        cli_id = item.get("cliente_id")

        if cli_id:
            cli = db.query(models.Cliente).filter_by(id=cli_id).first()
            if not cli:
                raise HTTPException(404, f"El inquilino #{cli_id} no existe.")
            if bool(cli.is_demo) != is_demo:
                raise HTTPException(403, f"El inquilino #{cli_id} no pertenece a tu workspace.")
        else:
            # Buscar por documento para evitar duplicados
            doc = (item.get("documento") or "").strip()
            if doc:
                cli = (
                    db.query(models.Cliente)
                    .filter(models.Cliente.is_demo == is_demo,
                            models.Cliente.documento == doc)
                    .first()
                )

            if cli is None:
                # Crear nuevo Cliente
                nombre = (item.get("nombre") or item.get("razon_social") or "").strip()
                if not nombre:
                    raise HTTPException(400, f"Inquilino #{idx + 1}: falta nombre o razón social.")
                cli = models.Cliente(
                    nombre=nombre,
                    apellido=item.get("apellido") or None,
                    razon_social=item.get("razon_social") or None,
                    documento=doc or None,
                    tipo_documento=item.get("tipo_documento") or None,
                    nacionalidad=item.get("nacionalidad") or None,
                    email=item.get("email") or None,
                    telefono=item.get("telefono") or None,
                    rol=models.ClienteRol.inquilino,
                    notas=item.get("notas") or None,
                    is_demo=is_demo,
                )
                db.add(cli); db.flush()

        es_principal = bool(item.get("es_principal")) or (idx == 0 and principal_cli_id is None)
        if es_principal:
            principal_cli_id = cli.id

        db.add(models.ContratoInquilino(
            contrato_id=contrato.id,
            cliente_id=cli.id,
            es_principal=es_principal,
            rol=item.get("rol"),
            notas=item.get("notas"),
        ))

    # Setear inquilino_id legacy al principal (o al primero si ninguno fue marcado)
    contrato.inquilino_id = principal_cli_id
    db.flush()


def _sync_garantes(db: Session, contrato: models.Contrato,
                   garantes_data: list[dict], is_demo: bool) -> None:
    """Sincroniza las filas `garantes` del contrato a partir de la lista que
    mandó el frontend. Los garantes se guardan inline (no son Clientes) y
    pertenecen a este contrato.

    Borra todas las filas previas del contrato y las recrea — pensado para
    POST (crear) y PATCH (editar) por igual. Usa SAVEPOINT para que un fallo
    (ej: tabla `garantes` aún no migrada) no rompa la transacción padre.
    """
    try:
        with db.begin_nested():
            for g in list(contrato.garantes or []):
                db.delete(g)
    except Exception as e:
        print(f"[_sync_garantes] limpiar previos falló (savepoint revertido): {e}")

    if not garantes_data:
        return

    for idx, item in enumerate(garantes_data):
        nombre = (item.get("nombre") or item.get("razon_social") or "").strip()
        if not nombre:
            raise HTTPException(400, f"Garante #{idx + 1}: falta nombre o razón social.")
        db.add(models.Garante(
            contrato_id=contrato.id,
            nombre=nombre,
            apellido=item.get("apellido") or None,
            razon_social=item.get("razon_social") or None,
            documento=item.get("documento") or None,
            tipo_documento=item.get("tipo_documento") or None,
            nacionalidad=item.get("nacionalidad") or None,
            domicilio=item.get("domicilio") or None,
            telefono=item.get("telefono") or None,
            email=item.get("email") or None,
            notas=item.get("notas") or None,
            is_demo=is_demo,
        ))
    db.flush()


@router.post("/", response_model=schemas.ContratoOut)
def crear(data: schemas.ContratoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Mensajes de error claros para los validaciones más comunes en vez de
    # un 500 genérico que aparezca como toast rojo sin información.
    payload = data.model_dump()
    inquilinos_data = payload.pop("inquilinos", None)
    garantes_data = payload.pop("garantes", None)

    # Validar propiedad
    if not payload.get("propiedad_id"):
        raise HTTPException(400, "Falta seleccionar una propiedad para el contrato.")
    prop = db.query(models.Propiedad).filter_by(id=payload["propiedad_id"]).first()
    if not prop:
        raise HTTPException(404, f"La propiedad #{payload['propiedad_id']} no existe.")

    # Validar inquilino_id legacy (si se mandó single y no la lista nueva)
    if not inquilinos_data and payload.get("inquilino_id"):
        cli = db.query(models.Cliente).filter_by(id=payload["inquilino_id"]).first()
        if not cli:
            raise HTTPException(404, f"El inquilino #{payload['inquilino_id']} no existe.")

    # Validar enums explícitamente — en Postgres con SQLEnum un valor inválido
    # tira un IntegrityError críptico al hacer commit.
    enum_checks = {
        "tipo": (models.ContratoTipo, payload.get("tipo")),
        "estado": (models.ContratoEstado, payload.get("estado") or "borrador"),
        "indice_ajuste": (models.IndiceAjuste, payload.get("indice_ajuste") or "ipc"),
    }
    for campo, (cls, val) in enum_checks.items():
        if val is None:
            continue
        try:
            cls(val)
        except ValueError:
            opciones = ", ".join(e.value for e in cls)
            raise HTTPException(400, f"Valor inválido para {campo}: '{val}'. Opciones: {opciones}")

    # La propiedad seleccionada debe estar en el mismo workspace que el usuario
    if bool(prop.is_demo) != workspace_flag(user):
        raise HTTPException(403, "La propiedad no pertenece a tu workspace.")

    is_demo = workspace_flag(user)

    # Autogenerar el código si vino vacío.
    codigo = (payload.get("codigo") or "").strip()
    if not codigo:
        codigo = _generar_codigo(db, is_demo)
    else:
        if db.query(models.Contrato).filter_by(codigo=codigo).first():
            raise HTTPException(409, f"Ya existe un contrato con el código '{codigo}'.")
    payload["codigo"] = codigo

    # Sacar listas de solo-lectura (no son columnas del modelo)
    payload.pop("inquilinos_lista", None)
    payload.pop("garantes_lista", None)

    try:
        obj = models.Contrato(**payload)
        obj.is_demo = is_demo
        db.add(obj); db.flush()  # flush para tener obj.id antes de _sync

        # Sincronizar inquilinos en la tabla pivote (defensivo: si la tabla
        # aún no existe en este deploy, lo logueamos pero no rompemos la creación)
        try:
            if inquilinos_data:
                _sync_inquilinos(db, obj, inquilinos_data, is_demo)
            elif obj.inquilino_id:
                db.add(models.ContratoInquilino(
                    contrato_id=obj.id,
                    cliente_id=obj.inquilino_id,
                    es_principal=True,
                ))
        except HTTPException:
            raise
        except Exception as e:
            print(f"[contratos.crear] sync inquilinos falló (continuamos): {e}")

        # Sincronizar garantes (tabla propia, inline). Defensivo igual que arriba.
        try:
            if garantes_data:
                _sync_garantes(db, obj, garantes_data, is_demo)
        except HTTPException:
            raise
        except Exception as e:
            print(f"[contratos.crear] sync garantes falló (continuamos): {e}")

        # Generar pagos pendientes futuros para que el contrato aparezca
        # automáticamente en Cobros y Liquidaciones.
        # Comparación de estado por STRING (no por enum) — en SQLite a veces
        # queda como string y la comparación con el Enum no matchea.
        estado_v = obj.estado.value if hasattr(obj.estado, "value") else str(obj.estado)
        print(f"[contratos.crear] post-flush contrato_id={obj.id} "
              f"estado={estado_v!r} fechas={obj.fecha_inicio}-{obj.fecha_fin} "
              f"monto={obj.monto_inicial} is_demo={obj.is_demo}")
        pagos_n = 0
        try:
            if estado_v == "vigente" and obj.fecha_inicio and obj.fecha_fin:
                from app.services.contrato_import import _generar_pagos_futuros
                pagos_n = _generar_pagos_futuros(db, obj)
                print(f"[contratos.crear] ✓ generados {pagos_n} pagos pendientes (pre-commit)")
            else:
                razones = []
                if estado_v != "vigente":   razones.append(f"estado={estado_v!r}")
                if not obj.fecha_inicio:    razones.append("falta fecha_inicio")
                if not obj.fecha_fin:       razones.append("falta fecha_fin")
                print(f"[contratos.crear] ⚠ NO se generan pagos: {', '.join(razones)}")
        except Exception as e:
            print(f"[contratos.crear] generar_pagos_futuros falló: {type(e).__name__}: {e}")

        # Historial: registramos la creación con el snapshot final del contrato.
        # La reversión va a borrarlo + pagos en cascada (FK ON DELETE CASCADE).
        historial.registrar(
            db, user,
            entidad="contratos",
            entidad_id=obj.id,
            accion=models.AccionTipo.create,
            descripcion=f"Creó contrato {obj.codigo or obj.id}",
            antes=None,
            despues=historial.snapshot(obj),
        )

        db.commit(); db.refresh(obj)

        # Verificación post-commit: SELECT explícito a la DB para confirmar
        # que los pagos quedaron persistidos. Si la transacción falló
        # silenciosamente, intentamos UNA VEZ MÁS en transacción nueva.
        try:
            count_db = db.query(models.Pago).filter_by(contrato_id=obj.id).count()
            print(f"[contratos.crear] ✅ contrato #{obj.id} CREADO en DB. "
                  f"Pagos en DB: {count_db} (esperados: {pagos_n})")

            # GARANTIZADOR: si esperábamos pagos y no hay ninguno, retry
            # en transacción independiente. Esto cubre el caso de que la
            # transacción principal haya hecho rollback parcial sin avisar.
            if pagos_n > 0 and count_db == 0:
                print(f"[contratos.crear] ⚠ retry en tx nueva — pagos no persistieron")
                from app.services.contrato_import import _generar_pagos_futuros
                try:
                    retry_n = _generar_pagos_futuros(db, obj)
                    db.commit()
                    final = db.query(models.Pago).filter_by(contrato_id=obj.id).count()
                    print(f"[contratos.crear] retry: generó {retry_n}, final en DB: {final}")
                except Exception as e:
                    print(f"[contratos.crear] retry falló: {e}")
                    try: db.rollback()
                    except Exception: pass
            elif estado_v == "vigente" and obj.fecha_inicio and obj.fecha_fin and count_db == 0:
                # Caso raro: contrato vigente con fechas pero pagos_n=0
                # (probablemente excepción silenciada arriba). Forzar generación.
                print(f"[contratos.crear] ⚠ contrato vigente sin pagos — forzando generación")
                from app.services.contrato_import import _generar_pagos_futuros
                try:
                    retry_n = _generar_pagos_futuros(db, obj)
                    db.commit()
                    final = db.query(models.Pago).filter_by(contrato_id=obj.id).count()
                    print(f"[contratos.crear] forzado: generó {retry_n}, final en DB: {final}")
                except Exception as e:
                    print(f"[contratos.crear] forzado falló: {e}")
                    try: db.rollback()
                    except Exception: pass
        except Exception as e:
            print(f"[contratos.crear] post-commit count falló: {e}")

        return obj
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[contratos.crear] {type(e).__name__}: {e}")
        raise HTTPException(400, f"No se pudo guardar el contrato: {type(e).__name__}: {str(e)[:300]}")


@router.get("/{id}", response_model=schemas.ContratoOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    return obj


@router.patch("/{id}", response_model=schemas.ContratoOut)
def editar(id: int, data: schemas.ContratoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")

    snap_antes = historial.snapshot(obj)

    payload = data.model_dump(exclude_unset=True)
    inquilinos_data = payload.pop("inquilinos", None)
    garantes_data = payload.pop("garantes", None)
    payload.pop("inquilinos_lista", None)  # solo lectura
    payload.pop("garantes_lista", None)    # solo lectura

    for k, v in payload.items():
        setattr(obj, k, v)

    # Si vino la lista de inquilinos en el PATCH, la sincronizamos.
    if inquilinos_data is not None:
        try:
            _sync_inquilinos(db, obj, inquilinos_data, workspace_flag(user))
        except HTTPException:
            db.rollback(); raise
        except Exception as e:
            print(f"[contratos.editar] sync inquilinos: {e}")

    # Si vino la lista de garantes en el PATCH, la sincronizamos (lista vacía
    # = borrar todos los garantes del contrato).
    if garantes_data is not None:
        try:
            _sync_garantes(db, obj, garantes_data, workspace_flag(user))
        except HTTPException:
            db.rollback(); raise
        except Exception as e:
            print(f"[contratos.editar] sync garantes: {e}")

    historial.registrar(
        db, user,
        entidad="contratos",
        entidad_id=obj.id,
        accion=models.AccionTipo.update,
        descripcion=f"Editó contrato {obj.codigo or obj.id}",
        antes=snap_antes,
        despues=historial.snapshot(obj),
    )
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    snap_antes = historial.snapshot(obj)
    historial.registrar(
        db, user,
        entidad="contratos",
        entidad_id=obj.id,
        accion=models.AccionTipo.delete,
        descripcion=f"Eliminó contrato {obj.codigo or obj.id}",
        antes=snap_antes,
        despues=None,
        # Borrar un contrato puede cascadear pagos/comprobantes/etc — no
        # podemos garantizar reconstrucción completa, así que lo marcamos
        # como no revertible para evitar falsos positivos.
        revertible=False,
    )
    db.delete(obj); db.commit()
    return {"ok": True}


@router.post("/{id}/archivar", response_model=schemas.ContratoOut)
def archivar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Marca el contrato como archivado. Deja de aparecer en listados
    activos pero queda accesible con ?incluir_archivados=true."""
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Contrato no encontrado")
    if obj.archivado:
        raise HTTPException(409, "Este contrato ya estaba archivado.")
    obj.archivado = True
    obj.fecha_archivado = datetime.utcnow()
    db.commit(); db.refresh(obj)
    return obj


@router.post("/{id}/desarchivar", response_model=schemas.ContratoOut)
def desarchivar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Saca el contrato del archivo."""
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Contrato no encontrado")
    obj.archivado = False
    obj.fecha_archivado = None
    db.commit(); db.refresh(obj)
    return obj


def _cliente_dict(c: models.Cliente | None) -> dict:
    if not c:
        return {"nombre_completo": "Sin asignar", "documento": None, "email": None, "telefono": None}
    nombre = " ".join([p for p in [c.nombre, c.apellido] if p])
    if c.razon_social:
        nombre = c.razon_social
    return {
        "nombre_completo": nombre or "Sin asignar",
        "documento": c.documento,
        "email": c.email,
        "telefono": c.telefono,
    }


def _propiedad_dict(p: models.Propiedad | None) -> dict:
    if not p:
        return {"direccion": "—", "ciudad": "—", "provincia": None, "tipo": "—"}
    return {
        "direccion": p.direccion,
        "ciudad": p.ciudad,
        "provincia": p.provincia,
        "tipo": (p.tipo.value if hasattr(p.tipo, "value") else str(p.tipo or "")).replace("_", " "),
    }


@router.get("/{id}/pdf")
def pdf_contrato(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Genera el PDF legal del contrato según su tipo."""
    contrato = _scope(db, user).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")

    propiedad = db.query(models.Propiedad).filter_by(id=contrato.propiedad_id).first()
    locatario = db.query(models.Cliente).filter_by(id=contrato.inquilino_id).first() if contrato.inquilino_id else None

    locador = None
    if propiedad and propiedad.propietario_id:
        locador = db.query(models.Cliente).filter_by(id=propiedad.propietario_id).first()

    ctx = {
        "contrato": {
            "id": contrato.id,
            "codigo": contrato.codigo,
            "tipo": contrato.tipo.value if hasattr(contrato.tipo, "value") else contrato.tipo,
            "estado": contrato.estado.value if hasattr(contrato.estado, "value") else contrato.estado,
            "fecha_inicio": contrato.fecha_inicio,
            "fecha_fin": contrato.fecha_fin,
            "monto_inicial": contrato.monto_inicial,
            "deposito": contrato.deposito,
            "indice_ajuste": contrato.indice_ajuste.value if hasattr(contrato.indice_ajuste, "value") else contrato.indice_ajuste,
            "periodicidad_meses": contrato.periodicidad_meses,
            "porcentaje_fijo": contrato.porcentaje_fijo,
            "comision_porc": contrato.comision_porc,
            "notas": contrato.notas,
        },
        "propiedad": _propiedad_dict(propiedad),
        "locador": _cliente_dict(locador),
        "locatario": _cliente_dict(locatario),
    }

    pdf = generar_pdf_contrato(ctx)
    filename = f"contrato-{contrato.codigo or contrato.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _persona_dict(c):
    if not c:
        return None
    return {
        "nombre": c.nombre,
        "apellido": c.apellido,
        "razon_social": c.razon_social,
        "documento": c.documento,
        "tipo_documento": getattr(c, "tipo_documento", None),
        "nacionalidad": getattr(c, "nacionalidad", None),
        "email": c.email,
        "telefono": c.telefono,
    }


def _garante_dict(g):
    return {
        "nombre": g.nombre,
        "apellido": g.apellido,
        "razon_social": g.razon_social,
        "documento": g.documento,
        "tipo_documento": g.tipo_documento,
        "nacionalidad": g.nacionalidad,
        "domicilio": g.domicilio,
        "telefono": g.telefono,
        "email": g.email,
    }


@router.get("/{id}/docx")
def docx_contrato(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Genera el contrato en formato Word (.docx) para que el admin lo edite
    antes de firmar. Después puede subir el .docx final con /archivo."""
    contrato = _scope(db, user).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")

    prop = db.query(models.Propiedad).filter_by(id=contrato.propiedad_id).first()
    inquilino = db.query(models.Cliente).filter_by(id=contrato.inquilino_id).first() if contrato.inquilino_id else None
    propietario = None
    if prop and prop.propietario_id:
        propietario = db.query(models.Cliente).filter_by(id=prop.propietario_id).first()

    garantes = [_garante_dict(g) for g in (contrato.garantes or [])]

    docx_bytes = generar_docx(
        contrato={
            "tipo": contrato.tipo.value if hasattr(contrato.tipo, "value") else contrato.tipo,
            "fecha_inicio": contrato.fecha_inicio,
            "fecha_fin": contrato.fecha_fin,
            "monto_inicial": contrato.monto_inicial,
            "deposito": contrato.deposito,
            "indice_ajuste": contrato.indice_ajuste.value if hasattr(contrato.indice_ajuste, "value") else contrato.indice_ajuste,
            "periodicidad_meses": contrato.periodicidad_meses,
            "comision_porc": contrato.comision_porc,
            "mora_diaria_porc": getattr(contrato, "mora_diaria_porc", None),
            "dia_inicio_pago": getattr(contrato, "dia_inicio_pago", None),
            "dia_vencimiento_pago": getattr(contrato, "dia_vencimiento_pago", None),
            "inventario": getattr(contrato, "inventario", None),
            "notas": contrato.notas,
        },
        propiedad={
            "direccion": prop.direccion if prop else None,
            "ciudad": prop.ciudad if prop else None,
            "provincia": prop.provincia if prop else None,
            "tipo": (prop.tipo.value if prop and hasattr(prop.tipo, "value") else (prop.tipo if prop else None)),
            "descripcion": prop.descripcion if prop else None,
        },
        propietario=_persona_dict(propietario),
        inquilino=_persona_dict(inquilino),
        garantes=garantes,
    )

    filename = f"contrato-{contrato.codigo or contrato.id}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{id}/archivo")
async def subir_archivo(
    id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Sube el contrato firmado o editado manualmente. Se guarda en Supabase
    Storage (bucket ciudad-contratos) y se actualiza la fila."""
    contrato = _scope(db, user).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")

    raw = await archivo.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Archivo > {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
    if not supabase_storage.enabled():
        raise HTTPException(503, "Supabase Storage no está configurado en el servidor")

    nombre = archivo.filename or f"contrato-{id}.docx"
    mime = archivo.content_type or "application/octet-stream"
    path = supabase_storage.gen_path(f"contrato-{id}", nombre)
    ok, info = supabase_storage.upload(
        supabase_storage.BUCKET_CONTRATOS, path, raw, mime,
    )
    if not ok:
        raise HTTPException(502, f"Error subiendo a Storage: {info}")

    # Si había un archivo anterior, intentar borrarlo (best-effort)
    if contrato.archivo_path:
        try:
            supabase_storage.delete(supabase_storage.BUCKET_CONTRATOS, contrato.archivo_path)
        except Exception:
            pass

    contrato.archivo_path = info
    contrato.archivo_nombre = nombre
    contrato.archivo_mime = mime
    contrato.archivo_subido_at = datetime.utcnow()
    db.commit()
    return {
        "ok": True,
        "archivo_nombre": nombre,
        "archivo_subido_at": contrato.archivo_subido_at.isoformat(),
        "tamano_bytes": len(raw),
    }


@router.get("/{id}/archivo")
def descargar_archivo(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Descarga el archivo subido manualmente (Word/PDF firmado)."""
    contrato = _scope(db, user).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")
    if not contrato.archivo_path:
        raise HTTPException(404, "Este contrato no tiene archivo subido")
    if not supabase_storage.enabled():
        raise HTTPException(503, "Storage no configurado")

    ok, signed = supabase_storage.get_signed_url(
        supabase_storage.BUCKET_CONTRATOS, contrato.archivo_path, expires_in=3600,
    )
    if not ok:
        raise HTTPException(502, f"sign falló: {signed}")
    return RedirectResponse(url=signed, status_code=307)


@router.delete("/{id}/archivo")
def borrar_archivo(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    contrato = _scope(db, user).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")
    if contrato.archivo_path and supabase_storage.enabled():
        try:
            supabase_storage.delete(supabase_storage.BUCKET_CONTRATOS, contrato.archivo_path)
        except Exception as e:
            print(f"[contratos] storage delete falló: {e}")
    contrato.archivo_path = None
    contrato.archivo_nombre = None
    contrato.archivo_mime = None
    contrato.archivo_subido_at = None
    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────
# Importación desde PDF con IA
# ─────────────────────────────────────────────────────────────────────

MAX_PDF_IMPORT_BYTES = 15 * 1024 * 1024   # 15 MB; PDFs muy grandes hacen explotar costo del LLM


_EXT_VALIDAS = (".pdf", ".doc", ".docx", ".txt")


@router.post("/importar-pdf-preview")
async def importar_pdf_preview(
    archivo: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """Recibe un contrato en formato PDF / DOC / DOCX / TXT, lo pasa por la
    IA y devuelve los datos extraídos SIN guardar nada. El frontend muestra
    esos datos como preview editable; cuando el usuario confirma, se llama
    /importar-pdf-confirmar.
    """
    fn = (archivo.filename or "").lower()
    if not any(fn.endswith(ext) for ext in _EXT_VALIDAS):
        raise HTTPException(
            400,
            f"Formato no soportado. Aceptados: {', '.join(_EXT_VALIDAS)}",
        )
    raw = await archivo.read()
    if len(raw) > MAX_PDF_IMPORT_BYTES:
        raise HTTPException(413, f"Archivo demasiado grande (máx {MAX_PDF_IMPORT_BYTES // 1024 // 1024} MB).")
    if len(raw) < 100:
        raise HTTPException(400, "El archivo parece vacío o corrupto.")
    try:
        datos = contrato_import.parsear_contrato_archivo(
            raw, filename=archivo.filename or "contrato",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[importar-pdf-preview] {type(e).__name__}: {e}")
        raise HTTPException(502, f"La IA no pudo procesar el archivo: {type(e).__name__}: {str(e)[:200]}")
    return {"ok": True, "datos": datos}


@router.post("/importar-pdf-confirmar")
def importar_pdf_confirmar(
    datos: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Recibe el JSON ya revisado por el usuario y crea las entidades
    (propietario, inquilino, propiedad, contrato). Devuelve qué creó y qué
    reutilizó (por DNI o por dirección)."""
    try:
        resumen = contrato_import.crear_desde_parsed(db, datos, user)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        print(f"[importar-pdf-confirmar] {type(e).__name__}: {e}")
        raise HTTPException(500, f"No se pudo importar: {type(e).__name__}: {str(e)[:200]}")
    return {"ok": True, **resumen}
