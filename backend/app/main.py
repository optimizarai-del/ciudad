import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.database import Base, engine
from app.routers import auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CIUDAD. — Inmuebles · Contratos · Gestión", version="0.1.0")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in [auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos]:
    app.include_router(r.router)


@app.get("/health")
def health():
    return {"status": "ok", "brand": "CIUDAD."}


@app.on_event("startup")
def _seed_if_empty():
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            from app.seed import run as seed_run
            seed_run()
    finally:
        db.close()
