"""
Seed de datos demo para CIUDAD. Inmobiliaria - Santa Rosa, La Pampa.
Genera usuarios, clientes (incluyendo fiadores), propiedades en Santa Rosa,
contratos con campos completos del modelo CIUDAD, pagos y ajustes.
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


INV_DEPTO_DEFAULT = (
    "SPLIT frio/calor con control remoto, termotanque electrico 47lt, "
    "cocina 4 hornallas a gas, extractor de aire, juego de bajomesada con "
    "puertas y cajoneras, alacena, portero electrico, juego de bano y griferia, "
    "espejo con marco. Iluminaria: apliques de vidrio en living, dormitorios y "
    "pasillo, tulipa de vidrio en bano, tubos fluorescentes en cocina. "
    "Departamento pintado al latex blanco - debera devolverse en mismas condiciones."
)


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            print("Seed ya ejecutado.")
            return

        # ── USUARIOS ──
        admin = models.User(
            nombre="Sofia Ramirez", email="admin@ciudad.com",
            telefono="+54 9 2954 50-0001",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.admin,
        )
        operador = models.User(
            nombre="Nicolas Torres", email="alquileres@ciudad.com",
            telefono="+54 9 2954 50-0002",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.alquileres,
        )
        finanzas = models.User(
            nombre="Valentina Diaz", email="ventas@ciudad.com",
            telefono="+54 9 2954 50-0003",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.ventas,
        )
        agente = models.User(
            nombre="Mateo Sanchez", email="agente@ciudad.com",
            telefono="+54 9 2954 50-0004",
            password_hash=hash_pw("ciudad1234"),
            role=models.UserRole.agente_ia,
        )
        db.add_all([admin, operador, finanzas, agente])
        db.commit()

        # ── PROPIETARIOS ──
        pr1 = models.Cliente(
            nombre="Maria Elena", apellido="Gonzalez",
            documento="27-12345678-9", email="mgonzalez@gmail.com",
            telefono="+54 9 2954 60-1001",
            rol=models.ClienteRol.propietario,
            nacionalidad="Argentina",
            direccion="Avellaneda 845", localidad="Santa Rosa", provincia="La Pampa",
            notas="Propietaria de varios departamentos en zona centro.",
        )
        pr2 = models.Cliente(
            nombre="Roberto", apellido="Fernandez",
            documento="20-98765432-1", email="rfernandez@outlook.com",
            telefono="+54 9 2954 60-1002",
            rol=models.ClienteRol.propietario,
            nacionalidad="Argentino",
            direccion="Lisandro de la Torre 1290", localidad="Santa Rosa", provincia="La Pampa",
        )
        pr3 = models.Cliente(
            nombre="Inversiones Del Sur", apellido="",
            razon_social="Inversiones Del Sur S.R.L.",
            documento="30-71234567-8", email="admin@inversionesdelsur.com",
            telefono="+54 9 2954 60-1003",
            rol=models.ClienteRol.propietario,
            direccion="Av. Roca 530, Piso 2", localidad="Santa Rosa", provincia="La Pampa",
            notas="Empresa con 6 inmuebles en cartera.",
        )
        pr4 = models.Cliente(
            nombre="Claudia", apellido="Morales",
            documento="27-44567890-3", email="cmorales@yahoo.com.ar",
            telefono="+54 9 2954 60-1004",
            rol=models.ClienteRol.propietario,
            nacionalidad="Argentina",
            direccion="Pasaje Trumao 215", localidad="Toay", provincia="La Pampa",
        )

        # ── INQUILINOS ──
        in1 = models.Cliente(
            nombre="Juan Ignacio", apellido="Lopez",
            documento="20-22222222-2", email="jilopez@gmail.com",
            telefono="+54 9 2954 70-2001",
            rol=models.ClienteRol.inquilino,
            nacionalidad="Argentino",
            direccion="Belgrano 1255", localidad="Santa Rosa", provincia="La Pampa",
        )
        in2 = models.Cliente(
            nombre="Ana Paula", apellido="Ruiz",
            documento="27-33333333-3", email="apruiz@gmail.com",
            telefono="+54 9 2954 70-2002",
            rol=models.ClienteRol.inquilino,
            nacionalidad="Argentina",
            direccion="Mitre 985", localidad="Santa Rosa", provincia="La Pampa",
        )
        in3 = models.Cliente(
            nombre="Diego", apellido="Herrera",
            documento="20-44444444-4", email="dherrera@hotmail.com",
            telefono="+54 9 2954 70-2003",
            rol=models.ClienteRol.inquilino,
            nacionalidad="Argentino",
            direccion="9 de Julio 122", localidad="Santa Rosa", provincia="La Pampa",
        )
        in4 = models.Cliente(
            nombre="Lucia", apellido="Martinez",
            documento="27-55555555-5", email="lmartinez@gmail.com",
            telefono="+54 9 2954 70-2004",
            rol=models.ClienteRol.inquilino,
            nacionalidad="Argentina",
            direccion="Coronel Gil 855", localidad="Santa Rosa", provincia="La Pampa",
        )
        in5 = models.Cliente(
            nombre="Restaurante El Caldenal", apellido="",
            razon_social="El Caldenal Gastronomia S.A.S.",
            documento="30-88776655-4", email="contacto@elcaldenal.com.ar",
            telefono="+54 9 2954 70-2005",
            rol=models.ClienteRol.inquilino,
            direccion="Av. San Martin 410", localidad="Santa Rosa", provincia="La Pampa",
            notas="Local gastronomico. Contrato comercial.",
        )
        in6 = models.Cliente(
            nombre="Martin", apellido="Gomez",
            documento="20-66666666-6", email="mgomez@gmail.com",
            telefono="+54 9 2954 70-2006",
            rol=models.ClienteRol.inquilino,
            nacionalidad="Argentino",
            direccion="Sarmiento 405", localidad="Santa Rosa", provincia="La Pampa",
        )

        # ── COMPRADOR / VENDEDOR ──
        co1 = models.Cliente(
            nombre="Patricia", apellido="Vega",
            documento="27-77777777-7", email="pvega@gmail.com",
            telefono="+54 9 2954 80-3001",
            rol=models.ClienteRol.comprador,
            nacionalidad="Argentina",
            direccion="Don Bosco 1240", localidad="Santa Rosa", provincia="La Pampa",
        )
        ve1 = models.Cliente(
            nombre="Hector", apellido="Ibanez",
            documento="20-88888888-8", email="hibanez@gmail.com",
            telefono="+54 9 2954 80-3002",
            rol=models.ClienteRol.vendedor,
            nacionalidad="Argentino",
            direccion="Spinetto 765", localidad="Santa Rosa", provincia="La Pampa",
        )

        # ── GARANTES ──
        ga1 = models.Cliente(
            nombre="Marin Rosa Isabel", apellido="Montecinos",
            documento="27-29761131-1", email="marin.montecinos@gmail.com",
            telefono="+54 9 2954 90-4001",
            rol=models.ClienteRol.garante,
            nacionalidad="Argentina",
            direccion="Santa Teresa 472", localidad="25 de Mayo", provincia="La Pampa",
            notas="Recibo de sueldo actualizado. Trabajadora estatal.",
        )
        ga2 = models.Cliente(
            nombre="Diego Fernando", apellido="Vacirca",
            documento="20-28847125-1", email="d.vacirca@gmail.com",
            telefono="+54 9 2954 90-4002",
            rol=models.ClienteRol.garante,
            nacionalidad="Argentino",
            direccion="Santa Teresa 472", localidad="25 de Mayo", provincia="La Pampa",
            notas="Recibo de sueldo actualizado. Empleado en relacion de dependencia.",
        )
        ga3 = models.Cliente(
            nombre="Carlos Alberto", apellido="Saavedra",
            documento="20-15876543-2", email="csaavedra@gmail.com",
            telefono="+54 9 2954 90-4003",
            rol=models.ClienteRol.garante,
            nacionalidad="Argentino",
            direccion="Quintana 380", localidad="General Pico", provincia="La Pampa",
        )
        ga4 = models.Cliente(
            nombre="Silvia Graciela", apellido="Ortega",
            documento="27-17234568-3", email="sortega@hotmail.com",
            telefono="+54 9 2954 90-4004",
            rol=models.ClienteRol.garante,
            nacionalidad="Argentina",
            direccion="Belgrano 654", localidad="Santa Rosa", provincia="La Pampa",
        )

        db.add_all([pr1, pr2, pr3, pr4, in1, in2, in3, in4, in5, in6, co1, ve1, ga1, ga2, ga3, ga4])
        db.commit()

        # ── PROPIEDADES (todas en La Pampa) ──
        props = [
            models.Propiedad(
                codigo="DEP-001", direccion="Coronel Gil 393, Piso 8 Dto. C - Edif. Pampa",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=72, ambientes=3,
                descripcion="Departamento luminoso en zona centrica. Dos dormitorios con placar, bano completo, cocina-comedor, pasillo y living. Pintado al latex blanco. Incluye SPLIT frio/calor, termotanque, cocina, extractor, bajomesada y alacena.",
                precio_alquiler=600000, expensas=42000,
                impuesto_inmobiliario=8500, tasa_municipal=4500,
                propietario_id=pr1.id,
            ),
            models.Propiedad(
                codigo="DEP-002", direccion="Avellaneda 845, Piso 2 Dto. B",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=48, ambientes=2,
                descripcion="Dos ambientes al frente. Edificio con cochera privada. Excelente ubicacion sobre Avellaneda.",
                precio_alquiler=420000, expensas=35000,
                impuesto_inmobiliario=6500, tasa_municipal=3800,
                propietario_id=pr1.id,
            ),
            models.Propiedad(
                codigo="DEP-003", direccion="Av. Roca 530, Piso 5 Dto. A",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=85, ambientes=3,
                descripcion="Tres ambientes con cochera cubierta. Edificio con SUM y portero electrico. Apto credito.",
                precio_alquiler=720000, expensas=58000,
                impuesto_inmobiliario=10500, tasa_municipal=6200,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="DEP-004", direccion="Lisandro de la Torre 1290 PB",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=42, ambientes=1,
                descripcion="Monoambiente reciclado a nuevo. Ideal estudiante UNLPam o profesional.",
                precio_alquiler=320000, expensas=22000,
                impuesto_inmobiliario=4500, tasa_municipal=2800,
                propietario_id=pr2.id,
            ),
            # Casas
            models.Propiedad(
                codigo="CAS-005", direccion="Pasaje Trumao 215",
                ciudad="Toay", provincia="La Pampa",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=180, ambientes=5,
                descripcion="Casa con jardin, quincho y parrilla. 3 dormitorios. Cochera doble cubierta.",
                precio_alquiler=850000, expensas=0,
                impuesto_inmobiliario=22000, tasa_municipal=15000,
                propietario_id=pr4.id,
            ),
            models.Propiedad(
                codigo="CAS-006", direccion="Quintana 380",
                ciudad="General Pico", provincia="La Pampa",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=140, ambientes=4,
                descripcion="Casa de tres dormitorios en barrio residencial. Patio amplio.",
                precio_alquiler=580000, expensas=0,
                impuesto_inmobiliario=14000, tasa_municipal=9500,
                propietario_id=pr2.id,
            ),
            # Locales
            models.Propiedad(
                codigo="LOC-007", direccion="Av. San Martin 410",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.local,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.ocupada,
                superficie_m2=85,
                descripcion="Local sobre Av. San Martin. Doble vidriera, deposito al fondo. Apto gastronomia.",
                precio_alquiler=950000, expensas=0,
                impuesto_inmobiliario=18000, tasa_municipal=12500,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="LOC-008", direccion="Pellegrini 245 Local 3",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.local,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.reservada,
                superficie_m2=32,
                descripcion="Local en galeria comercial centrica. Buen transito peatonal.",
                precio_alquiler=480000, expensas=28000,
                impuesto_inmobiliario=10000, tasa_municipal=6500,
                propietario_id=pr1.id,
            ),
            # Disponibles
            models.Propiedad(
                codigo="DEP-009", direccion="Av. Spinetto 765, Piso 3 Dto. D",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=78, ambientes=3,
                descripcion="Tres ambientes al contrafrente. Cocina equipada, balcon. Cochera por separado.",
                precio_alquiler=680000, expensas=48000,
                impuesto_inmobiliario=10000, tasa_municipal=6000,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="DEP-010", direccion="Belgrano 1255, Piso 1 Dto. A",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=44, ambientes=2,
                descripcion="Dos ambientes reciclado. Cerca de la zona universitaria.",
                precio_alquiler=380000, expensas=30000,
                impuesto_inmobiliario=5500, tasa_municipal=3500,
                propietario_id=pr4.id,
            ),
            models.Propiedad(
                codigo="CAS-011", direccion="Sarmiento 405",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=110, ambientes=4,
                descripcion="Casa independiente con patio y cochera cubierta. 3 dormitorios.",
                precio_alquiler=520000, expensas=0,
                impuesto_inmobiliario=12000, tasa_municipal=8500,
                propietario_id=pr2.id,
            ),
            # Venta
            models.Propiedad(
                codigo="VEN-012", direccion="Av. Belgrano 1480, Piso 9 Dto. B",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.venta,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=130, ambientes=4,
                descripcion="Cuatro ambientes con dos cocheras. Edificio premium con SUM y gimnasio.",
                precio_venta=145000, tokko_id="TKO-9981",
                propietario_id=pr2.id,
            ),
            models.Propiedad(
                codigo="VEN-013", direccion="Coronel Gil 1180, Piso 3 Dto. C",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.departamento,
                modalidad=models.PropiedadModalidad.venta,
                estado=models.PropiedadEstado.reservada,
                superficie_m2=88, ambientes=3,
                descripcion="Tres ambientes reciclado a nuevo. Ubicacion centrica.",
                precio_venta=95000, tokko_id="TKO-9982",
                propietario_id=pr1.id,
            ),
            models.Propiedad(
                codigo="CAS-014", direccion="9 de Julio 122",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.casa,
                modalidad=models.PropiedadModalidad.ambas,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=200, ambientes=5,
                descripcion="Casa en esquina con local comercial al frente. Tambien disponible para alquiler.",
                precio_alquiler=720000, precio_venta=88000,
                impuesto_inmobiliario=18000, tasa_municipal=13000,
                propietario_id=pr4.id,
            ),
            # Campo
            models.Propiedad(
                codigo="CMP-015", direccion="Ruta 5 km 218",
                ciudad="Catrilo", provincia="La Pampa",
                tipo=models.PropiedadTipo.campo,
                modalidad=models.PropiedadModalidad.venta,
                estado=models.PropiedadEstado.disponible,
                superficie_m2=2_500_000,
                descripcion="Campo agricola-ganadero de 250 ha. Apto soja/maiz/girasol. Casco con casa principal y galpones.",
                precio_venta=1_800_000,
                propietario_id=pr3.id,
            ),
            models.Propiedad(
                codigo="LOC-016", direccion="Mitre 985",
                ciudad="Santa Rosa", provincia="La Pampa",
                tipo=models.PropiedadTipo.local,
                modalidad=models.PropiedadModalidad.alquiler,
                estado=models.PropiedadEstado.inactiva,
                superficie_m2=70,
                descripcion="Local en zona centrica. En refaccion, disponible desde julio 2026.",
                precio_alquiler=620000,
                impuesto_inmobiliario=14000, tasa_municipal=9500,
                propietario_id=pr3.id,
            ),
        ]
        db.add_all(props)
        db.commit()

        p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15, p16 = props

        # ── CONTRATOS (modelo CIUDAD Santa Rosa: 1 ano, fiadores, pagare, etc.) ──
        contratos = [
            # Contrato modelo (replica del MODELO ALQUILERES FEDE)
            models.Contrato(
                codigo="ALQ-2026-001",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p1.id, inquilino_id=in1.id,
                fiador_id=ga1.id, fiador2_id=ga2.id,
                fecha_inicio=date(2026, 3, 1), fecha_fin=date(2027, 2, 28),
                monto_inicial=600000, deposito=600000,
                pagare_refuerzo=8_000_000,
                inventario=INV_DEPTO_DEFAULT,
                seguro_obligatorio=True, permite_mascotas=False,
                punicion_diaria_porc=1.0, dia_pago_desde=1, dia_pago_hasta=7,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=3,
                comision_porc=5,
                notas="Contrato bajo modelo CIUDAD. Pintura latex blanco a devolver igual.",
            ),
            models.Contrato(
                codigo="ALQ-2025-002",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p2.id, inquilino_id=in2.id,
                fiador_id=ga3.id,
                fecha_inicio=date(2025, 7, 1), fecha_fin=date(2026, 6, 30),
                monto_inicial=420000, deposito=420000,
                pagare_refuerzo=5_000_000,
                seguro_obligatorio=True, permite_mascotas=False,
                punicion_diaria_porc=1.0, dia_pago_desde=1, dia_pago_hasta=7,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=3,
                comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2025-003",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p3.id, inquilino_id=in3.id,
                fiador_id=ga4.id,
                fecha_inicio=date(2025, 10, 1), fecha_fin=date(2026, 9, 30),
                monto_inicial=720000, deposito=720000,
                pagare_refuerzo=10_000_000,
                seguro_obligatorio=True, permite_mascotas=True,
                punicion_diaria_porc=1.0, dia_pago_desde=1, dia_pago_hasta=7,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2025-004",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p4.id, inquilino_id=in6.id,
                fiador_id=ga1.id,
                fecha_inicio=date(2025, 12, 1), fecha_fin=date(2026, 11, 30),
                monto_inicial=320000, deposito=320000,
                pagare_refuerzo=3_500_000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=3,
                comision_porc=5,
            ),
            models.Contrato(
                codigo="ALQ-2025-005",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p5.id, inquilino_id=in4.id,
                fiador_id=ga2.id, fiador2_id=ga3.id,
                fecha_inicio=date(2025, 5, 1), fecha_fin=date(2026, 4, 30),
                monto_inicial=850000, deposito=1_700_000,
                pagare_refuerzo=12_000_000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=4,
                notas="Casa premium en Toay. Deposito reforzado.",
            ),
            models.Contrato(
                codigo="ALQ-2025-006",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p6.id, inquilino_id=in1.id,
                fiador_id=ga4.id,
                fecha_inicio=date(2025, 8, 1), fecha_fin=date(2026, 7, 31),
                monto_inicial=580000, deposito=580000,
                pagare_refuerzo=7_000_000,
                indice_ajuste=models.IndiceAjuste.fijo, porcentaje_fijo=8,
                periodicidad_meses=4, comision_porc=5,
            ),
            # Comercial
            models.Contrato(
                codigo="ALQ-2025-007",
                tipo=models.ContratoTipo.alquiler_comercial,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p7.id, inquilino_id=in5.id,
                fiador_id=ga2.id,
                fecha_inicio=date(2025, 2, 1), fecha_fin=date(2028, 1, 31),
                monto_inicial=950000, deposito=2_850_000,
                pagare_refuerzo=15_000_000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=6,
                comision_porc=8, notas="Contrato comercial 3 anos - gastronomia.",
            ),
            # Proximos a vencer
            models.Contrato(
                codigo="ALQ-2025-008",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p2.id, inquilino_id=in3.id,
                fiador_id=ga1.id,
                fecha_inicio=date(2024, 6, 1),
                fecha_fin=date.today() + timedelta(days=18),
                monto_inicial=300000, deposito=300000,
                pagare_refuerzo=3_500_000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5, notas="VENCE PRONTO - renovar o buscar nuevo inquilino.",
            ),
            models.Contrato(
                codigo="ALQ-2025-009",
                tipo=models.ContratoTipo.alquiler_comercial,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p8.id, inquilino_id=in2.id,
                fiador_id=ga3.id,
                fecha_inicio=date(2024, 5, 1),
                fecha_fin=date.today() + timedelta(days=5),
                monto_inicial=380000, deposito=760000,
                pagare_refuerzo=5_000_000,
                indice_ajuste=models.IndiceAjuste.icl, periodicidad_meses=6,
                comision_porc=8, notas="CRITICO - vence en menos de una semana.",
            ),
            # Vencido
            models.Contrato(
                codigo="ALQ-2024-010",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.vencido,
                propiedad_id=p9.id, inquilino_id=in4.id,
                fiador_id=ga4.id,
                fecha_inicio=date(2023, 1, 1), fecha_fin=date(2023, 12, 31),
                monto_inicial=180000, deposito=180000,
                pagare_refuerzo=2_500_000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5,
            ),
            # Borrador
            models.Contrato(
                codigo="ALQ-2026-011",
                tipo=models.ContratoTipo.alquiler_vivienda,
                estado=models.ContratoEstado.borrador,
                propiedad_id=p10.id, inquilino_id=None,
                fecha_inicio=date(2026, 6, 1), fecha_fin=date(2027, 5, 31),
                monto_inicial=380000, deposito=380000,
                pagare_refuerzo=4_000_000,
                indice_ajuste=models.IndiceAjuste.ipc, periodicidad_meses=3,
                comision_porc=5, notas="Esperando firma. Inquilino y fiador por confirmar.",
            ),
            # Boleto compraventa
            models.Contrato(
                codigo="BOL-2026-001",
                tipo=models.ContratoTipo.boleto_compraventa,
                estado=models.ContratoEstado.vigente,
                propiedad_id=p13.id, inquilino_id=co1.id,
                fecha_inicio=date(2026, 3, 15), fecha_fin=date(2026, 9, 15),
                monto_inicial=95000, deposito=9500,
                indice_ajuste=models.IndiceAjuste.sin_ajuste,
                periodicidad_meses=1, comision_porc=3,
                notas="Senado USD 9.500. Escritura traslativa Septiembre 2026.",
            ),
        ]
        db.add_all(contratos)
        db.commit()

        c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12 = contratos

        # ── PAGOS - historial parcial para los principales ──
        pagos_c1 = [
            ("2026-03", date(2026,3,7),  date(2026,3,5),  600000, 42000,  8500, 4500, "pagado"),
            ("2026-04", date(2026,4,7),  date(2026,4,6),  600000, 43500,  8500, 4500, "pagado"),
            ("2026-05", date(2026,5,7),  None,            600000, 44000,  8500, 4500, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c1:
            _pago(db, c1.id, per, vence, pago, alq, exp, imp, mun, est)

        pagos_c5 = [
            ("2025-05", date(2025,5,7),  date(2025,5,6),  850000, 0, 22000, 15000, "pagado"),
            ("2025-06", date(2025,6,7),  date(2025,6,7),  850000, 0, 22000, 15000, "pagado"),
            ("2025-07", date(2025,7,7),  date(2025,7,7),  850000, 0, 22000, 15000, "pagado"),
            ("2025-08", date(2025,8,7),  date(2025,8,9),  935000, 0, 22000, 15000, "pagado"),
            ("2025-09", date(2025,9,7),  date(2025,9,5),  935000, 0, 22000, 15000, "pagado"),
            ("2025-10", date(2025,10,7), date(2025,10,7), 935000, 0, 22500, 15500, "pagado"),
            ("2025-11", date(2025,11,7), date(2025,11,6),1028500, 0, 22500, 15500, "pagado"),
            ("2025-12", date(2025,12,7), date(2025,12,7),1028500, 0, 23000, 16000, "pagado"),
            ("2026-01", date(2026,1,7),  date(2026,1,9), 1028500, 0, 23000, 16000, "pagado"),
            ("2026-02", date(2026,2,7),  date(2026,2,5), 1131350, 0, 23000, 16000, "pagado"),
            ("2026-03", date(2026,3,7),  date(2026,3,7), 1131350, 0, 23500, 16500, "pagado"),
            ("2026-04", date(2026,4,7),  date(2026,4,7), 1131350, 0, 23500, 16500, "pagado"),
            ("2026-05", date(2026,5,7),  None,           1244485, 0, 23500, 16500, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c5:
            _pago(db, c5.id, per, vence, pago, alq, exp, imp, mun, est)

        pagos_c7 = [
            ("2025-02", date(2025,2,7),  date(2025,2,5),  950000, 0, 18000, 12500, "pagado"),
            ("2025-03", date(2025,3,7),  date(2025,3,7),  950000, 0, 18000, 12500, "pagado"),
            ("2025-04", date(2025,4,7),  date(2025,4,9),  950000, 0, 18000, 12500, "pagado"),
            ("2025-05", date(2025,5,7),  date(2025,5,5),  950000, 0, 18000, 12500, "pagado"),
            ("2025-06", date(2025,6,7),  date(2025,6,7),  950000, 0, 18000, 12500, "pagado"),
            ("2025-07", date(2025,7,7),  date(2025,7,7), 1045000, 0, 18500, 13000, "pagado"),
            ("2025-08", date(2025,8,7),  date(2025,8,8), 1045000, 0, 18500, 13000, "pagado"),
            ("2025-09", date(2025,9,7),  date(2025,9,15),1045000, 0, 18500, 13000, "pagado"),
            ("2025-10", date(2025,10,7), date(2025,10,7),1045000, 0, 19000, 13500, "pagado"),
            ("2025-11", date(2025,11,7), date(2025,11,7),1045000, 0, 19000, 13500, "pagado"),
            ("2025-12", date(2025,12,7), date(2025,12,7),1045000, 0, 19000, 13500, "pagado"),
            ("2026-01", date(2026,1,7),  date(2026,1,7), 1149500, 0, 19500, 14000, "pagado"),
            ("2026-02", date(2026,2,7),  date(2026,2,9), 1149500, 0, 19500, 14000, "pagado"),
            ("2026-03", date(2026,3,7),  None,           1149500, 0, 19500, 14000, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c7:
            _pago(db, c7.id, per, vence, pago, alq, exp, imp, mun, est)

        pagos_c2 = [
            ("2025-07", date(2025,7,7),  date(2025,7,6),  420000, 30000, 6500, 3800, "pagado"),
            ("2025-08", date(2025,8,7),  date(2025,8,7),  420000, 31000, 6500, 3800, "pagado"),
            ("2025-09", date(2025,9,7),  date(2025,9,9),  462000, 31500, 6500, 3800, "pagado"),
            ("2025-10", date(2025,10,7), date(2025,10,7), 462000, 32000, 6500, 3800, "pagado"),
            ("2025-11", date(2025,11,7), None,            462000, 32500, 6500, 3800, "vencido"),
            ("2025-12", date(2025,12,7), date(2025,12,9), 508200, 32500, 7000, 4000, "pagado"),
            ("2026-01", date(2026,1,7),  date(2026,1,7),  508200, 33000, 7000, 4000, "pagado"),
            ("2026-02", date(2026,2,7),  date(2026,2,7),  508200, 33500, 7000, 4000, "pagado"),
            ("2026-03", date(2026,3,7),  None,            559020, 34000, 7000, 4000, "pendiente"),
        ]
        for per, vence, pago, alq, exp, imp, mun, est in pagos_c2:
            _pago(db, c2.id, per, vence, pago, alq, exp, imp, mun, est)

        db.commit()

        print("Seed CIUDAD Santa Rosa completado:")
        print("   -> 4 usuarios")
        print("   -> 16 clientes (propietarios, inquilinos, comprador/vendedor, 4 garantes)")
        print("   -> 16 propiedades en La Pampa (Santa Rosa, Toay, Gral. Pico, Catrilo)")
        print("   -> 12 contratos con fiadores, pagare refuerzo y clausulas modelo CIUDAD")
        print("   -> Historial de pagos en 4 contratos")

    finally:
        db.close()


if __name__ == "__main__":
    run()
