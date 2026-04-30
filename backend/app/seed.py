from datetime import date
from app.database import SessionLocal, Base, engine
from app import models
from app.security import hash_pw


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            print("Seed ya ejecutado.")
            return

        admin = models.User(
            nombre="Admin Ciudad",
            email="admin@ciudad.com",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.admin,
        )
        db.add(admin); db.commit()

        # Clientes
        prop1 = models.Cliente(nombre="María", apellido="González", documento="20-12345678-9",
                               email="maria@mail.com", telefono="+5491155555001",
                               rol=models.ClienteRol.propietario)
        prop2 = models.Cliente(nombre="Carlos", apellido="Pérez", documento="20-11111111-1",
                               rol=models.ClienteRol.propietario)
        inq1 = models.Cliente(nombre="Juan", apellido="López", documento="20-22222222-2",
                              email="juan@mail.com", telefono="+5491155555002",
                              rol=models.ClienteRol.inquilino)
        inq2 = models.Cliente(nombre="Ana", apellido="Ruiz", rol=models.ClienteRol.inquilino)
        db.add_all([prop1, prop2, inq1, inq2]); db.commit()

        # Propiedades
        p1 = models.Propiedad(
            codigo="DEP-001", direccion="Av. Corrientes 1234, 5°A",
            ciudad="CABA", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.departamento,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.ocupada,
            superficie_m2=65, ambientes=3,
            descripcion="Departamento luminoso en pleno centro.",
            precio_alquiler=350000, expensas=85000,
            impuesto_inmobiliario=12000, tasa_municipal=8500,
            propietario_id=prop1.id,
        )
        p2 = models.Propiedad(
            codigo="CAS-002", direccion="Belgrano 456",
            ciudad="San Isidro", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.casa,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=180, ambientes=5,
            precio_alquiler=720000, expensas=0,
            impuesto_inmobiliario=35000, tasa_municipal=18000,
            propietario_id=prop2.id,
        )
        p3 = models.Propiedad(
            codigo="LOC-003", direccion="Av. Santa Fe 2890",
            ciudad="CABA", tipo=models.PropiedadTipo.local,
            modalidad=models.PropiedadModalidad.alquiler,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=45, precio_alquiler=950000,
            impuesto_inmobiliario=22000, tasa_municipal=14000,
            propietario_id=prop1.id,
        )
        p4 = models.Propiedad(
            codigo="VEN-004", direccion="Av. del Libertador 5500",
            ciudad="CABA", tipo=models.PropiedadTipo.departamento,
            modalidad=models.PropiedadModalidad.venta,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=110, ambientes=4,
            precio_venta=320000, tokko_id="TKO-9981",
            propietario_id=prop2.id,
        )
        p5 = models.Propiedad(
            codigo="CMP-005", direccion="Ruta 8 km 124",
            ciudad="Pergamino", provincia="Buenos Aires",
            tipo=models.PropiedadTipo.campo,
            modalidad=models.PropiedadModalidad.venta,
            estado=models.PropiedadEstado.disponible,
            superficie_m2=120000, precio_venta=850000,
            propietario_id=prop1.id,
        )
        db.add_all([p1, p2, p3, p4, p5]); db.commit()

        # Contratos
        c1 = models.Contrato(
            codigo="ALQ-2025-001", tipo=models.ContratoTipo.alquiler_vivienda,
            estado=models.ContratoEstado.vigente,
            propiedad_id=p1.id, inquilino_id=inq1.id,
            fecha_inicio=date(2025, 10, 1), fecha_fin=date(2028, 9, 30),
            monto_inicial=350000, deposito=350000,
            indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
            comision_porc=5,
        )
        c2 = models.Contrato(
            codigo="ALQ-2025-002", tipo=models.ContratoTipo.alquiler_comercial,
            estado=models.ContratoEstado.borrador,
            propiedad_id=p3.id, inquilino_id=inq2.id,
            fecha_inicio=date(2026, 5, 1), fecha_fin=date(2029, 4, 30),
            monto_inicial=950000, deposito=1900000,
            indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=6,
            comision_porc=8,
        )
        db.add_all([c1, c2]); db.commit()

        print("✅ Seed completado. Login: admin@ciudad.com / ciudad1234")
    finally:
        db.close()


if __name__ == "__main__":
    run()
