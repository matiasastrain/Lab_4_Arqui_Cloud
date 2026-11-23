"""Redacción del aviso al ciudadano con Gemini (Vertex AI).

Reemplaza a Microsoft Foundry del Laboratorio 1 y 2. La IA solo redacta: recibe el
estado ya confirmado en la base de datos y nunca decide el resultado del trámite.
Si el modelo falla, tarda o devuelve algo inválido, se usa una plantilla fija.
"""
import logging

from .config import TIPOS_TRAMITE, settings

log = logging.getLogger("pdi.ai")

ETIQUETA_ESTADO = {
    "RECIBIDO": "recibida",
    "EN_REVISION": "en revisión por un funcionario",
    "OBSERVADO": "observada: requiere que completes o corrijas información",
    "APROBADO": "aprobada: el certificado ya está disponible",
    "RECHAZADO": "rechazada",
}

PLANTILLAS = {
    "RECIBIDO": "Tu solicitud con folio {folio} fue recibida y quedó registrada.",
    "EN_REVISION": "Tu solicitud con folio {folio} está siendo revisada por un funcionario.",
    "OBSERVADO": "Tu solicitud con folio {folio} tiene observaciones. Ingresa al seguimiento para corregirlas.",
    "APROBADO": "Tu solicitud con folio {folio} fue aprobada. Ya puedes descargar tu certificado.",
    "RECHAZADO": "Tu solicitud con folio {folio} fue resuelta como rechazada. Revisa el detalle en el seguimiento.",
}

SISTEMA = (
    "Eres un asistente que redacta avisos breves para ciudadanos que hacen trámites "
    "migratorios en Chile. Escribe en español claro, tono formal y amable, máximo dos "
    "oraciones. Usa solo los datos entregados. No inventes plazos, fechas, requisitos ni "
    "motivos. No incluyas enlaces ni datos personales. Incluye el folio tal cual."
)


def construir_prompt(tipo: str, estado: str, folio: str) -> str:
    return (
        f"Trámite: {TIPOS_TRAMITE.get(tipo, tipo)}\n"
        f"Folio: {folio}\n"
        f"Estado confirmado: {ETIQUETA_ESTADO.get(estado, estado)}\n"
        "Redacta el aviso para el ciudadano."
    )


def _llamar_modelo(prompt: str) -> str:
    """Llamada real a Gemini. Usa las credenciales de la cuenta de servicio de Cloud Run."""
    from google import genai
    from google.genai import types

    cliente = genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.vertex_location,
        http_options=types.HttpOptions(timeout=8000),  # milisegundos
    )
    respuesta = cliente.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SISTEMA, temperature=0.2, max_output_tokens=1024
        ),
    )
    return (respuesta.text or "").strip()


def validar_salida(texto: str, folio: str) -> bool:
    """La salida de la IA se trata como no confiable: debe traer el folio y ser corta."""
    t = texto.lower()
    return bool(texto) and folio in texto and len(texto) <= 400 and "http" not in t and "www." not in t


def redactar_aviso(tipo: str, estado: str, folio: str) -> tuple[str, str]:
    """Devuelve (mensaje, generado_por) con generado_por en {"ia", "plantilla"}."""
    plantilla = PLANTILLAS.get(estado, "Tu solicitud con folio {folio} cambió de estado.").format(folio=folio)
    if not settings.ia_habilitada:
        return plantilla, "plantilla"
    try:
        texto = _llamar_modelo(construir_prompt(tipo, estado, folio))
        if validar_salida(texto, folio):
            return texto, "ia"
        log.warning("Salida de IA descartada por validación")
    except Exception as exc:  # noqa: BLE001
        log.warning("IA no disponible, se usa plantilla: %s", exc)
    return plantilla, "plantilla"
