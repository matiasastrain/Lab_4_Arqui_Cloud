"""Generación del certificado en PDF (documento de prueba, sin validez legal)."""
from __future__ import annotations

import hashlib

from fpdf import FPDF

from .config import get_config
from .db import TIPOS, Tramite


def codigo_verificacion(folio: str) -> str:
    h = hashlib.sha256(f"{folio}:{get_config().jwt_secret}".encode()).hexdigest()
    return h[:12].upper()


def generar_pdf(t: Tramite, fecha_aprobacion) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    ancho = pdf.w - 40

    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(ancho, 9, "POLICÍA DE INVESTIGACIONES DE CHILE", align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(ancho, 7, "Jefatura Nacional de Migraciones y Policía Internacional", align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(ancho, 8, TIPOS.get(t.tipo, {}).get("nombre", t.tipo).upper(), align="C")
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 11)
    filas = [
        ("Folio", t.folio),
        ("Nombre", t.nombre),
        ("RUT", t.rut),
        ("Fecha de aprobación", fecha_aprobacion.strftime("%d-%m-%Y %H:%M UTC")),
        ("Código de verificación", codigo_verificacion(t.folio)),
    ]
    for etiqueta, valor in filas:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(60, 8, f"{etiqueta}:")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(ancho - 60, 8, str(valor))

    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        ancho,
        6,
        "Se certifica que el trámite individualizado fue revisado y aprobado por un "
        "funcionario de la institución, de acuerdo con los antecedentes registrados.",
    )
    pdf.ln(14)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        ancho,
        5,
        "Documento generado por una prueba de concepto académica (TICS400). "
        "No tiene validez legal. Los antecedentes provienen de sistemas simulados.",
        align="C",
    )
    return bytes(pdf.output())
