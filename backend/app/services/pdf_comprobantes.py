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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
        topMargin=34 * mm, bottomMargin=18 * mm,
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


COLOR_ROJO = HexColor("#DC2626")  # red-600 — para descuentos como la comisión


def _tabla_desglose(rows: list[dict], total_pagado: float | None = None,
                    total_rendir: float | None = None,
                    total_final_label: str = "TOTAL A ENTREGAR",
                    total_final: float | None = None,
                    incluye_a_rendir: bool = True):
    """Tabla de desglose tipo modal de Liquidaciones.

    rows = [{label, pagado, a_rendir, descuento}]
        - descuento=True → fila en rojo y monto con prefijo "−"
        - pagado/a_rendir None o 0 → se muestra "—"

    Si incluye_a_rendir=False, tabla de 2 columnas (Concepto | Pagado).
    """
    # Header
    if incluye_a_rendir:
        data = [["Concepto", "Pagado", "A rendir"]]
        colWidths = [85 * mm, 42 * mm, 43 * mm]
    else:
        data = [["Concepto", "Monto"]]
        colWidths = [120 * mm, 50 * mm]

    # Filas
    rojas: list[int] = []  # índices (1-based en data) de filas a colorear en rojo
    for r in rows:
        label = r.get("label") or ""
        pagado = r.get("pagado")
        a_rendir = r.get("a_rendir")
        descuento = bool(r.get("descuento"))

        def _fmt(v):
            if v is None or v == 0:
                return "—"
            if descuento and v < 0:
                return f"− {_money(abs(v))}"
            return _money(v)

        if incluye_a_rendir:
            data.append([label, _fmt(pagado), _fmt(a_rendir)])
        else:
            # En modo inquilino: si tiene "monto" o usamos pagado
            v = r.get("monto") if r.get("monto") is not None else pagado
            data.append([label, _fmt(v)])

        if descuento:
            rojas.append(len(data) - 1)

    # Totales (suma)
    if incluye_a_rendir:
        sum_pagado = total_pagado if total_pagado is not None else sum(
            (r.get("pagado") or 0) for r in rows if not r.get("descuento")
        )
        sum_rendir = total_rendir if total_rendir is not None else sum(
            (r.get("a_rendir") or 0) for r in rows
        )
        data.append(["Totales", _money(sum_pagado), _money(sum_rendir)])
    else:
        sum_total = total_final if total_final is not None else sum(
            (r.get("monto") or r.get("pagado") or 0) for r in rows if not r.get("descuento")
        )
        data.append([total_final_label, _money(sum_total)])

    # Fila final destacada (solo si hay columna a_rendir)
    if incluye_a_rendir:
        final_value = total_final if total_final is not None else sum_rendir
        data.append([total_final_label, "", _money(final_value)])

    t = Table(data, colWidths=colWidths)
    style = [
        # Header
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_FONDO),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_NOCHE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, COLOR_BORDE),
        # Filas normales
        ("FONT", (0, 1), (-1, -3 if incluye_a_rendir else -2), "Helvetica", 9.5),
        ("LINEBELOW", (0, 1), (-1, -3 if incluye_a_rendir else -2), 0.25, COLOR_BORDE),
        # Alineación
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        # Padding
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        # Totales row (penúltima si hay total_final, última si no)
        ("FONT", (0, -2 if incluye_a_rendir else -1), (-1, -2 if incluye_a_rendir else -1), "Helvetica-Bold", 10),
        ("LINEABOVE", (0, -2 if incluye_a_rendir else -1), (-1, -2 if incluye_a_rendir else -1), 0.5, COLOR_BORDE),
    ]
    if incluye_a_rendir:
        # Última fila: TOTAL A ENTREGAR destacado en cobre
        style += [
            ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 12),
            ("LINEABOVE", (0, -1), (-1, -1), 1.2, COLOR_COBRE),
            ("TEXTCOLOR", (0, -1), (-1, -1), COLOR_COBRE),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#FAF8F3")),
        ]
    else:
        # Modo inquilino: solo la fila de Total destacada
        style += [
            ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
            ("LINEABOVE", (0, -1), (-1, -1), 1, COLOR_NOCHE),
            ("TEXTCOLOR", (0, -1), (-1, -1), COLOR_NOCHE),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#FAF8F3")),
        ]
    # Pintar de rojo las filas marcadas como descuento
    for idx in rojas:
        style.append(("TEXTCOLOR", (0, idx), (-1, idx), COLOR_ROJO))
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

    # Desglose con mismo estilo que el de propietario, pero sin "A rendir"
    # ni comisión (el inquilino no ve esa información interna).
    desglose_inq = [
        {"label": lbl, "monto": monto}
        for lbl, monto in (ctx.get("items") or [])
    ]
    story += [
        Spacer(1, 8 * mm),
        Paragraph("DESGLOSE", sty["CiudadSection"]),
        _tabla_desglose(
            desglose_inq,
            total_final_label="TOTAL ABONADO",
            total_final=ctx.get("total"),
            incluye_a_rendir=False,
        ),
    ]

    # Conceptos que el inquilino abonó directamente (al consorcio, municipio, etc.)
    # — informativo, no se cobran en la inmobiliaria.
    items_pagado_directo = ctx.get("items_pagado_directo") or ctx.get("items_propietario") or []
    if items_pagado_directo:
        story += [
            Spacer(1, 6 * mm),
            Paragraph("PAGADO DIRECTAMENTE POR USTED (informativo)", sty["CiudadSection"]),
            Paragraph(
                "Los siguientes conceptos figuran como abonados directamente por usted "
                "al ente correspondiente (consorcio, municipio, etc.). No se cobraron "
                "en la inmobiliaria — se asientan a modo informativo:",
                sty["CiudadClause"],
            ),
            _tabla_kv([(lbl, _money(monto)) for lbl, monto in items_pagado_directo]),
        ]

    story += [
        Spacer(1, 10 * mm),
        Paragraph(
            "Por la presente se deja constancia de la recepción del pago detallado, "
            "no quedando saldo pendiente para el período indicado.",
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


def generar_pdf_comprobante_propietario(ctx: dict) -> bytes:
    """
    Estructura económica:
        El inquilino paga Alquiler + Expensas + Tasas + Otros (= total cobrado).
        La comisión inmobiliaria se calcula SOLO sobre el alquiler (no sobre los
        gastos pasantes). El propietario percibe Alquiler − Comisión.
        Expensas, tasas y otros se muestran como pasantes (cobrados al inquilino,
        derivados a quien corresponda); no integran el neto al propietario.

    ctx = {
        "numero": "LIQ-2026-05-001",
        "fecha_pago": date,
        "periodo": "2026-05",
        "propiedad": {"direccion","ciudad","codigo"},
        "propietario": {"nombre_completo","documento","email","telefono"},
        "inquilino": {"nombre_completo"},
        "contrato": {"id","codigo"},
        "items_cobrados": [(label, monto), ...],     # todo lo cobrado al inquilino
        "monto_alquiler": float,                      # base para la comisión
        "comision_porc": float,
        "monto_comision": float,                      # = alquiler * comision_porc/100
        "monto_neto": float,                          # = alquiler - comision
        "monto_cobrado_total": float,                 # informativo
        "items_pasantes": [(label, monto), ...],     # expensas/tasas/otros (informativo)
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

    alquiler = float(ctx.get("monto_alquiler") or 0)
    comision_pct = float(ctx.get("comision_porc") or 0)
    comision = float(ctx.get("monto_comision") or round(alquiler * comision_pct / 100.0, 2))
    neto = float(ctx.get("monto_neto") or round(alquiler - comision, 2))
    cobrado_total = float(ctx.get("monto_cobrado_total") or 0)

    items_cobrados = ctx.get("items_cobrados") or []
    items_pasantes = ctx.get("items_pasantes") or []
    items_pagado_directo = ctx.get("items_pagado_directo") or ctx.get("items_propietario") or []

    # Desglose tipo modal de Liquidaciones:
    #   Concepto | Pagado (inquilino) | A rendir (al propietario)
    #   Alquiler:              pagado=alquiler         a_rendir=alquiler
    #   Expensas/Tasas/Otros:  pagado=monto            a_rendir=monto (íntegros)
    #   Comisión adm. X%:      pagado=—                a_rendir=−comisión  (rojo)
    desglose_rows = [{"label": "Alquiler", "pagado": alquiler, "a_rendir": alquiler}]
    for lbl, monto in items_pasantes:
        desglose_rows.append({"label": lbl, "pagado": monto, "a_rendir": monto})
    # Conceptos que el inquilino abonó directamente: figuran como pagados pero
    # NO se rinden al propietario (él no los recibió porque el inquilino los
    # pagó al ente — consorcio, municipio, etc.).
    for lbl, monto in items_pagado_directo:
        desglose_rows.append({
            "label": f"{lbl} (pagado directo por inquilino)",
            "pagado": monto,
            "a_rendir": 0,
        })
    if comision_pct and comision > 0:
        desglose_rows.append({
            "label": f"Comisión adm. {comision_pct}% s/ alquiler",
            "pagado": None,
            "a_rendir": -comision,
            "descuento": True,
        })

    story += [
        Spacer(1, 8 * mm),
        Paragraph("DESGLOSE", sty["CiudadSection"]),
        _tabla_desglose(
            desglose_rows,
            total_pagado=cobrado_total or sum(v for _, v in items_cobrados),
            total_rendir=neto,
            total_final_label="TOTAL A ENTREGAR",
            total_final=neto,
            incluye_a_rendir=True,
        ),
    ]

    story += [
        Spacer(1, 8 * mm),
        Paragraph(
            f"Por la presente se informa la liquidación correspondiente al período "
            f"{ctx.get('periodo','—')}. La comisión inmobiliaria se aplica "
            f"únicamente sobre el alquiler.",
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


