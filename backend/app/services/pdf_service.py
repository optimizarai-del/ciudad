"""
Generación de PDF de contratos con reportlab.
Tres plantillas: alquiler vivienda (Ley 27.551 / DNU 70/2023), alquiler comercial, boleto compraventa.
"""
import os
from io import BytesIO
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)


# Branding CIUDAD
BRAND_NAME = "CIUDAD"
BRAND_TAGLINE = "Negocios Inmobiliarios"
BRAND_SLOGAN = "#VIVIRMEJOR"

# Logo (JPG fondo negro). Se carga una sola vez.
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo-ciudad.jpg")
_LOGO_PATH = os.path.abspath(_LOGO_PATH)

def _logo():
    try:
        return ImageReader(_LOGO_PATH) if os.path.exists(_LOGO_PATH) else None
    except Exception:
        return None


# Paleta CIUDAD.
COLOR_NOCHE = HexColor("#0F1A2E")
COLOR_COBRE = HexColor("#B8893A")
COLOR_GRIS = HexColor("#737373")
COLOR_BORDE = HexColor("#E5E5E5")
COLOR_FONDO = HexColor("#F9F9F9")


TIPO_LABEL = {
    "alquiler_vivienda": "Contrato de Locación de Vivienda",
    "alquiler_comercial": "Contrato de Locación Comercial",
    "boleto_compraventa": "Boleto de Compraventa",
    "sena_alquiler": "Reserva / Seña de Alquiler",
}


INDICE_LABEL = {
    "ipc": "IPC (Índice de Precios al Consumidor — INDEC)",
    "icl": "ICL (Índice de Contratos de Locación — BCRA)",
    "fijo": "Porcentaje fijo establecido entre las partes",
    "sin_ajuste": "Sin ajuste",
}


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        name="CiudadTitle", fontName="Helvetica-Bold", fontSize=18,
        textColor=COLOR_NOCHE, spaceAfter=4, leading=22,
    ))
    s.add(ParagraphStyle(
        name="CiudadSubtitle", fontName="Helvetica", fontSize=9,
        textColor=COLOR_GRIS, spaceAfter=18, leading=12,
    ))
    s.add(ParagraphStyle(
        name="CiudadSection", fontName="Helvetica-Bold", fontSize=10,
        textColor=COLOR_COBRE, spaceBefore=10, spaceAfter=6, leading=14,
    ))
    s.add(ParagraphStyle(
        name="CiudadClause", fontName="Helvetica", fontSize=9.5,
        textColor=black, alignment=TA_JUSTIFY, leading=14, spaceAfter=8,
    ))
    s.add(ParagraphStyle(
        name="CiudadSmall", fontName="Helvetica", fontSize=8,
        textColor=COLOR_GRIS, leading=11, alignment=TA_CENTER,
    ))
    s.add(ParagraphStyle(
        name="CiudadSign", fontName="Helvetica", fontSize=9,
        textColor=black, alignment=TA_CENTER, spaceBefore=4,
    ))
    return s


