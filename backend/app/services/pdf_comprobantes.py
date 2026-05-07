"""
Comprobantes de pago en PDF.
- Inquilino: detalle de qué pagó (alquiler + expensas + impuestos + municipal + otros).
- Propietario: liquidación con monto cobrado, comisión inmobiliaria y neto a percibir.
Ambos comparten encabezado y estilo con los contratos.
"""
from io import BytesIO
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.lib.colors import HexColor

from app.services.pdf_service import (
    _styles, _header_footer, _money, _fecha,
    COLOR_NOCHE, COLOR_BORDE, COLOR_FONDO, COLOR_COBRE,
)


def _doc(buffer: BytesIO, codigo: str):
    return SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=30 * mm, bottomMargin=18 * mm,
        title=codigo, author="CIUDAD.",
    )


def _tabla_kv(rows, col1=55, col2=115):
    t = Table([[k, v] for k, v in rows], colWidths=[col1 * mm, col2 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_NOCHE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _tabla_montos(rows: list[tuple[str, float]], total_label="TOTAL", total_value=None,
                  acento_total=COLOR_NOCHE):
    """Tabla de columnas Concepto / Monto, con total en negrita al pie."""
    data = [["Concepto", "Monto"]]
    for k, v in rows:
        data.append([k, _money(v)])
    total_value = total_value if total_value is not None else sum(v for _, v in rows)
    data.append([total_label, _money(total_value)])

    t = Table(data, colWidths=[120 * mm, 50 * mm])
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_FONDO),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_NOCHE),
        ("FONT", (0, 1), (-1, -2), "Helvetica", 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, COLOR_BORDE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        # Total
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
        ("LINEABOVE", (0, -1), (-1, -1), 1, acento_total),
        ("TEXTCOLOR", (0, -1), (-1, -1), acento_total),
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#FAF8F3")),
    ]
    t.setStyle(TableStyle(style))
    return t


