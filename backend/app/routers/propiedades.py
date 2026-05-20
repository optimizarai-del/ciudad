from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services import supabase_storage
from app.services.workspace import apply_workspace_filter, workspace_flag, is_demo_user

router = APIRouter(prefix="/api/propiedades", tags=["propiedades"])


def _to_out(p: models.Propiedad) -> dict:
    """Serialización con propietario_nombre (legacy) y propietarios_lista (M2M)."""
    d = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    # Legacy: nombre del propietario principal
    nombre = None
    if p.propietario:
        partes = [p.propietario.nombre or "", p.propietario.apellido or ""]
        nombre = (p.propietario.razon_social or
                  " ".join([s for s in partes if s]).strip() or None)
    d["propietario_nombre"] = nombre

    # M2M: lista de todos los co-propietarios
    lista = []
    for pp in (p.propietarios or []):
        c = pp.cliente
        if not c:
            continue
        partes = [c.nombre or "", c.apellido or ""]
        nombre_co = (c.razon_social or
                     " ".join([s for s in partes if s]).strip() or "Sin nombre")
        lista.append({
            "cliente_id": c.id,
            "nombre": nombre_co,
            "documento": c.documento,
            "email": c.email,
            "porcentaje": pp.porcentaje,
            "es_principal": pp.es_principal,
        })
    d["propietarios_lista"] = lista
    return d


def _sincronizar_propietarios(
    db: Session,
    propiedad: models.Propiedad,
    propietarios: list[dict] | None,
    propietario_id_legacy: int | None,
):
    """Sincroniza la pivote `propiedad_propietarios` según lo que mande el
    frontend.

    Reglas:
    - Si viene `propietarios` (lista) → es la fuente de verdad, reemplaza
      la pivote completa. Cada item: {cliente_id, porcentaje?, es_principal?}.
    - Si viene solo `propietario_id` (legacy) → si la pivote está vacía,
      crea una fila con ese cliente. Si ya hay filas, no toca nada (el
      frontend nuevo usa propietarios=[]).
    - El campo `Propiedad.propietario_id` se mantiene sincronizado con el
      es_principal de la pivote para compatibilidad.
    """
    if propietarios is not None:
        # Borrar todas las filas actuales y volver a crear
        db.query(models.PropiedadPropietario).filter_by(
            propiedad_id=propiedad.id
        ).delete()
        db.flush()
        if propietarios:
            principal_set = False
            for i, item in enumerate(propietarios):
                cid = item.get("cliente_id") or item.get("id")
                if not cid:
                    continue
                porc = item.get("porcentaje")
                if porc in ("", None):
                    porc = None
                else:
                    try: porc = float(porc)
                    except Exception: porc = None
                es_principal = bool(item.get("es_principal", i == 0 and not principal_set))
                if es_principal:
                    principal_set = True
                db.add(models.PropiedadPropietario(
                    propiedad_id=propiedad.id,
                    cliente_id=int(cid),
                    porcentaje=porc,
                    es_principal=es_principal,
                ))
            db.flush()
            # Sincronizar el legacy propietario_id con el es_principal
            principal = (
                db.query(models.PropiedadPropietario)
                  .filter_by(propiedad_id=propiedad.id, es_principal=True)
                  .first()
            )
            if not principal:
                principal = (
                    db.query(models.PropiedadPropietario)
                      .filter_by(propiedad_id=propiedad.id)
                      .first()
                )
                if principal:
                    principal.es_principal = True
                    db.flush()
            propiedad.propietario_id = principal.cliente_id if principal else None
        else:
            propiedad.propietario_id = None
    elif propietario_id_legacy is not None:
        # Modo compat: crear una fila pivote si no existe ninguna
        existe = db.query(models.PropiedadPropietario).filter_by(
            propiedad_id=propiedad.id
        ).first()
        if not existe:
            db.add(models.PropiedadPropietario(
                propiedad_id=propiedad.id,
                cliente_id=propietario_id_legacy,
                es_principal=True,
            ))
            db.flush()


def _scope(db: Session, user):
    """Query base aislada por workspace (demo vs real)."""
    return apply_workspace_filter(db.query(models.Propiedad), models.Propiedad, user)


