#!/usr/bin/env python3
"""Comprueba que Gemini en Vertex AI responde ANTES de desplegar todo.

  pip install google-genai
  python3 scripts/probar_gemini.py --proyecto pdi-cloud-515801 [--modelo M] [--ubicacion global]

Si el modelo indicado no está disponible, prueba otros candidatos e indica
cuál usar con -var="gemini_modelo=..." al desplegar.
"""
import argparse
import sys

CANDIDATOS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


def probar(cliente, types, modelo):
    prompt = ("Redacta en una oración un aviso formal para un ciudadano indicando que su trámite "
              "folio CV-2026-000001 fue recibido. Sin enlaces.")
    try:
        cfg = types.GenerateContentConfig(temperature=0.3, max_output_tokens=1024,
                                          thinking_config=types.ThinkingConfig(thinking_budget=0))
        r = cliente.models.generate_content(model=modelo, contents=prompt, config=cfg)
    except Exception:
        cfg = types.GenerateContentConfig(temperature=0.3, max_output_tokens=1024)
        r = cliente.models.generate_content(model=modelo, contents=prompt, config=cfg)
    return (r.text or "").strip(), getattr(r, "usage_metadata", None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proyecto", required=True)
    p.add_argument("--ubicacion", default="global")
    p.add_argument("--modelo", default=CANDIDATOS[0])
    a = p.parse_args()

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        sys.exit("Falta el SDK: pip install google-genai")

    cliente = genai.Client(vertexai=True, project=a.proyecto, location=a.ubicacion)
    orden = [a.modelo] + [m for m in CANDIDATOS if m != a.modelo]
    for modelo in orden:
        try:
            texto, uso = probar(cliente, types, modelo)
            print(f"OK  {modelo} ({a.ubicacion})\n    Respuesta: {texto}")
            if uso:
                print(f"    Tokens: entrada={uso.prompt_token_count} salida={uso.candidates_token_count} "
                      f"razonamiento={getattr(uso, 'thoughts_token_count', None)}")
            if modelo != a.modelo:
                print(f"\nEl modelo {a.modelo} no respondió. Despliegue con:\n"
                      f"  ./scripts/deploy.sh {a.proyecto} dev -var=gemini_modelo={modelo}")
            return
        except Exception as e:
            print(f"--  {modelo}: {str(e)[:160]}")
    sys.exit("\nNingún modelo respondió. Revise la API aiplatform.googleapis.com, la ubicación o las cuotas.\n"
             "Puede desplegar igual con -var=ia_habilitada=false (los avisos usarán la plantilla).")


if __name__ == "__main__":
    main()