def _header_footer(canvas, doc, codigo: str):
    canvas.saveState()
    width, height = A4

    # Header band negro
    canvas.setFillColor(COLOR_NOCHE)
    canvas.rect(0, height - 26 * mm, width, 26 * mm, fill=1, stroke=0)

    # Logo a la izquierda (cuadrado, JPG con fondo negro encaja directo en la banda)
    logo = _logo()
    if logo:
        canvas.drawImage(
            logo, 16 * mm, height - 23 * mm, width=18 * mm, height=18 * mm,
            preserveAspectRatio=True, mask='auto',
        )

    # Texto del header (al lado del logo)
    text_x = 38 * mm
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(text_x, height - 13 * mm, BRAND_NAME)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(text_x, height - 17 * mm, BRAND_TAGLINE.upper())
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(COLOR_COBRE)
    canvas.drawString(text_x, height - 21 * mm, BRAND_SLOGAN)

    # Código y fecha a la derecha
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawRightString(width - 18 * mm, height - 13 * mm, codigo or "")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(width - 18 * mm, height - 17 * mm,
                           f"Generado el {date.today().strftime('%d/%m/%Y')}")

    # Footer
    canvas.setFillColor(COLOR_FONDO)
    canvas.rect(0, 0, width, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(COLOR_GRIS)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 5 * mm, f"{BRAND_NAME} — {BRAND_TAGLINE} · {BRAND_SLOGAN}")
    canvas.drawRightString(width - 18 * mm, 5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _money(v):
    if not v:
        return "—"
    try:
        return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


def _fecha(v):
    if not v:
        return "—"
    if isinstance(v, str):
        return v
    try:
        return v.strftime("%d/%m/%Y")
    except Exception:
        return str(v)


def _tabla_partes(propiedad: dict, locador: dict, locatario: dict, styles, rol_locatario: str = "LOCATARIO/A"):
    rows = [
        ["Propiedad",
         f"{propiedad.get('direccion','—')}\n"
         f"{propiedad.get('ciudad','') or ''}{', ' + propiedad.get('provincia','') if propiedad.get('provincia') else ''}\n"
         f"Tipo: {propiedad.get('tipo','—')}"],
        ["LOCADOR/A (Propietario)" if rol_locatario != "COMPRADOR/A" else "VENDEDOR/A",
         f"{locador.get('nombre_completo','Sin asignar')}\n"
         f"DNI/CUIT: {locador.get('documento') or '—'}\n"
         f"{locador.get('email') or ''} · {locador.get('telefono') or ''}"],
        [rol_locatario,
         f"{locatario.get('nombre_completo','Sin asignar')}\n"
         f"DNI/CUIT: {locatario.get('documento') or '—'}\n"
         f"{locatario.get('email') or ''} · {locatario.get('telefono') or ''}"],
    ]
    t = Table(rows, colWidths=[45 * mm, 125 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_NOCHE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_FONDO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDE),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _tabla_condiciones(rows: list[tuple[str, str]]):
    data = [[k, v] for k, v in rows]
    t = Table(data, colWidths=[60 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_NOCHE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _firmas(rol_a: str, rol_b: str):
    sty = _styles()
    data = [
        ["", ""],
        ["_______________________", "_______________________"],
        [Paragraph(rol_a, sty["CiudadSign"]), Paragraph(rol_b, sty["CiudadSign"])],
    ]
    t = Table(data, colWidths=[85 * mm, 85 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 36),
    ]))
    return t


# ────────────────────────────────────────────────────────────────────
# Plantilla 1 — Alquiler Vivienda (Ley 27.551 + reformas DNU 70/2023)
# ────────────────────────────────────────────────────────────────────
def _plantilla_alquiler_vivienda(story, ctx, sty):
    c = ctx["contrato"]
    monto = _money(c.get("monto_inicial"))
    deposito = _money(c.get("deposito"))
    indice_lbl = INDICE_LABEL.get(c.get("indice_ajuste") or "ipc", "IPC")
    period = c.get("periodicidad_meses") or 3

    cl = lambda txt: Paragraph(txt, sty["CiudadClause"])
    sec = lambda txt: Paragraph(txt, sty["CiudadSection"])

    story += [
        sec("PRIMERA — OBJETO"),
        cl(f"EL/LA LOCADOR/A da en locación al/la LOCATARIO/A, quien acepta de conformidad, "
           f"el inmueble identificado como <b>{ctx['propiedad'].get('direccion','—')}</b>, "
           f"ubicado en {ctx['propiedad'].get('ciudad','—')}, con destino exclusivo a <b>vivienda familiar</b>. "
           f"Queda expresamente prohibido cualquier otro uso, así como la cesión total o parcial de la locación "
           f"o sublocación sin consentimiento previo y por escrito del/la LOCADOR/A."),

        sec("SEGUNDA — PLAZO"),
        cl(f"La locación se conviene por el plazo de <b>treinta y seis (36) meses</b>, conforme al artículo 1198 del "
           f"Código Civil y Comercial de la Nación, desde el {_fecha(c.get('fecha_inicio'))} hasta el "
           f"{_fecha(c.get('fecha_fin'))}, fecha en la cual el inmueble deberá ser restituido en las mismas "
           f"condiciones en que fue recibido, salvo el desgaste natural por el uso normal."),

        sec("TERCERA — PRECIO Y FORMA DE PAGO"),
        cl(f"El precio de la locación se conviene en la suma inicial de <b>{monto}</b> mensuales, pagaderos del "
           f"1 al 10 de cada mes en la cuenta o domicilio que indique el/la LOCADOR/A. La mora será automática "
           f"por el solo vencimiento del plazo, devengándose un interés punitorio equivalente a la tasa activa "
           f"del Banco de la Nación Argentina."),

        sec("CUARTA — ACTUALIZACIÓN DEL CANON"),
        cl(f"El canon locativo se actualizará en forma <b>{('semestral' if period == 6 else 'cuatrimestral' if period == 4 else 'trimestral' if period == 3 else 'mensual' if period == 1 else f'cada {period} meses')}</b> "
           f"aplicando como índice <b>{indice_lbl}</b>. La actualización operará automáticamente sin necesidad "
           f"de interpelación, notificación o intimación de ninguna especie. Las partes ratifican que esta cláusula "
           f"resulta esencial al consentimiento prestado."),

        sec("QUINTA — DEPÓSITO EN GARANTÍA"),
        cl(f"El/La LOCATARIO/A entrega en este acto, en concepto de depósito en garantía, la suma de <b>{deposito}</b>, "
           f"equivalente a un mes del canon locativo. Dicho depósito será restituido al término del contrato, en "
           f"valor equivalente al precio del último mes de alquiler, previa verificación del estado del inmueble y "
           f"cumplimiento de todas las obligaciones a cargo del/la LOCATARIO/A (servicios, expensas, impuestos, "
           f"reparaciones por daños, etc.)."),

        sec("SEXTA — EXPENSAS, SERVICIOS E IMPUESTOS"),
        cl("Estarán a cargo del/la LOCATARIO/A las expensas ordinarias y los servicios públicos del inmueble "
           "(luz, gas, agua, internet, ABL/tasa municipal). Las expensas extraordinarias y los impuestos que "
           "graven la propiedad serán a cargo del/la LOCADOR/A, conforme al artículo 1209 del CCCN."),

        sec("SÉPTIMA — CONSERVACIÓN DEL INMUEBLE"),
        cl("El/La LOCATARIO/A se obliga a usar y gozar del inmueble como un buen administrador, conservándolo en "
           "buen estado y efectuando a su costo las reparaciones locativas. Las roturas o desperfectos producidos "
           "por culpa o negligencia del/la LOCATARIO/A o de las personas a su cargo serán reparadas a su exclusivo costo."),

        sec("OCTAVA — RESCISIÓN ANTICIPADA"),
        cl("Cumplido el plazo de seis (6) meses, el/la LOCATARIO/A podrá rescindir el contrato notificando "
           "fehacientemente con al menos un (1) mes de antelación. La indemnización por rescisión anticipada "
           "será equivalente a un mes y medio (1,5) de alquiler si la opción se ejerce dentro del primer año, "
           "y a un mes (1) si se ejerce con posterioridad."),

        sec("NOVENA — JURISDICCIÓN"),
        cl(f"Las partes constituyen domicilios especiales en los indicados en este contrato, donde se tendrán "
           f"por válidas todas las notificaciones judiciales y extrajudiciales, sometiéndose a los Tribunales "
           f"Ordinarios de {ctx['propiedad'].get('provincia') or ctx['propiedad'].get('ciudad') or 'la jurisdicción del inmueble'}, "
           f"con renuncia expresa a cualquier otro fuero o jurisdicción que pudiera corresponder."),
    ]


# ────────────────────────────────────────────────────────────────────
# Plantilla 2 — Alquiler Comercial
# ────────────────────────────────────────────────────────────────────
def _plantilla_alquiler_comercial(story, ctx, sty):
    c = ctx["contrato"]
    monto = _money(c.get("monto_inicial"))
    deposito = _money(c.get("deposito"))
    indice_lbl = INDICE_LABEL.get(c.get("indice_ajuste") or "ipc", "IPC")
    period = c.get("periodicidad_meses") or 3

    cl = lambda txt: Paragraph(txt, sty["CiudadClause"])
    sec = lambda txt: Paragraph(txt, sty["CiudadSection"])

    story += [
        sec("PRIMERA — OBJETO Y DESTINO"),
        cl(f"EL/LA LOCADOR/A da en locación al/la LOCATARIO/A el inmueble sito en "
           f"<b>{ctx['propiedad'].get('direccion','—')}</b> ({ctx['propiedad'].get('ciudad','—')}), "
           f"con destino exclusivo al ejercicio de la actividad <b>comercial</b> que desarrolla el/la LOCATARIO/A. "
           f"El cambio de destino requerirá autorización previa, expresa y por escrito del/la LOCADOR/A. "
           f"Toda habilitación municipal y autorización para el ejercicio del rubro comercial será a costo "
           f"y diligencia exclusiva del/la LOCATARIO/A."),

        sec("SEGUNDA — PLAZO"),
        cl(f"El plazo se establece en <b>treinta y seis (36) meses</b>, conforme al artículo 1199 del CCCN, desde "
           f"el {_fecha(c.get('fecha_inicio'))} hasta el {_fecha(c.get('fecha_fin'))}. La continuación de la "
           f"ocupación luego del vencimiento sin oposición del/la LOCADOR/A no implicará renovación tácita."),

        sec("TERCERA — CANON LOCATIVO"),
        cl(f"El canon mensual inicial se conviene en <b>{monto}</b>, pagadero por adelantado del 1 al 5 de cada "
           f"mes. El IVA, en caso de corresponder según la condición fiscal del/la LOCADOR/A, se adicionará al "
           f"precio convenido."),

        sec("CUARTA — ACTUALIZACIÓN"),
        cl(f"El canon se ajustará cada <b>{period} meses</b> aplicando el índice <b>{indice_lbl}</b>. Las partes "
           f"manifiestan que la cláusula de actualización constituye una condición esencial del contrato, sin la "
           f"cual no se hubiera celebrado. La aplicación es automática y de pleno derecho."),

        sec("QUINTA — GARANTÍAS"),
        cl(f"En garantía del fiel cumplimiento de las obligaciones, el/la LOCATARIO/A entrega un depósito de "
           f"<b>{deposito}</b>, sin perjuicio de la(s) garantía(s) adicional(es) que pudiera/n exigirse "
           f"(fiador solidario, seguro de caución, etc.)."),

        sec("SEXTA — MEJORAS Y REFACCIONES"),
        cl("Toda mejora o refacción que el/la LOCATARIO/A pretenda realizar en el inmueble requerirá conformidad "
           "previa por escrito del/la LOCADOR/A. Las mejoras útiles o de mero ornato quedarán en beneficio "
           "del inmueble sin derecho a reclamo o compensación. Las mejoras necesarias serán a cargo del/la "
           "LOCADOR/A solo si fueron previamente comunicadas y autorizadas."),

        sec("SÉPTIMA — IMPUESTOS, TASAS Y SERVICIOS"),
        cl("El/La LOCATARIO/A asumirá el pago de los impuestos y tasas que graven directamente la actividad "
           "comercial desarrollada en el inmueble, así como todos los servicios públicos. Los tributos que "
           "graven la propiedad raíz quedarán a cargo del/la LOCADOR/A."),

        sec("OCTAVA — RESCISIÓN"),
        cl("La rescisión anticipada por parte del/la LOCATARIO/A devengará una indemnización equivalente a dos "
           "(2) meses de canon locativo si la opción se ejerce dentro del primer año, y a un (1) mes en caso "
           "contrario, sin perjuicio de las obligaciones devengadas hasta la efectiva restitución."),

        sec("NOVENA — JURISDICCIÓN"),
        cl(f"Para toda divergencia derivada del presente contrato, las partes se someten a la jurisdicción "
           f"de los Tribunales Ordinarios de {ctx['propiedad'].get('provincia') or ctx['propiedad'].get('ciudad') or 'la jurisdicción del inmueble'}, "
           f"renunciando a cualquier otro fuero."),
    ]


# ────────────────────────────────────────────────────────────────────
# Plantilla 3 — Boleto de Compraventa
# ────────────────────────────────────────────────────────────────────
def _plantilla_boleto_compraventa(story, ctx, sty):
    c = ctx["contrato"]
    monto = _money(c.get("monto_inicial"))
    seña = _money(c.get("deposito"))

    cl = lambda txt: Paragraph(txt, sty["CiudadClause"])
    sec = lambda txt: Paragraph(txt, sty["CiudadSection"])

    story += [
        sec("PRIMERA — OBJETO DE LA COMPRAVENTA"),
        cl(f"EL/LA VENDEDOR/A vende, cede y transfiere a EL/LA COMPRADOR/A, quien acepta de conformidad, el "
           f"inmueble identificado como <b>{ctx['propiedad'].get('direccion','—')}</b>, sito en "
           f"{ctx['propiedad'].get('ciudad','—')}{', ' + ctx['propiedad'].get('provincia','') if ctx['propiedad'].get('provincia') else ''}, "
           f"con todo lo edificado, plantado, clavado y adherido al suelo, libre de toda ocupación, deuda, "
           f"gravamen e inhibición."),

        sec("SEGUNDA — PRECIO"),
        cl(f"El precio total y único de la operación se conviene en la suma de <b>{monto}</b>, pagaderos en la "
           f"forma y oportunidad establecidas en la cláusula tercera del presente. El pago del precio en los "
           f"términos pactados es esencial al consentimiento prestado por el/la VENDEDOR/A."),

        sec("TERCERA — SEÑA Y PAGOS"),
        cl(f"En este acto y como principio de ejecución del contrato (artículos 1059 y 1060 del CCCN), el/la "
           f"COMPRADOR/A entrega al/la VENDEDOR/A la suma de <b>{seña}</b> en concepto de seña, principio "
           f"de pago y a cuenta del precio total. El saldo deberá abonarse al momento de la suscripción de la "
           f"escritura traslativa de dominio, conforme al cronograma acordado entre las partes."),

        sec("CUARTA — POSESIÓN Y ESCRITURACIÓN"),
        cl(f"La posesión del inmueble se entregará al/la COMPRADOR/A en la fecha de la firma de la escritura "
           f"traslativa de dominio, libre de ocupantes, deudas y gravámenes. La escritura se otorgará dentro de "
           f"los <b>noventa (90) días</b> contados desde la firma del presente boleto, ante la escribanía que "
           f"designe el/la COMPRADOR/A. Los honorarios y gastos de escrituración se distribuirán conforme a "
           f"la costumbre y normativa vigente."),

        sec("QUINTA — IMPUESTOS Y SERVICIOS"),
        cl("Hasta la firma de la escritura traslativa de dominio, los impuestos, tasas, contribuciones y "
           "expensas que graven el inmueble estarán a cargo del/la VENDEDOR/A. A partir de dicha fecha "
           "todas las cargas pasarán al/la COMPRADOR/A."),

        sec("SEXTA — INCUMPLIMIENTO"),
        cl("La parte que incumpla con sus obligaciones autorizará a la otra a optar entre: (a) exigir el "
           "cumplimiento forzado del contrato con más los daños y perjuicios; o (b) tener por resuelto "
           "el contrato. Si quien incumple es el/la COMPRADOR/A, la seña entregada quedará en beneficio "
           "del/la VENDEDOR/A. Si quien incumple es el/la VENDEDOR/A, deberá restituir la seña duplicada, "
           "conforme al artículo 1059 del CCCN."),

        sec("SÉPTIMA — CONSTANCIAS REGISTRALES"),
        cl("EL/LA VENDEDOR/A declara bajo juramento que el inmueble se encuentra libre de gravámenes, "
           "embargos, restricciones al dominio y deudas por impuestos, tasas y servicios. Cualquier "
           "ocultamiento dará derecho al/la COMPRADOR/A a resolver el contrato y reclamar los daños."),

        sec("OCTAVA — JURISDICCIÓN"),
        cl(f"Para todos los efectos del presente boleto, las partes constituyen domicilios especiales en los "
           f"indicados en su encabezamiento y se someten a la jurisdicción de los Tribunales Ordinarios de "
           f"{ctx['propiedad'].get('provincia') or ctx['propiedad'].get('ciudad') or 'la jurisdicción del inmueble'}, "
           f"con renuncia expresa a cualquier otro fuero."),
    ]


def _plantilla_sena_alquiler(story, ctx, sty):
    c = ctx["contrato"]
    monto = _money(c.get("monto_inicial"))
    sena = _money(c.get("deposito"))

    cl = lambda txt: Paragraph(txt, sty["CiudadClause"])
    sec = lambda txt: Paragraph(txt, sty["CiudadSection"])

    story += [
        sec("PRIMERA — RESERVA"),
        cl(f"EL/LA INTERESADO/A entrega en este acto a CIUDAD. y/o al/la PROPIETARIO/A, "
           f"a cuenta de la futura locación del inmueble sito en "
           f"<b>{ctx['propiedad'].get('direccion','—')}</b> ({ctx['propiedad'].get('ciudad','—')}), "
           f"la suma de <b>{sena}</b> en concepto de seña y reserva. La operación queda "
           f"sujeta a la aprobación del/la PROPIETARIO/A y al cumplimiento de los requisitos "
           f"habituales (presentación de garantías, antecedentes y documentación)."),

        sec("SEGUNDA — VALOR DEL ALQUILER"),
        cl(f"De aceptarse la reserva, el canon locativo inicial será de <b>{monto}</b> mensuales, "
           f"sujeto a las condiciones de ajuste y plazo que se establezcan en el contrato de "
           f"locación definitivo."),

        sec("TERCERA — IMPUTACIÓN DE LA SEÑA"),
        cl("Aceptada la reserva por el/la PROPIETARIO/A, el monto entregado se imputará "
           "íntegramente al primer canon locativo, depósito en garantía o gastos administrativos, "
           "según se acuerde en el contrato definitivo."),

        sec("CUARTA — RECHAZO O DESISTIMIENTO"),
        cl("Si el/la PROPIETARIO/A rechaza la oferta, la seña será restituida en su totalidad "
           "al/la INTERESADO/A dentro de las 72 horas. Si el/la INTERESADO/A desiste de la "
           "operación una vez aceptada la reserva, perderá el monto entregado en concepto de "
           "indemnización por la inmovilización del inmueble."),

        sec("QUINTA — PLAZO DE RESPUESTA"),
        cl("EL/LA PROPIETARIO/A cuenta con un plazo de hasta cinco (5) días hábiles desde la "
           "presentación formal de esta reserva para aceptarla o rechazarla. Vencido ese plazo "
           "sin respuesta, se considerará rechazada y la seña será restituida."),
    ]


PLANTILLAS = {
    "alquiler_vivienda": _plantilla_alquiler_vivienda,
    "alquiler_comercial": _plantilla_alquiler_comercial,
    "boleto_compraventa": _plantilla_boleto_compraventa,
    "sena_alquiler": _plantilla_sena_alquiler,
}


def generar_pdf_contrato(ctx: dict) -> bytes:
    """
    ctx = {
        "contrato": {... campos del contrato},
        "propiedad": {... campos de la propiedad},
        "locador": {"nombre_completo", "documento", "email", "telefono"},
        "locatario": {"nombre_completo", "documento", "email", "telefono"},
    }
    """
    c = ctx["contrato"]
    tipo = c.get("tipo") or "alquiler_vivienda"
    codigo = c.get("codigo") or f"CONTRATO-{c.get('id','—')}"
    titulo = TIPO_LABEL.get(tipo, "Contrato")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=34 * mm, bottomMargin=18 * mm,
        title=codigo, author="CIUDAD.",
    )
    sty = _styles()
    story = []

    # Título principal
    story += [
        Paragraph(titulo.upper(), sty["CiudadTitle"]),
        Paragraph(f"Documento {codigo} · Estado: {c.get('estado','—')}", sty["CiudadSubtitle"]),
    ]

    # Partes intervinientes
    story += [Paragraph("PARTES INTERVINIENTES", sty["CiudadSection"])]
    rol_locatario = "COMPRADOR/A" if tipo == "boleto_compraventa" else (
        "LOCATARIO/A COMERCIAL" if tipo == "alquiler_comercial" else "LOCATARIO/A"
    )
    story += [_tabla_partes(ctx["propiedad"], ctx["locador"], ctx["locatario"], sty, rol_locatario)]

    # Condiciones económicas resumen
    cond_rows = [
        ("Tipo de contrato", titulo),
        ("Código", codigo),
        ("Fecha de inicio", _fecha(c.get("fecha_inicio"))),
        ("Fecha de finalización", _fecha(c.get("fecha_fin"))),
        ("Monto inicial", _money(c.get("monto_inicial"))),
        ("Depósito / Seña", _money(c.get("deposito"))),
    ]
    if tipo != "boleto_compraventa":
        cond_rows += [
            ("Índice de ajuste", INDICE_LABEL.get(c.get("indice_ajuste") or "ipc", "—")),
            ("Periodicidad de ajuste", f"{c.get('periodicidad_meses') or 3} meses"),
        ]
        if (c.get("indice_ajuste") or "") == "fijo":
            cond_rows.append(("Porcentaje fijo por período", f"{c.get('porcentaje_fijo') or 0}%"))
        if c.get("comision_porc"):
            cond_rows.append(("Comisión inmobiliaria", f"{c.get('comision_porc')}%"))

    story += [
        Spacer(1, 6 * mm),
        Paragraph("CONDICIONES PRINCIPALES", sty["CiudadSection"]),
        _tabla_condiciones(cond_rows),
        Spacer(1, 6 * mm),
    ]

    # Cláusulas
    story += [Paragraph("CLÁUSULAS", sty["CiudadSection"])]
    plantilla = PLANTILLAS.get(tipo, _plantilla_alquiler_vivienda)
    plantilla(story, ctx, sty)

    if c.get("notas"):
        story += [
            Paragraph("OBSERVACIONES", sty["CiudadSection"]),
            Paragraph(str(c["notas"]).replace("\n", "<br/>"), sty["CiudadClause"]),
        ]

    # Lugar y fecha
    story += [
        Spacer(1, 8 * mm),
        Paragraph(
            f"En la Ciudad de {ctx['propiedad'].get('ciudad') or '________________'}, "
            f"a los {date.today().strftime('%d')} días del mes de "
            f"{['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][date.today().month-1]} "
            f"de {date.today().year}, en prueba de conformidad y previa lectura "
            f"se otorgan dos (2) ejemplares de un mismo tenor y a un solo efecto.",
            sty["CiudadClause"],
        ),
    ]

    doc.build(
        story,
        onFirstPage=lambda canv, d: _header_footer(canv, d, codigo),
        onLaterPages=lambda canv, d: _header_footer(canv, d, codigo),
    )
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