def generar_pdf_comprobante_inquilino(ctx: dict) -> bytes:
    """
    ctx = {
        "numero": "REC-2026-05-001",
        "fecha_pago": date,
        "periodo": "2026-05",
        "propiedad": {"direccion","ciudad","codigo"},
        "inquilino": {"nombre_completo","documento","email","telefono"},
        "contrato": {"id","codigo"},
        "items": [(label, monto), ...],   # alquiler, expensas, impuestos, municipal, otros
        "total": float,
    }
    """
    numero = ctx.get("numero") or "RECIBO"
    buffer = BytesIO()
    doc = _doc(buffer, numero)
    sty = _styles()
    story = []

    story += [
        Paragraph("RECIBO DE PAGO", sty["CiudadTitle"]),
        Paragraph(f"Comprobante {numero} · Período {ctx.get('periodo','—')}", sty["CiudadSubtitle"]),
        Paragraph("DATOS DEL PAGO", sty["CiudadSection"]),
    ]

    inq = ctx.get("inquilino") or {}
    prop = ctx.get("propiedad") or {}
    contrato = ctx.get("contrato") or {}

    story += [_tabla_kv([
        ("Recibimos de", inq.get("nombre_completo") or "—"),
        ("DNI / CUIT", inq.get("documento") or "—"),
        ("Propiedad", prop.get("direccion") or "—"),
        ("Contrato", contrato.get("codigo") or f"#{contrato.get('id','—')}"),
        ("Período", ctx.get("periodo") or "—"),
        ("Fecha de pago", _fecha(ctx.get("fecha_pago"))),
    ])]

    story += [
        Spacer(1, 8 * mm),
        Paragraph("DETALLE DE CONCEPTOS", sty["CiudadSection"]),
        _tabla_montos(
            ctx.get("items") or [],
            total_label="TOTAL ABONADO",
            total_value=ctx.get("total"),
            acento_total=COLOR_NOCHE,
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "Por la presente se deja constancia de la recepción del pago detallado, "
            "no quedando saldo pendiente para el período indicado.",
            sty["CiudadClause"],
        ),
        Spacer(1, 14 * mm),
        KeepTogether(_firmas_recibo("CIUDAD. — Recibido por", "Conformidad inquilino/a")),
    ]

    doc.build(
        story,
        onFirstPage=lambda canv, d: _header_footer(canv, d, numero),
        onLaterPages=lambda canv, d: _header_footer(canv, d, numero),
    )
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def generar_pdf_comprobante_propietario(ctx: dict) -> bytes:
    """
    ctx = {
        "numero": "LIQ-2026-05-001",
        "fecha_pago": date,
        "periodo": "2026-05",
        "propiedad": {"direccion","ciudad","codigo"},
        "propietario": {"nombre_completo","documento","email","telefono"},
        "inquilino": {"nombre_completo"},
        "contrato": {"id","codigo"},
        "monto_cobrado": float,
        "comision_porc": float,
        "monto_comision": float,
        "monto_neto": float,
        "items_descuento": [(label, monto), ...],   # comisión + otros descuentos
    }
    """
    numero = ctx.get("numero") or "LIQUIDACION"
    buffer = BytesIO()
    doc = _doc(buffer, numero)
    sty = _styles()
    story = []

    story += [
        Paragraph("LIQUIDACIÓN AL PROPIETARIO", sty["CiudadTitle"]),
        Paragraph(f"Comprobante {numero} · Período {ctx.get('periodo','—')}", sty["CiudadSubtitle"]),
        Paragraph("DATOS DE LA OPERACIÓN", sty["CiudadSection"]),
    ]

    pro = ctx.get("propietario") or {}
    inq = ctx.get("inquilino") or {}
    prop = ctx.get("propiedad") or {}
    contrato = ctx.get("contrato") or {}

    story += [_tabla_kv([
        ("Liquidamos a", pro.get("nombre_completo") or "—"),
        ("DNI / CUIT", pro.get("documento") or "—"),
        ("Propiedad", prop.get("direccion") or "—"),
        ("Inquilino/a", inq.get("nombre_completo") or "—"),
        ("Contrato", contrato.get("codigo") or f"#{contrato.get('id','—')}"),
        ("Período", ctx.get("periodo") or "—"),
        ("Fecha de cobro", _fecha(ctx.get("fecha_pago"))),
    ])]

    story += [
        Spacer(1, 8 * mm),
        Paragraph("DETALLE DE LA LIQUIDACIÓN", sty["CiudadSection"]),
    ]

    cobrado = float(ctx.get("monto_cobrado") or 0)
    comision_pct = float(ctx.get("comision_porc") or 0)
    comision = float(ctx.get("monto_comision") or 0)
    neto = float(ctx.get("monto_neto") or 0)

    items = [
        ("Monto total cobrado al inquilino", cobrado),
        (f"Comisión inmobiliaria ({comision_pct}%)", -comision),
    ]
    for label, monto in (ctx.get("items_descuento") or []):
        items.append((label, -float(monto or 0)))

    story += [
        _tabla_montos(
            items,
            total_label="NETO A LIQUIDAR AL PROPIETARIO",
            total_value=neto,
            acento_total=COLOR_COBRE,
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            f"Por la presente se le informa la liquidación correspondiente al período "
            f"{ctx.get('periodo','—')}. El monto neto será depositado/transferido conforme "
            f"a los datos bancarios oportunamente provistos.",
            sty["CiudadClause"],
        ),
        Spacer(1, 14 * mm),
        KeepTogether(_firmas_recibo("CIUDAD. — Administrador", "Conformidad propietario/a")),
    ]

    doc.build(
        story,
        onFirstPage=lambda canv, d: _header_footer(canv, d, numero),
        onLaterPages=lambda canv, d: _header_footer(canv, d, numero),
    )
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def _firmas_recibo(rol_a: str, rol_b: str):
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
        ("TOPPADDING", (0, 0), (-1, 0), 30),
    ]))
    return t
