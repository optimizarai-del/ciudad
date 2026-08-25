"""
Estado y disparo del motor de ajustes de alquiler.

El motor ya corre solo dentro del servidor (loop diario en main.py +
aplicación perezosa al abrir Cobranza). Este router agrega dos cosas para que
la actualización 24/7 sea A PRUEBA DE TODO y VERIFICABLE:

  GET  /api/ajustes/estado  → latido: cuándo corrió por última vez, si salió
       ok, qué ajustó, y qué tan frescos están los índices IPC/ICL. Sirve para
       comprobar de un vistazo que "está vivo".

  POST /api/ajustes/correr  → fuerza una corrida ya (refresca índices + aplica
       ajustes pendientes). Pensado para un CRON EXTERNO diario de respaldo: si
       el loop interno alguna vez se cayera, el cron externo garantiza igual la
       corrida. También sirve para forzarla a mano.

Autorización de ambos endpoints (cualquiera de las dos alcanza):
  - JWT de un usuario admin (Authorization: Bearer ...), o
  - Token de cron compartido: header `X-Cron-Token` o query `?token=` igual a
    la env var AJUSTES_CRON_TOKEN. Así un cron sin login puede dispararlo.
Si AJUSTES_CRON_TOKEN no está seteada, el path por token queda deshabilitado
y solo se permite con admin.
"""
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import SECRET_KEY, ALGORITHM, get_current_user
from app.services import ajuste_contratos
from app.services.workspace import apply_workspace_filter

router = APIRouter(prefix="/api/ajustes", tags=["ajustes"])


def _es_admin_por_jwt(request: Request, db: Session) -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return False
    from app.models import User
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        return False
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return role == "admin"


def _token_cron_valido(request: Request) -> bool:
    esperado = (os.getenv("AJUSTES_CRON_TOKEN") or "").strip()
    if not esperado:
        return False  # sin token configurado, este camino queda cerrado
    recibido = (
        request.headers.get("X-Cron-Token")
        or request.query_params.get("token")
        or ""
    ).strip()
    if not recibido:
        return False
    # Comparación en tiempo constante para no filtrar el token por timing.
    return secrets.compare_digest(recibido, esperado)


def _autorizar(request: Request, db: Session) -> None:
    if _token_cron_valido(request) or _es_admin_por_jwt(request, db):
        return
    raise HTTPException(401, "No autorizado (requiere admin o token de cron)")


def _snapshot_indices(db: Session) -> dict:
    """Frescura de los índices y último ajuste guardado — sin pegarle a las APIs
    (usa el cache de series ya cargado). Defensivo: nunca rompe el endpoint."""
    out: dict = {}
    try:
        from app.services import indices_service
        serie_ipc = indices_service._SERIE_CACHE.get("ipc") or {}
        out["ipc_ultimo_mes"] = max(serie_ipc.keys()) if serie_ipc else None
        icl_cache = indices_service._SERIE_CACHE.get("icl")
        if icl_cache and icl_cache[0]:
            out["icl_ultima_fecha"] = icl_cache[0][-1][0].isoformat()
        else:
            out["icl_ultima_fecha"] = None
    except Exception as e:
        out["indices_error"] = f"{type(e).__name__}: {e}"
    try:
        from app import models
        ult = (db.query(models.AjusteContrato)
               .order_by(models.AjusteContrato.fecha.desc(),
                         models.AjusteContrato.id.desc())
               .first())
        out["ultimo_ajuste_db"] = ult.fecha.isoformat() if ult and ult.fecha else None
    except Exception as e:
        out["ajuste_db_error"] = f"{type(e).__name__}: {e}"
    return out


@router.get("/estado")
def estado(request: Request, db: Session = Depends(get_db)):
    """Latido del motor de ajustes: última corrida + frescura de índices."""
    _autorizar(request, db)
    hb = ajuste_contratos.estado_actualizacion()
    return {
        "motor": "ajustes-diarios",
        "loop_interno_activo": os.getenv("AJUSTES_DIARIOS_ENABLED", "true").lower()
                               in ("1", "true", "yes"),
        "cron_externo_configurado": bool((os.getenv("AJUSTES_CRON_TOKEN") or "").strip()),
        "ultima_corrida": hb.get("ultima_corrida"),
        "ultima_corrida_ok": hb.get("ok"),
        "ultimo_resumen": hb.get("resumen"),
        **_snapshot_indices(db),
    }


@router.post("/correr")
def correr(request: Request, db: Session = Depends(get_db)):
    """Fuerza una corrida del motor ahora mismo. Devuelve el resumen. Pensado
    para el cron externo diario de respaldo y para disparos manuales."""
    _autorizar(request, db)
    resumen = ajuste_contratos.correr_actualizacion_diaria()
    return {"disparado": True, "resumen": resumen}


@router.post("/recalcular")
def recalcular(dry_run: bool = True, db: Session = Depends(get_db),
               user=Depends(get_current_user)):
    """Recalcula los ajustes YA EXISTENTES con la fórmula actual (corrige los
    que se guardaron con una versión anterior del cálculo). SOLO ADMIN.

    Respeta el WORKSPACE del usuario: un admin real solo recalcula contratos
    reales (is_demo=false); nunca toca datos del sandbox demo (y viceversa).

    - `dry_run=true` (default): NO toca nada, solo devuelve qué cambiaría.
    - `dry_run=false`: aplica los cambios (corrige la tabla de ajustes). No
      toca los pagos ya cobrados: esos conservan su monto histórico.
    """
    from app import models
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role not in ("admin", "admin_demo"):
        raise HTTPException(403, "Solo un admin puede recalcular ajustes")
    contratos = (apply_workspace_filter(db.query(models.Contrato), models.Contrato, user)
                 .filter(models.Contrato.estado == "vigente").all())
    cambios = ajuste_contratos.recalcular_ajustes(db, contratos, dry_run=dry_run)
    if not dry_run and cambios:
        db.commit()
    total_dif = round(sum(
        (c.get("monto_final_correcto", 0) - c.get("monto_final_viejo", 0))
        for c in cambios
    ), 2)
    return {
        "dry_run": dry_run,
        "contratos_con_cambios": len(cambios),
        "diferencia_total_precio_vigente": total_dif,
        "cambios": cambios,
    }
