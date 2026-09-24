import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

_ph = PasswordHasher()
ALGO = "HS256"


# --- Mots de passe ---
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


# --- Access token (JWT, courte durée) ---
def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm=ALGO)


def decode_access_token(token: str) -> int | None:
    try:
        data = jwt.decode(token, settings.JWT_SECRET.get_secret_value(), algorithms=[ALGO])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# --- Refresh token (opaque, seul le hash est stocké) ---
def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Retourne (token_en_clair, hash)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)