"""Configuración central. Nunca guardar secretos en el repositorio."""
import os
from zoneinfo import ZoneInfo


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "")
    if not value:
        raise RuntimeError("Definir DATABASE_URL (PostgreSQL) antes de ejecutar el backend")
    return value


def jwt_secret() -> str:
    value = os.getenv("AUTH_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("AUTH_SECRET debe tener al menos 32 caracteres aleatorios")
    return value


def business_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/Santo_Domingo"))


def cpa_max_age_hours() -> int:
    value = int(os.getenv("CPA_MAX_AGE_HOURS", "24"))
    if value < 1:
        raise ValueError("CPA_MAX_AGE_HOURS debe ser mayor que cero")
    return value
