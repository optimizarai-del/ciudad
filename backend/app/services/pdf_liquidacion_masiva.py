"""
PDF de liquidación consolidada por propietario.
Incluye una tabla con todas sus propiedades cobradas en el período + total neto.
"""
from io import BytesIO
from datetime import date as _date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

from app.services.pdf_service import (
    _styles, _header_footer, _money, _fecha,
    COLOR_NOCHE, COLOR_BORDE, COLOR_FONDO, COLOR_COBRE,
)


def generar_pdf_liquidacion_consolidada(ctx: dict) -> bytes:
    """
    ctx = {
        "numero": "LIQ-MES-2026-05-001",
        "periodo": "2026-05",
        "fecha_emision": date,
        "propietario": {nombre, documento, email, telefono},
        "items": [{contrato_codigo, propiedad, alquiler, comision_porc,
                   comision, neto_alquiler, expensas, tasas, otros, cobrado_total}],
        "totales": {alquiler, comision, neto, expensas, tasas, otros, cobrado_total},
    }
    """
    numero = ctx.get("numero") or "LIQ-MASIVA"
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=34 * mm, bottomMargin=18 * mm,
        title=numero, author="CIUDAD.",
    )
    sty = _styles()
    story = []

    pro = ctx.get("propietario") or {}
    items = ctx.get("items") or []
    tot = ctx.get("totales") or {}

    story += [
        Paragraph("LIQUIDACIÓN MENSUAL CONSOLIDADA", sty["CiudadTitle"]),
        Paragraph(f"Comprobante {numero} · Período {ctx.get('periodo','—')}", sty["CiudadSubtitle"]),
    ]

    # Datos del propietario
    story += [Paragraph("PROPIETARIO/A", sty["CiudadSection"])]
    info = [
        ["Nombre / Razón social", pro.get("nombre") or "—"],
        ["DNI / CUIT", pro.get("documento") or "—"],
        ["Email", pro.get("email") or "—"],
        ["Teléfono", pro.get("telefono") or "—"],
        ["Fecha de emisión", _fecha(ctx.get("fecha_emision"))],
    ]
    t = Table(info, colWidths=[55 * mm, 125 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_NOCHE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [t, Spacer(1, 6 * mm)]

    # Detalle por propiedad
    story += [Paragraph("DETALLE POR PROPIEDAD", sty["CiudadSection"])]
    head = ["Contrato", "Propiedad", "Alquiler", f"Com.%", "Comisión", "Neto"]
    rows = [head]
    for it in items:
        rows.append([
            it.get("contrato_codigo") or f"#{it['contrato_id']}",
            (it.get("propiedad") or "—")[:32],
            _money(it.get("alquiler")),
            f"{it.get('comision_porc') or 0}%",
            _money(it.get("comision")),
            _money(it.get("neto_alquiler")),
        ])
    rows.append(["", "TOTAL ALQUILERES",
                 _money(tot.get("alquiler")),
                 "",
                 _money(tot.get("comision")),
                 _money(tot.get("neto"))])
    t = Table(rows, colWidths=[28 * mm, 60 * mm, 26 * mm, 14 * mm, 26 * mm, 26 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_FONDO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, COLOR_BORDE),
        ("FONT", (0, 1), (-1, -2), "Helvetica", 8.5),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9),
        ("LINEABOVE", (0, -1), (-1, -1), 1, COLOR_COBRE),
        ("TEXTCOLOR", (0, -1), (-1, -1), COLOR_COBRE),
    ]))
    story += [t, Spacer(1, 4 * mm)]

    # Conceptos pasantes (informativo)
    pasantes = [
        ("Expensas", tot.get("expensas") or 0),
        ("Tasas municipales", tot.get("tasas") or 0),
        ("Otros conceptos", tot.get("otros") or 0),
    ]
    pasantes = [(l, v) for l, v in pasantes if v]
    if pasantes:
        story += [
            Paragraph(
                "Conceptos pasantes (cobrados al inquilino y derivados a quien "
                "corresponda — no integran el neto al propietario):",
                sty["CiudadClause"],
            ),
        ]
        rows_pas = [[lbl, _money(v)] for lbl, v in pasantes]
        t = Table(rows_pas, colWidths=[55 * mm, 30 * mm])
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
            ("TEXTCOLOR", (0, 0), (0, -1), COLOR_NOCHE),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, COLOR_BORDE),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [t, Spacer(1, 6 * mm)]

    # Resumen final
    story += [
        Paragraph("RESUMEN DEL LOTE", sty["CiudadSection"]),
        Paragraph(
            f"Período {ctx.get('periodo','—')} · {len(items)} propiedad/es liquidada/s. "
            f"Total cobrado al inquilino: {_money(tot.get('cobrado_total'))}. "
            f"Comisión total: {_money(tot.get('comision'))}. "
            f"<b>Neto total a transferir al propietario: {_money(tot.get('neto'))}.</b> "
            f"La comisión se aplica únicamente sobre el alquiler.",
            sty["CiudadClause"],
        ),
    ]

    doc.build(
        story,
        onFirstPage=lambda canv, d: _header_footer(canv, d, numero),
        onLaterPages=lambda canv, d: _header_footer(canv, d, numero),
    )
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
