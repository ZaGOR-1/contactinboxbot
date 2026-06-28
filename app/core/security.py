"""Security helpers for passwords, signed sessions, and CSRF protection."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings


SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
CSRF_TOKEN_BYTES = 32
CSRF_COOKIE_NAME = "telegram_inbox_csrf"
PENDING_2FA_COOKIE_NAME = "telegram_inbox_pending_2fa"
PENDING_2FA_MAX_AGE_SECONDS = 60 * 5
PBKDF2_ITERATIONS = 390_000


@dataclass(frozen=True)
class SessionData:
    admin_user_id: int
    username: str
    issued_at: int


@dataclass(frozen=True)
class PendingTwoFactorData:
    admin_user_id: int
    username: str
    issued_at: int


class PasswordHasher:
    """Password hashing facade based on PBKDF2-SHA256.

    The project originally allowed passlib/bcrypt, but bcrypt rejects passwords
    longer than 72 bytes. PBKDF2 keeps admin password handling dependency-light
    and avoids surprising failures for long or non-ASCII passwords.
    """

    def hash(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PBKDF2_ITERATIONS,
        ).hex()
        return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"

    def verify(self, password: str, password_hash: str) -> bool:
        if password_hash.startswith("pbkdf2_sha256$"):
            return self._verify_pbkdf2(password, password_hash)
        return False

    def _verify_pbkdf2(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, iterations, salt, expected = password_hash.split("$", 3)
        except ValueError:
            return False

        if algorithm != "pbkdf2_sha256":
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return secrets.compare_digest(digest, expected)


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def csrf_token_digest(token: str, settings: Settings | None = None) -> str:
    app_settings = settings or get_settings()
    secret = app_settings.secret_key.get_secret_value()
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_csrf_token(
    submitted_token: str | None,
    expected_digest: str | None,
    settings: Settings | None = None,
) -> bool:
    if not submitted_token or not expected_digest:
        return False
    actual_digest = csrf_token_digest(submitted_token, settings)
    return secrets.compare_digest(actual_digest, expected_digest)


def create_csrf_pair(settings: Settings | None = None) -> tuple[str, str]:
    token = generate_csrf_token()
    return token, csrf_token_digest(token, settings)


def set_csrf_cookie(response: Any, token_digest: str, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token_digest,
        secure=app_settings.session_cookie_secure,
        httponly=True,
        samesite=app_settings.session_cookie_samesite,
    )


def clear_csrf_cookie(response: Any, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        secure=app_settings.session_cookie_secure,
        httponly=True,
        samesite=app_settings.session_cookie_samesite,
    )


def create_session_payload(admin_user_id: int, username: str) -> dict[str, Any]:
    return {
        "admin_user_id": admin_user_id,
        "username": username,
        "issued_at": int(time.time()),
    }


def sign_data(data: dict[str, Any], settings: Settings | None = None) -> str:
    app_settings = settings or get_settings()
    secret = app_settings.secret_key.get_secret_value()
    raw_payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload = _base64_url_encode(raw_payload)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_base64_url_encode(signature)}"


def unsign_data(
    signed_value: str | None,
    settings: Settings | None = None,
    *,
    max_age_seconds: int | None = None,
) -> dict[str, Any] | None:
    if not signed_value or "." not in signed_value:
        return None

    app_settings = settings or get_settings()
    secret = app_settings.secret_key.get_secret_value()
    payload, signature = signed_value.rsplit(".", 1)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()

    try:
        provided_signature = _base64_url_decode(signature)
    except (binascii.Error, ValueError):
        return None

    if not secrets.compare_digest(provided_signature, expected_signature):
        return None

    try:
        data = json.loads(_base64_url_decode(payload))
    except (binascii.Error, json.JSONDecodeError, ValueError):
        return None

    if max_age_seconds is not None:
        issued_at = int(data.get("issued_at", 0))
        if issued_at <= 0 or int(time.time()) - issued_at > max_age_seconds:
            return None

    return data


def create_signed_session(
    *,
    admin_user_id: int,
    username: str,
    settings: Settings | None = None,
) -> str:
    return sign_data(create_session_payload(admin_user_id, username), settings)


def load_signed_session(
    signed_value: str | None,
    settings: Settings | None = None,
    *,
    max_age_seconds: int = SESSION_MAX_AGE_SECONDS,
) -> SessionData | None:
    data = unsign_data(signed_value, settings, max_age_seconds=max_age_seconds)
    if data is None:
        return None

    try:
        return SessionData(
            admin_user_id=int(data["admin_user_id"]),
            username=str(data["username"]),
            issued_at=int(data["issued_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def create_pending_2fa_cookie_value(
    *,
    admin_user_id: int,
    username: str,
    settings: Settings | None = None,
) -> str:
    return sign_data(create_session_payload(admin_user_id, username), settings)


def load_pending_2fa_cookie_value(
    signed_value: str | None,
    settings: Settings | None = None,
    *,
    max_age_seconds: int = PENDING_2FA_MAX_AGE_SECONDS,
) -> PendingTwoFactorData | None:
    data = unsign_data(signed_value, settings, max_age_seconds=max_age_seconds)
    if data is None:
        return None

    try:
        return PendingTwoFactorData(
            admin_user_id=int(data["admin_user_id"]),
            username=str(data["username"]),
            issued_at=int(data["issued_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def set_pending_2fa_cookie(response: Any, signed_value: str, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    response.set_cookie(
        key=PENDING_2FA_COOKIE_NAME,
        value=signed_value,
        max_age=PENDING_2FA_MAX_AGE_SECONDS,
        secure=app_settings.session_cookie_secure,
        httponly=True,
        samesite=app_settings.session_cookie_samesite,
    )


def clear_pending_2fa_cookie(response: Any, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    response.delete_cookie(
        key=PENDING_2FA_COOKIE_NAME,
        secure=app_settings.session_cookie_secure,
        httponly=True,
        samesite=app_settings.session_cookie_samesite,
    )


def set_session_cookie(response: Any, signed_session: str, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    response.set_cookie(
        key=app_settings.session_cookie_name,
        value=signed_session,
        max_age=SESSION_MAX_AGE_SECONDS,
        secure=app_settings.session_cookie_secure,
        httponly=app_settings.session_cookie_httponly,
        samesite=app_settings.session_cookie_samesite,
    )


def clear_session_cookie(response: Any, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    response.delete_cookie(
        key=app_settings.session_cookie_name,
        secure=app_settings.session_cookie_secure,
        httponly=app_settings.session_cookie_httponly,
        samesite=app_settings.session_cookie_samesite,
    )


def _base64_url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64_url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
