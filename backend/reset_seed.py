"""
Borra la base de datos y vuelve a cargar todos los datos demo.
Ejecutar con el backend APAGADO:
    python reset_seed.py
"""
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "ciudad.db")

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("ciudad.db eliminada")
else:
    print("No existia ciudad.db")

from app.seed import run
run()
