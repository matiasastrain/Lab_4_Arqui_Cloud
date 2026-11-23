"""Punto de entrada único: la misma imagen corre tres servicios según APP_MODE."""
import os

modo = os.getenv("APP_MODE", "gestor")

if modo == "gestor":
    from .gestor import app
elif modo == "notificaciones":
    from .notificaciones import app
elif modo == "adaptadores":
    from .adaptadores import app
else:  # pragma: no cover
    raise RuntimeError(f"APP_MODE desconocido: {modo}")

__all__ = ["app"]
