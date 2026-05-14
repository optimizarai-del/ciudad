from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services.pdf_service import generar_pdf_contrato
from app.services.contrato_docx import generar_docx
from app.services import supabase_storage

router = APIRouter(prefix="/api/contratos", tags=["contratos"])


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.get("/", response_model=List[schemas.ContratoOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Contrato).order_by(models.Contrato.id.desc()).all()


@router.post("/", response_model=schemas.ContratoOut)
def crear(data: schemas.ContratoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Mensajes de error claros para los validaciones más comunes en vez de
    # un 500 genérico que aparezca como toast rojo sin información.
    payload = data.model_dump()

    # Validar propiedad
    if not payload.get("propiedad_id"):
        raise HTTPException(400, "Falta seleccionar una propiedad para el contrato.")
    prop = db.query(models.Propiedad).filter_by(id=payload["propiedad_id"]).first()
    if not prop:
        raise HTTPException(404, f"La propiedad #{payload['propiedad_id']} no existe.")

    # Validar inquilino si se mandó
    if payload.get("inquilino_id"):
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

    try:
        obj = models.Contrato(**payload)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    except Exception as e:
        db.rollback()
        print(f"[contratos.crear] {type(e).__name__}: {e}")
        raise HTTPException(400, f"No se pudo guardar el contrato: {type(e).__name__}: {str(e)[:300]}")


@router.get("/{id}", response_model=schemas.ContratoOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Contrato).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    return obj


@router.patch("/{id}", response_model=schemas.ContratoOut)
def editar(id: int, data: schemas.ContratoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Contrato).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Contrato).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


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
    contrato = db.query(models.Contrato).filter_by(id=id).first()
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
        "email": c.email,
        "telefono": c.telefono,
    }


@router.get("/{id}/docx")
def docx_contrato(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Genera el contrato en formato Word (.docx) para que el admin lo edite
    antes de firmar. Después puede subir el .docx final con /archivo."""
    contrato = db.query(models.Contrato).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")

    prop = db.query(models.Propiedad).filter_by(id=contrato.propiedad_id).first()
    inquilino = db.query(models.Cliente).filter_by(id=contrato.inquilino_id).first() if contrato.inquilino_id else None
    propietario = None
    if prop and prop.propietario_id:
        propietario = db.query(models.Cliente).filter_by(id=prop.propietario_id).first()

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
            "notas": contrato.notas,
        },
        propiedad={
            "direccion": prop.direccion if prop else None,
            "ciudad": prop.ciudad if prop else None,
            "provincia": prop.provincia if prop else None,
        },
        propietario=_persona_dict(propietario),
        inquilino=_persona_dict(inquilino),
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
    contrato = db.query(models.Contrato).filter_by(id=id).first()
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
    contrato = db.query(models.Contrato).filter_by(id=id).first()
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
    contrato = db.query(models.Contrato).filter_by(id=id).first()
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
