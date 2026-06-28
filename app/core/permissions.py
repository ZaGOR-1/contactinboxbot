"""Permission helpers for the private admin panel."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.security import (
    CSRF_COOKIE_NAME,
    SessionData,
    load_signed_session,
    verify_csrf_token,
)

try:
    from fastapi import HTTPException, Request, status
except (ImportError, ModuleNotFoundError):
    HTTPException = None  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client is None:
        return ""
    return request.client.host


def is_ip_allowed(request: Request, settings: Settings | None = None) -> bool:
    app_settings = settings or get_settings()
    if not app_settings.enable_ip_allowlist:
        return True
    return get_client_ip(request) in app_settings.allowed_admin_ip_list


def get_session_from_request(
    request: Request,
    settings: Settings | None = None,
) -> SessionData | None:
    app_settings = settings or get_settings()
    signed_session = request.cookies.get(app_settings.session_cookie_name)
    return load_signed_session(signed_session, app_settings)


def require_admin_session(
    request: Request,
    settings: Settings | None = None,
) -> SessionData:
    app_settings = settings or get_settings()
    if not is_ip_allowed(request, app_settings):
        raise_forbidden()

    session = get_session_from_request(request, app_settings)
    if session is None:
        raise_forbidden()
    return session


def get_current_admin_id(request: Request) -> int:
    return require_admin_session(request).admin_user_id


async def verify_csrf_request(
    request: Request,
    settings: Settings | None = None,
) -> None:
    """Validate CSRF token for unsafe form or header based requests."""

    app_settings = settings or get_settings()
    submitted_token = request.headers.get("x-csrf-token")

    if submitted_token is None:
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            submitted_token = form.get("csrf_token") or form.get("_csrf_token")

    expected_digest = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(str(submitted_token) if submitted_token else None, expected_digest, app_settings):
        raise_forbidden()


def raise_forbidden() -> None:
    if HTTPException is None or status is None:
        raise PermissionError("Forbidden")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
