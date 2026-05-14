"""
Workspace de demo: aislamiento de datos.

Los usuarios con `role=admin_demo` viven en un "sandbox": ven sólo registros
con `is_demo=True` y los registros que crean nacen con `is_demo=True`.

Los usuarios "reales" (admin, gerencia, alquileres, ventas, agente_ia) ven
sólo `is_demo=False` y crean con `is_demo=False`.

Este módulo es la verdad única — todos los routers deben:
- llamar a `apply_workspace_filter(query, Modelo, user)` antes de devolver
  resultados de un GET;
- pasar `is_demo=is_demo_user(user)` al instanciar el modelo en un POST.

Mantener esta convención garantiza que ningún usuario del workspace real
vea datos demo (y viceversa).
"""
from app import models


def is_demo_user(user) -> bool:
    """True si el usuario pertenece al sandbox demo."""
    if not user:
        return False
    role = user.role
    # En Postgres viene como enum, en SQLite a veces como string.
    if hasattr(role, "value"):
        role = role.value
    return role == "admin_demo"


def apply_workspace_filter(query, model, user):
    """Filtra el query para que solo devuelva las filas del workspace del
    usuario. El modelo debe tener `is_demo`."""
    flag = is_demo_user(user)
    return query.filter(model.is_demo == flag)


def workspace_flag(user) -> bool:
    """Alias semántico para usar al crear registros: `is_demo=workspace_flag(user)`."""
    return is_demo_user(user)
