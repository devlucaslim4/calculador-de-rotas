"""Autenticação e assinatura dos links temporários."""

from __future__ import annotations

import hashlib
import hmac
import time


def api_key_matches(expected: str, provided: str | None) -> bool:
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))


def create_download_token(secret: str, file_id: str, expires_at: int) -> str:
    payload = f"{file_id}:{expires_at}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{expires_at}.{signature}"


def verify_download_token(
    secret: str,
    file_id: str,
    token: str,
    *,
    now: int | None = None,
) -> int | None:
    try:
        expires_text, signature = token.split(".", 1)
        expires_at = int(expires_text)
    except (AttributeError, TypeError, ValueError):
        return None
    current = int(time.time()) if now is None else int(now)
    if expires_at < current:
        return None
    expected = create_download_token(secret, file_id, expires_at).split(".", 1)[1]
    if not hmac.compare_digest(expected, signature):
        return None
    return expires_at

