"""Redacción del aviso al ciudadano con Gemini en Vertex AI.

Regla de diseño: la IA SOLO redacta el texto; nunca decide el resultado.
La salida se valida (contiene el folio, <= 400 caracteres, sin enlaces). Si
falla la validación, la IA está deshabilitada o el modelo no responde, se usa
una plantilla fija. Así una caída del modelo no detiene el trámite.
"""
from __future__ import annotations

import re
from typing import Optional

from . import logs
from .config import get_config
from .db import TIPOS

MAX_CARACTERES = 400
_PATRON_ENLACE = re.compile(r"(https?://|www\.|\b[\w-]+\.(cl|com|org|net|gob|gov|io)\b)", re.I)

_DESCRIPCION_ESTADO = {
    "RECIBIDO": "fue recibido y quedó en cola para revisión",
    "EN_REVISION": "está siendo revisado por un funcionario",
    "APROBADO": "fue aprobado y el certificado está disponible para descarga en el portal",
    "OBSERVADO": "tiene observaciones que debe subsanar en el portal",
    "RECHAZADO": "fue rechazado",
}

_client = None


def plantilla(folio: str, tipo: str, estado: str, nombre: str, comentario: Optional[str]) -> str:
    tipo_txt = TIPOS.get(tipo, {}).get("nombre", tipo)
    texto = f"Estimado/a {nombre}: su trámite {tipo_txt}, folio {folio}, {_DESCRIPCION_ESTADO.get(estado, estado)}."
    if comentario and estado in ("OBSERVADO", "RECHAZADO"):
        texto += f" Motivo: {comentario}"
    texto += " PDI."
    return texto[:MAX_CARACTERES]


def validar(texto: Optional[str], folio: str) -> bool:
    if not texto:
        return False
    texto = texto.strip()
    return (
        folio in texto
        and len(texto) <= MAX_CARACTERES
        and not _PATRON_ENLACE.search(texto)
    )


def _cliente():
    global _client
    if _client is None:
        from google import genai  # import diferido: no se necesita en modo local

        c = get_config()
        _client = genai.Client(vertexai=True, project=c.gcp_project, location=c.vertex_location)
    return _client


def _prompt(folio, tipo, estado, nombre, comentario) -> str:
    tipo_txt = TIPOS.get(tipo, {}).get("nombre", tipo)
    partes = [
        "Redacta un aviso breve para un ciudadano sobre su trámite en la Policía de Investigaciones de Chile (PDI).",
        f"Nombre del ciudadano: {nombre}.",
        f"Trámite: {tipo_txt}.",
        f"Folio (debe aparecer exactamente así): {folio}.",
        f"Situación: el trámite {_DESCRIPCION_ESTADO.get(estado, estado)}.",
    ]
    if comentario and estado in ("OBSERVADO", "RECHAZADO"):
        partes.append(f"Motivo indicado por el funcionario: {comentario}.")
    partes += [
        "Reglas: español de Chile, tono formal y cercano, máximo 300 caracteres, una sola oración o dos,",
        "sin enlaces ni direcciones web, sin inventar datos, plazos ni requisitos, y sin cambiar el resultado.",
        "Responde solo con el texto del aviso.",
    ]
    return "\n".join(partes)


def _generar(prompt: str) -> Optional[str]:
    from google.genai import types

    c = get_config()
    cliente = _cliente()
    base = dict(temperature=0.3, max_output_tokens=1024)
    try:
        # Razonamiento desactivado: mantiene la salida cerca de los 120 tokens
        # supuestos en la estimación de costos.
        cfg = types.GenerateContentConfig(**base, thinking_config=types.ThinkingConfig(thinking_budget=0))
        resp = cliente.models.generate_content(model=c.gemini_model, contents=prompt, config=cfg)
    except Exception as e:  # el modelo puede no aceptar thinking_budget=0
        logs.warning("Reintento sin thinking_config", error=str(e)[:300])
        cfg = types.GenerateContentConfig(**base)
        resp = cliente.models.generate_content(model=c.gemini_model, contents=prompt, config=cfg)
    return (resp.text or "").strip()


def redactar_aviso(folio: str, tipo: str, estado: str, nombre: str, comentario: Optional[str] = None) -> tuple[str, str]:
    """Devuelve (texto, origen) donde origen es 'gemini' o 'plantilla'."""
    c = get_config()
    if c.ia_habilitada and c.gcp_project:
        try:
            texto = _generar(_prompt(folio, tipo, estado, nombre, comentario))
            if validar(texto, folio):
                return texto.strip(), "gemini"
            logs.warning("Salida de Gemini rechazada por la validación", folio=folio, salida=(texto or "")[:500])
        except Exception as e:
            logs.error("Gemini no respondió, se usa plantilla", folio=folio, error=str(e)[:500])
    return plantilla(folio, tipo, estado, nombre, comentario), "plantilla"
