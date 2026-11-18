"""Autenticación local mínima con scrypt + JWT."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from backend.settings import jwt_secret


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = stored.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64)
        target = base64.urlsafe_b64decode(digest_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(target))
        return hmac.compare_digest(digest, target)
    except (ValueError, TypeError):
        return False


def sign_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=8)}, jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> int:
    payload = jwt.decode(token, jwt_secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
    return int(payload["sub"])


def hash_workstation_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
