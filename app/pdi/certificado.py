"""Generación del certificado en PDF (reportlab)."""
import io
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from .config import TIPOS_TRAMITE
from .db import Tramite


def generar_certificado_pdf(t: Tramite) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    ancho, alto = A4
    c.setTitle(f"Certificado {t.folio}")
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(ancho / 2, alto - 3 * cm, "PRUEBA DE CONCEPTO - PDI MIGRACIONES")
    c.setFont("Helvetica", 12)
    c.drawCentredString(ancho / 2, alto - 4 * cm, TIPOS_TRAMITE.get(t.tipo, t.tipo))
    y = alto - 6.5 * cm
    for etiqueta, valor in (
        ("Folio", t.folio),
        ("Solicitante", t.nombre),
        ("RUT", t.rut),
        ("Fecha de emisión", datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")),
    ):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(3 * cm, y, f"{etiqueta}:")
        c.setFont("Helvetica", 11)
        c.drawString(7 * cm, y, str(valor))
        y -= 0.9 * cm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(3 * cm, 3 * cm, "Documento generado con datos sintéticos para el Laboratorio 3 de TICS400.")
    c.drawString(3 * cm, 2.5 * cm, "No tiene validez legal.")
    c.showPage()
    c.save()
    return buf.getvalue()