@router.get("/", response_model=List[schemas.PropiedadOut])
def listar(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Eager-load propietario (1 JOIN) y la pivote M2M propietarios + sus clientes
    # (1 subquery adicional via selectinload). Evita el N+1 que se producía al
    # acceder a p.propietario y pp.cliente desde _to_out() con lazy loading.
    q = (
        _scope(db, user)
        .options(
            joinedload(models.Propiedad.propietario),
            selectinload(models.Propiedad.propietarios)
            .joinedload(models.PropiedadPropietario.cliente),
        )
        .order_by(models.Propiedad.id.desc())
    )
    if limit:
        q = q.limit(limit)
    return [_to_out(p) for p in q.all()]


@router.post("/", response_model=schemas.PropiedadOut)
def crear(data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    payload = data.model_dump()
    # Extraer lista nueva y propietario legacy antes de instanciar el modelo
    propietarios_lista = payload.pop("propietarios", None)
    propietario_legacy = payload.get("propietario_id")
    obj = models.Propiedad(**payload)
    obj.is_demo = workspace_flag(user)
    db.add(obj); db.flush()
    _sincronizar_propietarios(db, obj, propietarios_lista, propietario_legacy)
    db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.get("/{id}", response_model=schemas.PropiedadOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    return _to_out(obj)


@router.patch("/{id}", response_model=schemas.PropiedadOut)
def editar(id: int, data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    payload = data.model_dump(exclude_unset=True)
    propietarios_lista = payload.pop("propietarios", None)
    propietario_legacy = payload.get("propietario_id")
    for k, v in payload.items():
        if k == "is_demo":  # no se puede cambiar el workspace via API
            continue
        setattr(obj, k, v)
    db.flush()
    # Solo tocamos la pivote si el frontend mandó algo explícito
    if propietarios_lista is not None or "propietario_id" in payload:
        _sincronizar_propietarios(db, obj, propietarios_lista, propietario_legacy)
    db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}


class FichaPDFRequest(BaseModel):
    condiciones: Optional[str] = None


def _fotos_urls(db: Session, prop: models.Propiedad) -> list[str]:
    """URLs descargables de las fotos de la propiedad."""
    adj = (
        db.query(models.PropiedadAdjunto)
          .filter_by(propiedad_id=prop.id, tipo=models.AdjuntoTipo.foto)
          .order_by(
              models.PropiedadAdjunto.es_principal.desc(),
              models.PropiedadAdjunto.created_at.asc(),
          )
          .all()
    )
    urls = []
    for a in adj:
        if a.storage_path and supabase_storage.enabled():
            ok, signed = supabase_storage.get_signed_url(
                supabase_storage.BUCKET_ADJUNTOS, a.storage_path, expires_in=600,
            )
            if ok:
                urls.append(signed)
        # blob_b64 legacy: no soportado para el PDF (necesitaríamos un endpoint
        # auto-firmado, complica innecesariamente; los datos nuevos van a Storage).
    return urls


@router.post("/{id}/ficha-pdf")
def ficha_pdf(
    id: int,
    data: FichaPDFRequest = FichaPDFRequest(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Genera un PDF de presentación del inmueble — fotos + características +
    condiciones. SIN propietarios ni inquilinos (es la versión comercial)."""
    p = _scope(db, user).filter_by(id=id).first()
    if not p:
        raise HTTPException(404, "Propiedad no encontrada")

    from app.services.pdf_ficha_inmueble import generar_pdf_ficha
    payload = {
        "tipo": p.tipo.value if hasattr(p.tipo, "value") else p.tipo,
        "direccion": p.direccion,
        "ciudad": p.ciudad,
        "provincia": p.provincia,
        "ambientes": p.ambientes,
        "superficie_m2": p.superficie_m2,
        "precio_alquiler": p.precio_alquiler,
        "expensas": p.expensas,
        "tasa_municipal": p.tasa_municipal,
        "descripcion": p.descripcion,
    }
    fotos = _fotos_urls(db, p)
    pdf = generar_pdf_ficha(payload, fotos, condiciones=data.condiciones)

    safe_addr = (p.direccion or f"propiedad-{p.id}").replace(" ", "-")[:60]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ficha-{safe_addr}.pdf"',
        },
    )
