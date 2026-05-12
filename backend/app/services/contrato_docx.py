"""
Generación de contratos en formato Word (.docx) — editable por el admin
antes de firmar. Después puede subir el .docx actualizado a /upload-archivo
y queda asociado al contrato.

Soporta los mismos 4 tipos que pdf_service:
  alquiler_vivienda, alquiler_comercial, boleto_compraventa, sena_alquiler

Genera un documento estilo "borrador" con campos prellenados pero editables.
"""
import io
from datetime import date
from typing import Optional

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


GOLD = RGBColor(0xB8, 0x89, 0x3A)
DARK = RGBColor(0x0A, 0x0A, 0x0A)
GRAY = RGBColor(0x73, 0x73, 0x73)


TIPO_TITULO = {
    "alquiler_vivienda":  "CONTRATO DE LOCACIÓN DE VIVIENDA",
    "alquiler_comercial": "CONTRATO DE LOCACIÓN COMERCIAL",
    "boleto_compraventa": "BOLETO DE COMPRAVENTA",
    "sena_alquiler":      "RESERVA / SEÑA DE ALQUILER",
}


def _money(v) -> str:
    try:
        n = float(v or 0)
    except Exception:
        return "—"
    return f"$ {n:,.0f}".replace(",", ".") if n > 0 else "—"


def _fecha(d) -> str:
    if not d:
        return "____ de _______________ de 20__"
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except Exception:
            return d
    meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{d.day:02d} de {meses[d.month]} de {d.year}"


def _setup_styles(doc: Document):
    """Estilos base — Helvetica/Calibri-like, 11pt body."""
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)


