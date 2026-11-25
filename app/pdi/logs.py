"""Logs estructurados en JSON (Cloud Logging los interpreta automáticamente)."""
import json
import sys
from datetime import datetime, timezone


def log(severity: str, message: str, **campos) -> None:
    registro = {
        "severity": severity,
        "message": message,
        "time": datetime.now(timezone.utc).isoformat(),
        **campos,
    }
    print(json.dumps(registro, ensure_ascii=False, default=str), file=sys.stdout, flush=True)


def info(message: str, **campos) -> None:
    log("INFO", message, **campos)


def warning(message: str, **campos) -> None:
    log("WARNING", message, **campos)


def error(message: str, **campos) -> None:
    log("ERROR", message, **campos)
