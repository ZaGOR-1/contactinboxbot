"""Language switch route for the admin UI."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from app.web.i18n import LANG_COOKIE_NAME, SUPPORTED_LANGUAGES


router = APIRouter(tags=["language"])


@router.get("/language/{language}")
async def switch_language(language: str, request: Request, next: str = "/") -> RedirectResponse:
    selected_language = language if language in SUPPORTED_LANGUAGES else "uk"
    response = RedirectResponse(safe_next_url(next), status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=LANG_COOKIE_NAME,
        value=selected_language,
        max_age=60 * 60 * 24 * 365,
        secure=request.app.state.settings.session_cookie_secure,
        httponly=True,
        samesite=request.app.state.settings.session_cookie_samesite,
    )
    return response


def safe_next_url(value: str) -> str:
    if value.startswith("/") and not value.startswith("//"):
        return value
    return "/"
