"""Almacenamiento de adjuntos y certificados (Cloud Storage; disco local en pruebas)."""
from pathlib import Path

from .config import settings


class AlmacenLocal:
    def __init__(self, base: str):
        self.base = Path(base)

    def guardar(self, ruta: str, datos: bytes, content_type: str) -> None:
        destino = self.base / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)

    def leer(self, ruta: str) -> bytes:
        return (self.base / ruta).read_bytes()


class AlmacenGCS:
    def __init__(self, bucket: str):
        from google.cloud import storage  # import diferido: no se necesita en modo local

        self.bucket = storage.Client().bucket(bucket)

    def guardar(self, ruta: str, datos: bytes, content_type: str) -> None:
        self.bucket.blob(ruta).upload_from_string(datos, content_type=content_type)

    def leer(self, ruta: str) -> bytes:
        return self.bucket.blob(ruta).download_as_bytes()


_almacen = None


def get_almacen():
    global _almacen
    if _almacen is None:
        if settings.local_mode:
            _almacen = AlmacenLocal(settings.local_storage_dir)
        else:
            _almacen = AlmacenGCS(settings.bucket)
    return _almacen


def reiniciar_almacen() -> None:
    global _almacen
    _almacen = None
