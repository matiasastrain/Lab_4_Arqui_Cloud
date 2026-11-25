"""Almacenamiento de adjuntos: Cloud Storage (bucket privado) o disco local."""
from __future__ import annotations

import os

from .config import get_config

_gcs_client = None


def _bucket():
    global _gcs_client
    from google.cloud import storage

    if _gcs_client is None:
        _gcs_client = storage.Client()
    return _gcs_client.bucket(get_config().bucket)


def guardar(ruta: str, datos: bytes, content_type: str) -> None:
    c = get_config()
    if c.bucket:
        _bucket().blob(ruta).upload_from_string(datos, content_type=content_type)
        return
    destino = os.path.join(c.storage_dir, ruta)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(datos)


def leer(ruta: str) -> bytes:
    c = get_config()
    if c.bucket:
        return _bucket().blob(ruta).download_as_bytes()
    with open(os.path.join(c.storage_dir, ruta), "rb") as f:
        return f.read()