def _h1(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = DARK
    p.paragraph_format.space_after = Pt(4)


def _h2(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = GOLD
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)


def _eyebrow(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.font.size = Pt(8)
    run.font.color.rgb = GOLD


def _p(doc, text, justify=True, bold=False, italic=False):
    p = doc.add_paragraph()
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(11)
    return p


def _datos_tabla(doc, rows: list[tuple[str, str]]):
    t = doc.add_table(rows=len(rows), cols=2)
    t.autofit = False
    for i, (lbl, val) in enumerate(rows):
        c0 = t.cell(i, 0)
        c1 = t.cell(i, 1)
        c0.width = Cm(5)
        c1.width = Cm(11)
        r0 = c0.paragraphs[0].add_run(lbl)
        r0.font.size = Pt(10)
        r0.font.color.rgb = GRAY
        r1 = c1.paragraphs[0].add_run(val or "—")
        r1.font.size = Pt(10)
        r1.bold = True


def _persona_str(c: Optional[dict]) -> str:
    if not c:
        return "[Completar datos]"
    partes = []
    if c.get("nombre") or c.get("apellido"):
        partes.append(f"{c.get('nombre','')} {c.get('apellido','')}".strip())
    if c.get("razon_social"):
        partes.append(c["razon_social"])
    if c.get("documento"):
        partes.append(f"DNI/CUIT {c['documento']}")
    if c.get("email"):
        partes.append(c["email"])
    if c.get("telefono"):
        partes.append(c["telefono"])
    return ", ".join(partes) if partes else "[Completar datos]"


def _direccion_str(p: Optional[dict]) -> str:
    if not p:
        return "[Sin propiedad]"
    bits = [p.get("direccion") or ""]
    if p.get("ciudad"):
        bits.append(p["ciudad"])
    if p.get("provincia"):
        bits.append(p["provincia"])
    return ", ".join([b for b in bits if b])


def generar_docx(*, contrato: dict, propiedad: dict, propietario: Optional[dict],
                 inquilino: Optional[dict]) -> bytes:
    """Devuelve el .docx en bytes."""
    doc = Document()
    _setup_styles(doc)

    tipo = contrato.get("tipo") or "alquiler_vivienda"
    titulo = TIPO_TITULO.get(tipo, "CONTRATO")

    _eyebrow(doc, "CIUDAD · NEGOCIOS INMOBILIARIOS")
    _h1(doc, titulo)
    _eyebrow(doc, "#VIVIRMEJOR")

    _p(doc, "")  # spacer

    # Lugar y fecha
    _p(doc,
       f"En la ciudad de _________________, a los {_fecha(contrato.get('fecha_inicio'))}, "
       f"entre las partes que a continuación se identifican, se celebra el presente "
       f"contrato bajo las cláusulas y condiciones que se detallan.")

    # Partes
    _h2(doc, "Partes intervinientes")
    rol_a = "LOCADOR" if tipo.startswith("alquiler") else "VENDEDOR"
    rol_b = "LOCATARIO" if tipo.startswith("alquiler") else "COMPRADOR"
    _datos_tabla(doc, [
        (rol_a, _persona_str(propietario)),
        (rol_b, _persona_str(inquilino)),
    ])

    # Objeto
    _h2(doc, "Objeto")
    obj_txt = {
        "alquiler_vivienda":
            f"El LOCADOR da en locación al LOCATARIO el inmueble ubicado en {_direccion_str(propiedad)}, "
            f"destinado exclusivamente a vivienda familiar.",
        "alquiler_comercial":
            f"El LOCADOR da en locación al LOCATARIO el inmueble ubicado en {_direccion_str(propiedad)}, "
            f"destinado exclusivamente a uso comercial.",
        "boleto_compraventa":
            f"El VENDEDOR vende y el COMPRADOR adquiere el inmueble ubicado en {_direccion_str(propiedad)}.",
        "sena_alquiler":
            f"El presente instrumenta la reserva del inmueble ubicado en {_direccion_str(propiedad)} "
            f"con destino a alquiler, sujeto a la firma del contrato definitivo.",
    }.get(tipo, f"Inmueble ubicado en {_direccion_str(propiedad)}.")
    _p(doc, obj_txt)

    # Plazo y monto
    _h2(doc, "Plazo y precio")
    _datos_tabla(doc, [
        ("Inicio",     _fecha(contrato.get("fecha_inicio"))),
        ("Vencimiento", _fecha(contrato.get("fecha_fin"))),
        ("Monto inicial", _money(contrato.get("monto_inicial"))),
        ("Depósito",   _money(contrato.get("deposito"))),
        ("Índice de ajuste", contrato.get("indice_ajuste") or "IPC"),
        ("Periodicidad de ajuste", f"{contrato.get('periodicidad_meses') or 3} meses"),
        ("Comisión inmobiliaria", f"{contrato.get('comision_porc') or 0} %"),
    ])

    # Cláusulas tipo (texto plantilla, el admin lo edita en Word)
    _h2(doc, "Cláusulas")
    _p(doc,
       "PRIMERA. — El plazo del contrato se establece en los términos indicados. "
       "Vencido el mismo, las partes podrán acordar su prórroga por escrito.")
    _p(doc,
       "SEGUNDA. — El precio mensual se ajustará conforme al índice convenido, "
       "según la periodicidad detallada en el cuadro precedente.")
    _p(doc,
       "TERCERA. — Los gastos ordinarios del inmueble (expensas, tasas e impuestos) "
       "estarán a cargo del LOCATARIO, salvo pacto en contrario.")
    _p(doc,
       "CUARTA. — El incumplimiento del pago por parte del LOCATARIO en los términos pactados "
       "habilitará al LOCADOR a iniciar las acciones legales pertinentes.")
    _p(doc,
       "QUINTA. — Cualquier modificación al presente contrato deberá realizarse por escrito y "
       "firmada por ambas partes.")

    # Notas adicionales
    if contrato.get("notas"):
        _h2(doc, "Notas adicionales")
        _p(doc, contrato["notas"])

    # Firmas
    _h2(doc, "Firmas")
    doc.add_paragraph()
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "____________________________"
    t.cell(0, 1).text = "____________________________"
    t.cell(1, 0).text = rol_a
    t.cell(1, 1).text = rol_b
    for cell in (t.cell(1, 0), t.cell(1, 1)):
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(9)
                r.font.color.rgb = GRAY

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
