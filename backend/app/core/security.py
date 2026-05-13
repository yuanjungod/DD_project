from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(subject: str, role: str) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": int(time.time()) + settings.token_ttl_seconds,
    }
    encoded_payload = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(encoded_payload)
    return f"{encoded_payload}.{signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(encoded_payload), signature):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(_pad(encoded_payload)).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def _sign(value: str) -> str:
    digest = hmac.new(settings.auth_secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _pad(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("utf-8")
