"""Seguridad: validación de RUT (módulo 11), tokens JWT y roles.

ClaveÚnica está SIMULADA: el ciudadano ingresa con un RUT válido y recibe un
JWT con rol "ciudadano". El funcionario ingresa con una clave guardada en
Secret Manager y recibe un JWT con rol "funcionario".
"""
from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException

from .config import get_config

CIUDADANO = "ciudadano"
FUNCIONARIO = "funcionario"
_ALG = "HS256"


def calcular_dv(cuerpo: int) -> str:
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def normalizar_rut(rut: str) -> Optional[str]:
    """Devuelve el RUT como 12345678-5 si es válido, o None."""
    if not rut:
        return None
    limpio = re.sub(r"[.\s]", "", rut).upper()
    m = re.fullmatch(r"(\d{7,8})-?([\dK])", limpio)
    if not m:
        return None
    cuerpo, dv = int(m.group(1)), m.group(2)
    if calcular_dv(cuerpo) != dv:
        return None
    return f"{cuerpo}-{dv}"


def rut_valido(rut: str) -> bool:
    return normalizar_rut(rut) is not None


@dataclass
class Usuario:
    sub: str
    rol: str
    nombre: str = ""
    email: Optional[str] = None
    telefono: Optional[str] = None


def emitir_token(usuario: Usuario, horas: int = 8) -> str:
    payload = {
        "sub": usuario.sub,
        "rol": usuario.rol,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "telefono": usuario.telefono,
        "exp": datetime.now(timezone.utc) + timedelta(hours=horas),
    }
    return jwt.encode(payload, get_config().jwt_secret, algorithm=_ALG)


def clave_funcionario_correcta(clave: str) -> bool:
    return hmac.compare_digest((clave or "").encode(), get_config().funcionario_api_key.encode())


def usuario_actual(authorization: Optional[str] = Header(default=None)) -> Usuario:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta el token de acceso")
    token = authorization.split(" ", 1)[1]
    try:
        p = jwt.decode(token, get_config().jwt_secret, algorithms=[_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "La sesión expiró")
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido")
    return Usuario(p["sub"], p["rol"], p.get("nombre", ""), p.get("email"), p.get("telefono"))


def requiere_ciudadano(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != CIUDADANO:
        raise HTTPException(403, "Solo para ciudadanos")
    return u


def requiere_funcionario(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != FUNCIONARIO:
        raise HTTPException(403, "Solo para funcionarios")
    return u
