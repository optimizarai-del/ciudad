"""
Seed de datos demo para CIUDAD.
Genera usuarios, clientes, propiedades, contratos, pagos y ajustes realistas.
"""
from datetime import date, timedelta
from app.database import SessionLocal, Base, engine
from app import models
from app.security import hash_pw


def _pago(db, contrato_id, periodo, vence, pagado_en, alq, exp, imp, mun, estado):
    total = alq + exp + imp + mun
    p = models.Pago(
        contrato_id=contrato_id,
        periodo=periodo,
        fecha_vencimiento=vence,
        fecha_pago=pagado_en,
        monto_alquiler=alq,
        monto_expensas=exp,
        monto_impuestos=imp,
        monto_municipal=mun,
        monto_total=total,
        estado=estado,
    )
    db.add(p)


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            print("Seed ya ejecutado.")
            return

        # ───────────────��──────────────────────────────
        # USUARIOS
        # ─────────────────────────────��────────────────
        admin = models.User(
            nombre="Sofía Ramírez",
            email="admin@ciudad.com",
            telefono="+54 9 11 5500-0001",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.admin,
        )
        operador = models.User(
            nombre="Nicolás Torres",
            email="alquileres@ciudad.com",
            telefono="+54 9 11 5500-0002",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.alquileres,
        )
        finanzas = models.User(
            nombre="Valentina Díaz",
            email="ventas@ciudad.com",
            telefono="+54 9 11 5500-0003",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.ventas,
        )
        agente = models.User(
            nombre="Mateo Sánchez",
            email="agente@ciudad.com",
            telefono="+54 9 11 5500-0004",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.agente_ia,
        )
        db.add_all([admin, operador, finanzas, agente])
        db.commit()

        # ──────────────────────────────────────────────
        # CLIENTES — propietarios
        # ──────────────────────────────────────���───────
        pr1 = models.Cliente(
            nombre="María Elena", apellido="González",
            documento="20-12345678-9", email="mgonzalez@gmail.com",
            telefono="+54 9 11 6001-1001",
            rol=models.ClienteRol.propietario,
            notas="Propietaria de varios departamentos en CABA.",
        )
        pr2 = models.Cliente(
            nombre="Roberto", apellido="Fernández",
            documento="20-98765432-1", email="rfernandez@outlook.com",
            telefono="+54 9 11 6001-1002",
            rol=models.ClienteRol.propietario,
        )
        pr3 = models.Cliente(
            nombre="Inversiones Del Sur", apellido="",
            razon_social="Inversiones Del Sur S.R.L.",
            documento="30-71234567-8", email="admin@inversionesdelsur.com",
            telefono="+54 9 11 6001-1003",
            rol=models.ClienteRol.propietario,
            notas="Empresa con 6 inmuebles en cartera.",
        )
        pr4 = models.Cliente(
            nombre="Claudia", apellido="Morales",
            documento="27-44567890-3", email="cmorales@yahoo.com.ar",
            telefono="+54 9 11 6001-1004",
            rol=models.ClienteRol.propietario,
        )

        # CLIENTES — inquilinos
        in1 = models.Cliente(
            nombre="Juan Ignacio", apellido="López",
            documento="20-22222222-2", email="jilopez@gmail.com",
            telefono="+54 9 11 7001-2001",
            rol=models.ClienteRol.inquilino,
        )
        in2 = models.Cliente(
            nombre="Ana Paula", apellido="Ruiz",
            documento="27-33333333-3", email="apruiz@gmail.com",
            telefono="+54 9 11 7001-2002",
            rol=models.ClienteRol.inquilino,
        )
        in3 = models.Cliente(
            nombre="Diego", apellido="Herrera",
            documento="20-44444444-4", email="dherrera@hotmail.com",
            telefono="+54 9 11 7001-2003",
            rol=models.ClienteRol.inquilino,
        )
        in4 = models.Cliente(
            nombre="Lucía", apellido="Martínez",
            documento="27-55555555-5", email="lmartinez@gmail.com",
            telefono="+54 9 11 7001-2004",
            rol=models.ClienteRol.inquilino,
        )
        in5 = models.Cliente(
            nombre="Restaurante El Portal", apellido="",
            razon_social="El Portal Gastronomía S.A.S.",
            documento="30-88776655-4", email="contacto@elportal.com.ar",
            telefono="+54 9 11 7001-2005",
            rol=models.ClienteRol.inquilino,
            notas="Local gastronómico. Contrato comercial.",
        )
        in6 = models.Cliente(
            nombre="Martín", apellido="Gómez",
            documento="20-66666666-6", email="mgomez@gmail.com",
            telefono="+54 9 11 7001-2006",
            rol=models.ClienteRol.inquilino,
        )

        # CLIENTES — compradores / vendedores
        co1 = models.Cliente(
            nombre="Patricia", apellido="Vega",
            documento="27-77777777-7", email="pvega@gmail.com",
            telefono="+54 9 11 8001-3001",
            rol=models.ClienteRol.comprador,
        )
        ve1 = models.Cliente(
            nombre="Héctor", apellido="Ibáñez",
            documento="20-88888888-8", email="hibanez@gmail.com",
            telefono="+54 9 11 8001-3002",
            rol=models.ClienteRol.vendedor,
        )

        db.add_all([pr1, pr2, pr3, pr4, in1, in2, in3, in4, in5, in6, co1, ve1])
        db.commit()

        # ────────────────���─────────────────────────────
        # PROPIEDADES
        # ──────────────────────────────────────────────
        props = [
            # --- CABA ocupadas ---
            models.Propiedad(
                codigo="DEP-001", direccion="Av. Corrientes 1234 5°A",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=65, ambientes=3,
                descripcion="Departamento luminoso en el corazón del teatro. Piso 5 con vista a Corrientes, cocina americana, balcón.",
                precio_alquiler=420000, expensas=92000,
                impuesto_inmobiliario=14000, tasa_municipal=9500,
                propietario_id=pr1.id,
            ),
            models.Propiedad(
                codigo="DEP-002", direccion="Charcas 3450 2°B",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=48, ambientes=2,
                descripcion="Dos ambientes en Palermo. Luminoso, contrafrente.",
                precio_alquiler=360000, expensas=78000,
                impuesto_inmobiliario=11000, tasa_municipal=7500,
                propietario_id=pr1.id,
            ),
            models.Propiedad(
                codigo="DEP-003", direccion="Lavalle 1890 8°C",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=55, ambientes=3,
                descripcion="Tres ambientes con cochera. Edificio con amenities.",
                precio_alquiler=490000, expensas=105000,
                impuesto_inmobiliario=16000, tasa_municipal=11000,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="DEP-004", direccion="Thames 765 PB",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=38, ambientes=1,
                descripcion="Monoambiente en Palermo SoHo. Ideal profesional.",
                precio_alquiler=280000, expensas=62000,
                impuesto_inmobiliario=9000, tasa_municipal=6000,
                propietario_id=pr2.id,
            ),
            # --- GBA ocupadas ---
            models.Propiedad(
                codigo="CAS-005", direccion="Belgrano 456",
                ciudad="San Isidro", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=220, ambientes=6,
                descripcion="Casa con jardín, quincho y pileta. Barrio privado. 3 dormitorios en suite.",
                precio_alquiler=890000, expensas=0,
                impuesto_inmobiliario=42000, tasa_municipal=28000,
                propietario_id=pr4.id,
            ),
            models.Propiedad(
                codigo="CAS-006", direccion="Los Aromos 122",
                ciudad="Tigre", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=140, ambientes=4,
                descripcion="Casa en barrio cerrado. Acceso a dársena privada.",
                precio_alquiler=620000, expensas=0,
                impuesto_inmobiliario=28000, tasa_municipal=19000,
                propietario_id=pr2.id,
            ),
            # --- Locales comerciales ---
            models.Propiedad(
                codigo="LOC-007", direccion="Av. Santa Fe 2890 PB",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.local,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=55,
                descripcion="Local a la calle sobre Av. Santa Fe. Vidriera doble. Ideal gastronomía.",
                precio_alquiler=1150000, expensas=0,
                impuesto_inmobiliario=32000, tasa_municipal=22000,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="LOC-008", direccion="Cabildo 1200 PB loc 3",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.local,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.reservada,
                superficie_m2=30,
                descripcion="Local en galería comercial. Alto tránsito peatonal.",
                precio_alquiler=680000, expensas=45000,
                impuesto_inmobiliario=18000, tasa_municipal=12000,
                propietario_id=pr1.id,
            ),
            # --- Disponibles para alquiler ---
            models.Propiedad(
                codigo="DEP-009", direccion="Av. Rivadavia 4560 3°D",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=72, ambientes=3,
                descripcion="Tres ambientes amplio. Planta libre, piso flotante, cocina equipada.",
                precio_alquiler=530000, expensas=88000,
                impuesto_inmobiliario=17000, tasa_municipal=11500,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="DEP-010", direccion="Billinghurst 890 1°A",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=44, ambientes=2,
                descripcion="Dos ambientes reciclado. Barrio de Villa Crespo.",
                precio_alquiler=330000, expensas=70000,
                impuesto_inmobiliario=10000, tasa_municipal=7000,
                propietario_id=pr4.id,
            ),
            models.Propiedad(
                codigo="CAS-011", direccion="Mitre 340",
                ciudad="Morón", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=110, ambientes=4,
                descripcion="Casa independiente con patio. 3 dormitorios, cochera cubierta.",
                precio_alquiler=480000, expensas=0,
                impuesto_inmobiliario=22000, tasa_municipal=16000,
                propietario_id=pr2.id,
            ),
            # --- En venta ---
            models.Propiedad(
                codigo="VEN-012", direccion="Av. del Libertador 5500 9°B",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.venta,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=130, ambientes=4,
                descripcion="Cuatro ambientes con vista al río. Edificio con amenities premium.",
                precio_venta=380000, tokko_id="TKO-9981",
                propietario_id=pr2.id,
            ),
            models.Propiedad(
                codigo="VEN-013", direccion="Olleros 2200 4°C",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.venta,
                estado=models.PropiedadEstado.reservada,
                superficie_m2=88, ambientes=3,
                descripcion="Tres ambientes en Palermo. Reciclado a nuevo.",
                precio_venta=210000, tokko_id="TKO-9982",
                propietario_id=pr1.id,
            ),
            models.Propiedad(
                codigo="CAS-014", direccion="Av. Gaona 3100",
                ciudad="Ramos Mejía", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.ambas,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=180, ambientes=5,
                descripcion="Casa en esquina. También disponible para alquiler.",
                precio_alquiler=750000, precio_venta=145000,
                impuesto_inmobiliario=34000, tasa_municipal=24000,
                propietario_id=pr4.id,
            ),
            # --- Campo ---
            models.Propiedad(
                codigo="CMP-015", direccion="Ruta 8 km 124",
                ciudad="Pergamino", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.campo,
                modalidad=models.PropiedadModalidad.venta,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=1_200_000,
                descripcion="Campo agrícola de 120 ha. Apto soja/maíz. Escritura limpia.",
                precio_venta=1_200_000,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="LOC-016", direccion="Humberto Primo 1450",
                ciudad="CABA", provincia="Buenos Aires",
                tipo=models.PropiedadTipo.local,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.inactiva,
                superficie_m2=80,
                descripcion="Local en San Telmo. En refacción. Disponible desde agosto 2026.",
                precio_alquiler=920000,
                impuesto_inmobiliario=26000, tasa_municipal=18000,
                propietario_id=pr3.id,
            ),
        ]
        db.add_all(props)
        db.commit()

        p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15, p16 = props

        # ───────────────────────────────────���──────────
        # CONTRATOS
        # ──────────────────────────────────────────────
        contratos = [
            # Vigentes con historial de pagos
            models.Contrato(
                codigo="ALQ-2024-001",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p1.id, inquilino_id=in1.id,
                fecha_inicio=date(2024, 3, 1), fecha_fin=date(2027, 2, 28),
                monto_inicial=350000, deposito=350000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5, notas="Primer inquilino del edificio. Muy buen pagador.",
            ),
            models.Contrato(
                codigo="ALQ-2024-002",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p2.id, inquilino_id=in2.id,
                fecha_inicio=date(2024, 7, 1), fecha_fin=date(2026, 6, 30),
                monto_inicial=300000, deposito=600000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=3,
                comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2024-003",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p3.id, inquilino_id=in3.id,
                fecha_inicio=date(2024, 10, 1), fecha_fin=date(2027, 9, 30),
                monto_inicial=430000, deposito=430000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2024-004",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p4.id, inquilino_id=in6.id,
                fecha_inicio=date(2024, 12, 1), fecha_fin=date(2026, 11, 30),
                monto_inicial=260000, deposito=260000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=3,
                comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2024-005",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p5.id, inquilino_id=in4.id,
                fecha_inicio=date(2024, 5, 1), fecha_fin=date(2027, 4, 30),
                monto_inicial=750000, deposito=1500000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=4, notas="Casa premium. Depósito reforzado.",
            ),
            models.Contrato(
                codigo="ALQ-2024-006",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p6.id, inquilino_id=in1.id,
                fecha_inicio=date(2024, 8, 1), fecha_fin=date(2026, 7, 31),
                monto_inicial=550000, deposito=550000,
                indice_ajuste=models.IndiceAjuste.fijo, porcentaje_fijo=8,
                periodicidad_meses=4, comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2024-007",
                tipo=models.ContratoTipo.alquiler_comercial,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p7.id, inquilino_id=in5.id,
                fecha_inicio=date(2024, 2, 1), fecha_fin=date(2027, 1, 31),
                monto_inicial=900000, deposito=2700000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=6,
                comision_porc=8, notas="Contrato comercial de 3 años.",
            ),
            # Próximo a vencer (alerta)
            models.Contrato(
                codigo="ALQ-2024-008",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p2.id, inquilino_id=in3.id,
                fecha_inicio=date(2023, 6, 1),
                fecha_fin=date.today() + timedelta(days=18),
                monto_inicial=280000, deposito=280000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5, notas="VENCE PRONTO — renovar o buscar nuevo inquilino.",
            ),
            # Crítico: vence en 5 días
            models.Contrato(
                codigo="ALQ-2024-009",
                tipo=models.ContratoTipo.alquiler_comercial,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p8.id, inquilino_id=in2.id,
                fecha_inicio=date(2023, 5, 1),
                fecha_fin=date.today() + timedelta(days=5),
                monto_inicial=580000, deposito=1160000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=6,
                comision_porc=8, notas="CRÍTICO — vence en menos de una semana.",
            ),
            # Vencido
            models.Contrato(
                codigo="ALQ-2023-010",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vencido,
                propiedad_id=p9.id, inquilino_id=in4.id,
                fecha_inicio=date(2022, 1, 1), fecha_fin=date(2024, 12, 31),
                monto_inicial=180000, deposito=180000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5,
            ),
            # Borrador
            models.Contrato(
                codigo="ALQ-2026-011",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.borrador,
                propiedad_id=p10.id, inquilino_id=None,
                fecha_inicio=date(2026, 6, 1), fecha_fin=date(2029, 5, 31),
                monto_inicial=330000, deposito=330000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5, notas="Esperando firma. Inquilino por confirmar.",
            ),
            # Boleto de compraventa
            models.Contrato(
                codigo="BOL-2026-001",
                tipo=models.ContratoTipo.boleto_compraventa,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p13.id, inquilino_id=co1.id,
                fecha_inicio=date(2026, 3, 15), fecha_fin=date(2026, 9, 15),
                monto_inicial=210000, deposito=21000,
                indice_ajuste=models.IndiceAjuste.sin_ajuste,
                periodicidad_meses=1, comision_porc=3,
                notas="Señado $21.000 USD. Escritura en Septiembre 2026.",
            ),
        ]
        db.add_all(contratos)
        db.commit()

        c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12 = contratos

        # ──────────────────────────────────────────────
        # PAGOS — historial para contratos vigentes
        # ──────────────────────────────────────��───────

        # Contrato ALQ-2024-001 — 14 meses de historial
        pagos_c1 = [
            ("2024-03", date(2024,3,10), date(2024,3,8),  350000, 85000, 14000, 9500,  "pagado"),
            ("2024-04", date(2024,4,10), date(2024,4,9),  350000, 85000, 14000, 9500,  "pagado"),
            ("2024-05", date(2024,5,10), date(2024,5,7),  350000, 87000, 14000, 9500,  "pagado"),
            ("2024-06", date(2024,6,10), date(2024,7,1),  385000, 87000, 14000, 9500,  "pagado"),  # ajuste IPC
            ("2024-07", date(2024,7,10), date(2024,7,11), 385000, 88000, 14000, 9500,  "pagado"),
            ("2024-08", date(2024,8,10), date(2024,8,9),  385000, 88000, 14000, 9500,  "pagado"),
            ("2024-09", date(2024,9,10), date(2024,9,12), 420000, 90000, 14000, 9500,  "pagado"),  # ajuste
            ("2024-10", date(2024,10,10),date(2024,10,9), 420000, 90000, 14000, 9500,  "pagado"),
            ("2024-11", date(2024,11,10),date(2024,11,8), 420000, 91000, 14000, 9500,  "pagado"),
            ("2024-12", date(2024,12,10),date(2024,12,10),462000, 91000, 14000, 9500,  "pagado"),  # ajuste
            ("2025-01", date(2025,1,10), date(2025,1,9),  462000, 92000, 14500, 9800,  "pagado"),
            ("2025-02", date(2025,2,10), date(2025,2,11), 462000, 92000, 14500, 9800,  "pagado"),
            ("2025-03", date(2025,3,10), date(2025,3,10), 508200, 92000, 14500, 9800,  "pagado"),  # ajuste
            ("2025-04", date(2025,4,10), None,            508200, 93000, 14500, 9800,  "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c1:
            _pago(db, c1.id, per, vence, pago, alq, exp, imp, mun, est)

        # Contrato ALQ-2024-005 — casa premium
        pagos_c5 = [
            ("2024-05", date(2024,5,10), date(2024,5,8),  750000, 0, 42000, 28000, "pagado"),
            ("2024-06", date(2024,6,10), date(2024,6,9),  750000, 0, 42000, 28000, "pagado"),
            ("2024-07", date(2024,7,10), date(2024,7,10), 750000, 0, 42000, 28000, "pagado"),
            ("2024-08", date(2024,8,10), date(2024,8,12), 825000, 0, 42000, 28000, "pagado"),
            ("2024-09", date(2024,9,10), date(2024,9,9),  825000, 0, 42000, 28000, "pagado"),
            ("2024-10", date(2024,10,10),date(2024,10,10),825000, 0, 42000, 28000, "pagado"),
            ("2024-11", date(2024,11,10),date(2024,11,9), 907500, 0, 42000, 28000, "pagado"),
            ("2024-12", date(2024,12,10),date(2024,12,11),907500, 0, 43000, 29000, "pagado"),
            ("2025-01", date(2025,1,10), date(2025,1,9),  907500, 0, 43000, 29000, "pagado"),
            ("2025-02", date(2025,2,10), date(2025,2,10), 998250, 0, 43000, 29000, "pagado"),
            ("2025-03", date(2025,3,10), date(2025,3,9),  998250, 0, 43000, 29000, "pagado"),
            ("2025-04", date(2025,4,10), None,            998250, 0, 43000, 29000, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c5:
            _pago(db, c5.id, per, vence, pago, alq, exp, imp, mun, est)

        # Contrato ALQ-2024-007 — local gastronómico
        pagos_c7 = [
            ("2024-02", date(2024,2,5), date(2024,2,4),   900000, 0, 32000, 22000, "pagado"),
            ("2024-03", date(2024,3,5), date(2024,3,5),   900000, 0, 32000, 22000, "pagado"),
            ("2024-04", date(2024,4,5), date(2024,4,10),  900000, 0, 32000, 22000, "pagado"),
            ("2024-05", date(2024,5,5), date(2024,5,4),   900000, 0, 32000, 22000, "pagado"),
            ("2024-06", date(2024,6,5), date(2024,6,5),   990000, 0, 32000, 22000, "pagado"),
            ("2024-07", date(2024,7,5), date(2024,7,7),   990000, 0, 32000, 22000, "pagado"),
            ("2024-08", date(2024,8,5), date(2024,8,5),   990000, 0, 33000, 23000, "pagado"),
            ("2024-09", date(2024,9,5), date(2024,9,18), 1089000, 0, 33000, 23000, "pagado"),  # 2 días tarde
            ("2024-10", date(2024,10,5),date(2024,10,5), 1089000, 0, 33000, 23000, "pagado"),
            ("2024-11", date(2024,11,5),date(2024,11,4), 1089000, 0, 33000, 23000, "pagado"),
            ("2024-12", date(2024,12,5),date(2024,12,5), 1197900, 0, 33000, 23000, "pagado"),
            ("2025-01", date(2025,1,5), date(2025,1,5),  1197900, 0, 33000, 23000, "pagado"),
            ("2025-02", date(2025,2,5), date(2025,2,7),  1197900, 0, 33000, 23000, "pagado"),
            ("2025-03", date(2025,3,5), None,            1317690, 0, 33000, 23000, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c7:
            _pago(db, c7.id, per, vence, pago, alq, exp, imp, mun, est)

        # Contrato ALQ-2023-010 — vencido, todos pagados
        pagos_c10 = [
            ("2023-01", date(2023,1,10), date(2023,1,9),  180000, 55000, 10000, 7000, "pagado"),
            ("2023-02", date(2023,2,10), date(2023,2,10), 180000, 55000, 10000, 7000, "pagado"),
            ("2023-03", date(2023,3,10), date(2023,3,11), 180000, 57000, 10000, 7000, "pagado"),
            ("2023-06", date(2023,6,10), date(2023,6,9),  198000, 57000, 10500, 7200, "pagado"),
            ("2023-09", date(2023,9,10), date(2023,9,10), 217800, 60000, 11000, 7500, "pagado"),
            ("2023-12", date(2023,12,10),date(2023,12,9), 239580, 62000, 11500, 7800, "pagado"),
            ("2024-03", date(2024,3,10), date(2024,3,12), 263538, 64000, 12000, 8000, "pagado"),
            ("2024-06", date(2024,6,10), date(2024,6,10), 289892, 66000, 12500, 8200, "pagado"),
            ("2024-09", date(2024,9,10), date(2024,9,9),  318881, 68000, 13000, 8500, "pagado"),
            ("2024-12", date(2024,12,10),date(2024,12,10),350769, 70000, 13500, 8800, "pagado"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c10:
            _pago(db, c10.id, per, vence, pago, alq, exp, imp, mun, est)

        # Contrato ALQ-2024-002 — un vencido, resto pagados
        pagos_c2 = [
            ("2024-07", date(2024,7,10), date(2024,7,9),  300000, 78000, 11000, 7500, "pagado"),
            ("2024-08", date(2024,8,10), date(2024,8,9),  300000, 78000, 11000, 7500, "pagado"),
            ("2024-09", date(2024,9,10), date(2024,9,12), 330000, 79000, 11000, 7500, "pagado"),
            ("2024-10", date(2024,10,10),date(2024,10,9), 330000, 79000, 11000, 7500, "pagado"),
            ("2024-11", date(2024,11,10),None,            330000, 80000, 11000, 7500, "vencido"),
            ("2024-12", date(2024,12,10),date(2024,12,11),363000, 80000, 11000, 7500, "pagado"),
            ("2025-01", date(2025,1,10), date(2025,1,10), 363000, 80000, 11500, 7800, "pagado"),
            ("2025-02", date(2025,2,10), date(2025,2,9),  363000, 81000, 11500, 7800, "pagado"),
            ("2025-03", date(2025,3,10), None,            399300, 81000, 11500, 7800, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c2:
            _pago(db, c2.id, per, vence, pago, alq, exp, imp, mun, est)

        db.commit()

        print("Seed demo completado:")
        print("   -> 4 usuarios  (admin / alquileres / ventas / agente - todos: ciudad1234)")
        print("   -> 12 clientes")
        print("   -> 16 propiedades")
        print("   -> 12 contratos  (vigentes / borrador / vencido / boleto)")
        print("   -> Historial de pagos en 5 contratos")
        print("   -> 2 contratos con alerta de vencimiento proximo")

    finally:
        db.close()


if __name__ == "__main__":
    run()
