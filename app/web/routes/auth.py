"""Authentication routes for the private admin panel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.permissions import get_client_ip, require_admin_session, verify_csrf_request
from app.core.security import (
    PENDING_2FA_COOKIE_NAME,
    clear_csrf_cookie,
    clear_pending_2fa_cookie,
    clear_session_cookie,
    create_csrf_pair,
    create_pending_2fa_cookie_value,
    create_signed_session,
    load_pending_2fa_cookie_value,
    set_csrf_cookie,
    set_pending_2fa_cookie,
    set_session_cookie,
)
from app.db.database import get_db_session
from app.services.auth_service import AuthService
from app.services.two_factor_service import TwoFactorService


router = APIRouter(tags=["auth"])


def templates(request: Request) -> Any:
    return request.app.state.templates


def settings(request: Request) -> Settings:
    return request.app.state.settings


def redirect_to(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)


def render_with_csrf(
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
    *,
    status_code: int = status.HTTP_200_OK,
) -> Any:
    csrf_token, csrf_digest = create_csrf_pair(settings(request))
    response = templates(request).TemplateResponse(
        request,
        template_name,
        {
            "csrf_token": csrf_token,
            **(context or {}),
        },
        status_code=status_code,
    )
    set_csrf_cookie(response, csrf_digest, settings(request))
    return response


@router.get("/login")
async def login_page(request: Request) -> Any:
    if require_optional_session(request):
        return redirect_to("/")
    return render_with_csrf(
        request,
        "login.html",
        {
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    await verify_csrf_request(request, settings(request))
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    if not username or not password:
        return render_with_csrf(
            request,
            "login.html",
            {"error": "Username and password are required.", "username": username},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    auth_service = AuthService(db_session)
    result = await auth_service.authenticate(
        username=username,
        password=password,
        ip_address=get_client_ip(request),
    )

    if not result.success or result.admin_user is None:
        await db_session.commit()
        return render_with_csrf(
            request,
            "login.html",
            {"error": result.message, "username": username},
            status_code=status.HTTP_401_UNAUTHORIZED if not result.locked else status.HTTP_429_TOO_MANY_REQUESTS,
        )

    app_settings = settings(request)
    if app_settings.enable_telegram_2fa:
        try:
            await TwoFactorService(db_session, app_settings).create_and_send_code(result.admin_user)
        except RuntimeError as exc:
            await db_session.rollback()
            return render_with_csrf(
                request,
                "login.html",
                {"error": str(exc), "username": username},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        await db_session.commit()
        response = redirect_to("/2fa")
        signed_pending_2fa = create_pending_2fa_cookie_value(
            admin_user_id=result.admin_user.id,
            username=result.admin_user.username,
            settings=app_settings,
        )
        set_pending_2fa_cookie(response, signed_pending_2fa, app_settings)
        clear_csrf_cookie(response, app_settings)
        return response

    await auth_service.mark_login_success(result.admin_user.id)
    await db_session.commit()
    response = redirect_to("/")
    set_session_cookie(
        response,
        create_signed_session(
            admin_user_id=result.admin_user.id,
            username=result.admin_user.username,
            settings=app_settings,
        ),
        app_settings,
    )
    clear_pending_2fa_cookie(response, app_settings)
    clear_csrf_cookie(response, app_settings)
    return response


@router.get("/2fa")
async def two_factor_page(request: Request) -> Any:
    pending = load_pending_2fa_cookie_value(
        request.cookies.get(PENDING_2FA_COOKIE_NAME),
        settings(request),
    )
    if pending is None:
        return redirect_to("/login")
    return render_with_csrf(request, "two_factor.html", {"username": pending.username})


@router.post("/2fa")
async def two_factor_submit(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    app_settings = settings(request)
    await verify_csrf_request(request, app_settings)

    pending = load_pending_2fa_cookie_value(
        request.cookies.get(PENDING_2FA_COOKIE_NAME),
        app_settings,
    )
    if pending is None:
        return redirect_to("/login")

    form = await request.form()
    code = str(form.get("code", "")).strip()
    result = await TwoFactorService(db_session, app_settings).verify_code(
        admin_user_id=pending.admin_user_id,
        submitted_code=code,
    )

    if not result.success:
        await db_session.commit()
        return render_with_csrf(
            request,
            "two_factor.html",
            {"error": result.message, "username": pending.username},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    await AuthService(db_session).mark_login_success(pending.admin_user_id)
    await db_session.commit()

    response = redirect_to("/")
    set_session_cookie(
        response,
        create_signed_session(
            admin_user_id=pending.admin_user_id,
            username=pending.username,
            settings=app_settings,
        ),
        app_settings,
    )
    clear_pending_2fa_cookie(response, app_settings)
    clear_csrf_cookie(response, app_settings)
    return response


@router.post("/logout")
async def logout_submit(request: Request) -> RedirectResponse:
    app_settings = settings(request)
    require_admin_session(request, app_settings)
    await verify_csrf_request(request, app_settings)

    response = redirect_to("/login?message=Logged out.")
    clear_session_cookie(response, app_settings)
    clear_pending_2fa_cookie(response, app_settings)
    clear_csrf_cookie(response, app_settings)
    return response


def require_optional_session(request: Request) -> bool:
    try:
        require_admin_session(request, settings(request))
    except Exception:
        return False
    return True
