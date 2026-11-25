"""Punto de entrada único. La misma imagen cambia de rol según APP_MODE:

  gestor          API de trámites (portal -> gestor)
  notificaciones  recibe las tareas de Cloud Tasks y redacta el aviso
  adaptadores     simula GEPOL y B3000
"""
import os

modo = os.environ.get("APP_MODE", "gestor")

if modo == "notificaciones":
    from pdi.notificaciones import crear_app
elif modo == "adaptadores":
    from pdi.adaptadores import crear_app
elif modo == "gestor":
    from pdi.gestor import crear_app
else:
    raise SystemExit(f"APP_MODE desconocido: {modo}")

app = crear_app()
