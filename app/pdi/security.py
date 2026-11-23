"""RUT, tokens de sesión y control de acceso por rol.

ClaveÚnica no se integra en la prueba de concepto: el ingreso del ciudadano es
simulado (basta un RUT válido) y el del funcionario usa una clave guardada en
Secret Manager. En producción esto lo reemplazan ClaveÚnica e IAP con MFA.
"""
import hmac
import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- RUT
def normalizar_rut(rut: str) -> str:
    limpio = re.sub(r"[^0-9kK]", "", rut or "").upper()
    if len(limpio) < 2:
        return ""
    return f"{int(limpio[:-1])}-{limpio[-1]}"


def digito_verificador(cuerpo: int) -> str:
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return "0" if resto == 11 else "K" if resto == 10 else str(resto)


def validar_rut(rut: str) -> bool:
    norm = normalizar_rut(rut)
    if not norm:
        return False
    cuerpo, dv = norm.split("-")
    return 1_000_000 <= int(cuerpo) <= 99_999_999 and digito_verificador(int(cuerpo)) == dv


# ---------------------------------------------------------------- tokens
class Usuario:
    def __init__(self, sub: str, rol: str):
        self.sub = sub
        self.rol = rol


def crear_token(sub: str, rol: str, horas: int = 2) -> str:
    ahora = datetime.now(timezone.utc)
    claims = {"sub": sub, "rol": rol, "iat": ahora, "exp": ahora + timedelta(hours=horas)}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def clave_funcionario_valida(clave: str) -> bool:
    esperada = settings.funcionario_api_key
    return bool(esperada) and hmac.compare_digest(clave.encode(), esperada.encode())


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Usuario:
    if cred is None:
        raise HTTPException(401, "Falta el token de sesión")
    try:
        datos = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido o vencido") from None
    return Usuario(datos["sub"], datos["rol"])


def solo_ciudadano(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != "ciudadano":
        raise HTTPException(403, "Operación reservada al ciudadano")
    return u


def solo_funcionario(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != "funcionario":
        raise HTTPException(403, "Operación reservada al funcionario")
    return u
