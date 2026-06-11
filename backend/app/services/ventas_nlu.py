"""
NLU: texto libre → campos estructurados de un pedido (Fase 2, plan sección 7).

Si hay `ANTHROPIC_API_KEY`, usa Claude (response forzado a JSON). Si no, cae a
un parser por reglas/regex que cubre los casos típicos en español argentino
("Juan busca casa 2 dorm hasta 150k en Pilar"). Así el endpoint funciona
siempre y se enchufa Claude cuando esté la key.
"""
import os
import re
import json

TIPOS = ["casa", "departamento", "lote", "local", "oficina", "galpon", "campo"]
_TIPO_SINONIMOS = {
    "depto": "departamento", "depa": "departamento", "dpto": "departamento",
    "ph": "departamento", "terreno": "lote", "lote": "lote", "casa": "casa",
    "local": "local", "oficina": "oficina", "galpon": "galpon", "galpón": "galpon",
    "campo": "campo",
}


def _parse_precio(texto: str):
    """Detecta 'hasta 150k', '150.000', 'usd 150000', '150 mil'."""
    t = texto.lower().replace(".", "").replace(",", "")
    # 150k / 150 mil
    m = re.search(r'(\d+)\s*(k|mil)\b', t)
    if m:
        return int(m.group(1)) * 1000
    # número grande (>= 10000) suelto, posiblemente con usd/u$s
    m = re.search(r'(?:usd|u\$s|dolares|dólares)?\s*(\d{4,7})', t)
    if m:
        val = int(m.group(1))
        if val >= 10000:
            return val
    return None


def _parse_dorm(texto: str):
    m = re.search(r'(\d+)\s*(?:dorm|dormitorio|amb|ambiente)', texto.lower())
    return int(m.group(1)) if m else None


def _parse_tipo(texto: str):
    t = texto.lower()
    for k, v in _TIPO_SINONIMOS.items():
        if re.search(rf'\b{k}', t):
            return v
    return None


def _parse_zona(texto: str):
    # "en Pilar", "en el centro", "zona norte"
    m = re.search(r'\ben\s+(?:el\s+|la\s+)?([a-záéíóúñ\s]{3,25}?)(?:\s+(?:hasta|por|de|con)\b|[.,]|$)',
                  texto.lower())
    if m:
        return m.group(1).strip().title()
    m = re.search(r'\bzona\s+([a-záéíóúñ]{3,20})', texto.lower())
    if m:
        return m.group(1).strip().title()
    return None


def _fallback(texto: str) -> dict:
    return {
        "tipo": _parse_tipo(texto),
        "zona": _parse_zona(texto),
        "precio_max_usd": _parse_precio(texto),
        "dormitorios_min": _parse_dorm(texto),
        "_motor": "reglas",
    }


def _claude(texto: str) -> dict | None:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=key)
        tool = {
            "name": "registrar_pedido",
            "description": "Extrae los campos del pedido inmobiliario.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tipo": {"type": ["string", "null"], "enum": TIPOS + [None]},
                    "zona": {"type": ["string", "null"]},
                    "precio_max_usd": {"type": ["number", "null"]},
                    "dormitorios_min": {"type": ["integer", "null"]},
                },
            },
        }
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            tools=[tool],
            tool_choice={"type": "tool", "name": "registrar_pedido"},
            messages=[{"role": "user", "content":
                       f"Extraé los datos de este pedido inmobiliario. Si un dato no está, devolvé null (no inventes):\n\n{texto}"}],
        )
        for block in msg.content:
            if block.type == "tool_use":
                out = dict(block.input)
                out["_motor"] = "claude"
                return out
    except Exception as e:
        print(f"[ventas_nlu] Claude fallback a reglas: {e}")
    return None


def parsear_pedido(texto: str) -> dict:
    """Devuelve dict con tipo/zona/precio_max_usd/dormitorios_min (+ _motor)."""
    res = _claude(texto)
    if res is None:
        res = _fallback(texto)
    # Normalizar tipo
    if res.get("tipo") and res["tipo"] not in TIPOS:
        res["tipo"] = _TIPO_SINONIMOS.get(str(res["tipo"]).lower())
    return res
