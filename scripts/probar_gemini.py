#!/usr/bin/env python3
"""Verifica que el proyecto puede llamar a Gemini en Vertex AI ANTES de desplegar.

  pip install --user google-genai
  python3 probar_gemini.py --proyecto TU_PROYECTO
"""
import argparse

from google import genai

ap = argparse.ArgumentParser()
ap.add_argument("--proyecto", required=True)
ap.add_argument("--ubicacion", default="global")
ap.add_argument("--modelo", default="gemini-3.5-flash-lite")
a = ap.parse_args()

cliente = genai.Client(vertexai=True, project=a.proyecto, location=a.ubicacion)
r = cliente.models.generate_content(
    model=a.modelo,
    contents="Redacta en una oración, en español formal, un aviso para el folio PDI-2026-000001: la solicitud fue aprobada.",
)
print(f"Modelo: {a.modelo} ({a.ubicacion})")
print(f"Respuesta: {r.text}")
