"""
PDF de presentación de un inmueble (ficha técnica).

Genera un PDF A4 con:
  - Header con branding CIUDAD
  - Foto principal grande (si hay)
  - Datos del inmueble: tipo, dirección, ciudad, ambientes, m², precio
  - Descripción
  - Galería de fotos adicionales
  - Condiciones generales

Deliberadamente NO incluye propietarios ni inquilinos — es la versión
"comercial" para mandarle al interesado.
"""
import io
import httpx
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
)


GOLD = HexColor("#B8893A")
DARK = HexColor("#0A0A0A")
GRAY = HexColor("#737373")
LIGHT_GRAY = HexColor("#E5E5E5")


TIPO_LABEL = {
    "departamento": "Departamento",
    "casa": "Casa",
    "local": "Local comercial",
    "oficina": "Oficina / Consultorio",
    "galpon": "Galpón",
    "campo": "Campo",
}


def _styles():
    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24,
                           textColor=DARK, leading=28, spaceAfter=4)
    subtitle = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11,
                              textColor=GRAY, leading=14, spaceAfter=12)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=10,
                          textColor=DARK, leading=14, alignment=TA_JUSTIFY)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12,
                        textColor=DARK, leading=16, spaceBefore=10, spaceAfter=6)
    eyebrow = ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=8,
                             textColor=GOLD, leading=10, spaceAfter=2,
                             alignment=TA_LEFT)
    return dict(title=title, subtitle=subtitle, body=body, h2=h2, eyebrow=eyebrow)


def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    # Header
    canvas.setFillColor(DARK)
    canvas.rect(0, h - 18 * mm, w, 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(20 * mm, h - 8 * mm, "NEGOCIOS INMOBILIARIOS")
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(20 * mm, h - 14 * mm, "CIUDAD.")
    canvas.setFillColor(GOLD)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 20 * mm, h - 13 * mm, "#VIVIRMEJOR")

    # Footer
    canvas.setFillColor(GRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(w / 2, 10 * mm,
                             "CIUDAD — Negocios Inmobiliarios · ficha informativa")
    canvas.drawRightString(w - 20 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _money(v) -> str:
    try:
        n = float(v or 0)
    except Exception:
        return "—"
    if n <= 0:
        return "—"
    return f"$ {n:,.0f}".replace(",", ".")


def _img_from_url(url: str, max_w_mm: float, max_h_mm: float):
    """Descarga la imagen y devuelve un flowable Image, o None si falla."""
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return None
        ir = ImageReader(io.BytesIO(r.content))
        iw, ih = ir.getSize()
        # Ajustar al cuadro manteniendo proporción
        max_w = max_w_mm * mm
        max_h = max_h_mm * mm
        ratio = min(max_w / iw, max_h / ih)
        return Image(io.BytesIO(r.content), width=iw * ratio, height=ih * ratio)
    except Exception:
        return None


def generar_pdf_ficha(
    propiedad: dict,
    fotos_urls: list[str],
    condiciones: Optional[str] = None,
) -> bytes:
    """
    propiedad: dict con tipo, direccion, ciudad, provincia, ambientes,
               superficie_m2, precio_alquiler, expensas, tasa_municipal,
               descripcion.
    fotos_urls: lista de URLs públicas/firmadas de las fotos. La primera
                se usa como foto principal grande.
    condiciones: texto libre opcional con condiciones comerciales.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=28 * mm, bottomMargin=18 * mm,
        title=f"Ficha — {propiedad.get('direccion', '')}",
    )
    sty = _styles()
    story = []

    # --- Foto principal ---
    if fotos_urls:
        img = _img_from_url(fotos_urls[0], max_w_mm=170, max_h_mm=85)
        if img is not None:
            story.append(img)
            story.append(Spacer(1, 4 * mm))

    # --- Título ---
    tipo = TIPO_LABEL.get(propiedad.get("tipo", ""), propiedad.get("tipo", ""))
    story.append(Paragraph(tipo.upper(), sty["eyebrow"]))
    story.append(Paragraph(propiedad.get("direccion", "Sin dirección"), sty["title"]))
    loc = propiedad.get("ciudad") or ""
    if propiedad.get("provincia"):
        loc += f", {propiedad['provincia']}"
    if loc:
        story.append(Paragraph(loc, sty["subtitle"]))

    # --- Tabla de características ---
    car_rows = []
    if propiedad.get("ambientes"):
        car_rows.append(["Ambientes", str(propiedad["ambientes"])])
    if propiedad.get("superficie_m2"):
        car_rows.append(["Superficie", f"{propiedad['superficie_m2']} m²"])
    if propiedad.get("precio_alquiler"):
        car_rows.append(["Alquiler mensual", _money(propiedad["precio_alquiler"])])
    if propiedad.get("expensas"):
        car_rows.append(["Expensas", _money(propiedad["expensas"])])
    if propiedad.get("tasa_municipal"):
        car_rows.append(["Tasas e impuestos", _money(propiedad["tasa_municipal"])])

    if car_rows:
        story.append(Paragraph("Características", sty["h2"]))
        tabla = Table(car_rows, colWidths=[55 * mm, 115 * mm], hAlign="LEFT")
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 0), (1, -1), DARK),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, LIGHT_GRAY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(tabla)

    # --- Descripción ---
    desc = (propiedad.get("descripcion") or "").strip()
    if desc:
        story.append(Paragraph("Descripción", sty["h2"]))
        story.append(Paragraph(desc.replace("\n", "<br/>"), sty["body"]))

    # --- Condiciones ---
    if condiciones:
        story.append(Paragraph("Condiciones generales", sty["h2"]))
        story.append(Paragraph(condiciones.replace("\n", "<br/>"), sty["body"]))

    # --- Galería ---
    extras = fotos_urls[1:9]   # hasta 8 fotos adicionales
    if extras:
        story.append(PageBreak())
        story.append(Paragraph("Galería de fotos", sty["h2"]))
        story.append(Spacer(1, 2 * mm))
        # 2 columnas de imágenes 80x55 mm
        celdas = []
        for url in extras:
            img = _img_from_url(url, max_w_mm=80, max_h_mm=55)
            celdas.append(img if img is not None else Paragraph("(foto no disponible)", sty["body"]))
        # rellenar a múltiplos de 2
        if len(celdas) % 2 == 1:
            celdas.append("")
        rows = [[celdas[i], celdas[i + 1]] for i in range(0, len(celdas), 2)]
        tg = Table(rows, colWidths=[85 * mm, 85 * mm], hAlign="CENTER")
        tg.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tg)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
