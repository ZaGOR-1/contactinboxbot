"""User administration routes."""

from __future__ import annotations

from math import ceil
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin_session, verify_csrf_request
from app.core.security import create_csrf_pair, set_csrf_cookie
from app.db.database import get_db_session
from app.db.models import MessageStatus
from app.db.repositories import MessageRepository, UserRepository
from app.services.message_service import MessageService
from app.services.telegram_service import TelegramService


router = APIRouter(tags=["users"])

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100


@router.get("/users")
async def users_page(
    request: Request,
    q: str | None = None,
    blocked: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    admin_session = require_admin_session(request, request.app.state.settings)
    normalized_page = max(page, 1)
    normalized_per_page = min(max(per_page, 1), MAX_PER_PAGE)
    blocked_filter = parse_blocked_filter(blocked)

    users = UserRepository(db_session)
    total = await users.count(search=q, is_blocked=blocked_filter)
    rows = await users.list_users_with_message_counts(
        search=q,
        is_blocked=blocked_filter,
        limit=normalized_per_page,
        offset=(normalized_page - 1) * normalized_per_page,
    )

    csrf_token, csrf_digest = create_csrf_pair(request.app.state.settings)
    response = request.app.state.templates.TemplateResponse(
        request,
        "users.html",
        {
            "admin_session": admin_session,
            "csrf_token": csrf_token,
            "rows": rows,
            "filters": {
                "q": q or "",
                "blocked": blocked or "",
            },
            "pagination": {
                "page": normalized_page,
                "per_page": normalized_per_page,
                "total": total,
                "pages": max(ceil(total / normalized_per_page), 1),
                "prev_url": build_users_url(request, normalized_page - 1) if normalized_page > 1 else None,
                "next_url": build_users_url(request, normalized_page + 1)
                if normalized_page * normalized_per_page < total
                else None,
            },
            "flash": request.query_params.get("message"),
        },
    )
    set_csrf_cookie(response, csrf_digest, request.app.state.settings)
    return response


@router.get("/users/{user_id}")
async def user_detail_page(
    user_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    admin_session = require_admin_session(request, request.app.state.settings)
    user = await UserRepository(db_session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    conversation = await MessageRepository(db_session).list_user_conversation(user_id=user.id)
    csrf_token, csrf_digest = create_csrf_pair(request.app.state.settings)
    response = request.app.state.templates.TemplateResponse(
        request,
        "user_detail.html",
        {
            "admin_session": admin_session,
            "csrf_token": csrf_token,
            "user": user,
            "conversation": conversation,
            "flash": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
    )
    set_csrf_cookie(response, csrf_digest, request.app.state.settings)
    return response


@router.post("/users/{user_id}/reply")
async def reply_to_user(
    user_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    require_admin_session(request, request.app.state.settings)
    await verify_csrf_request(request, request.app.state.settings)
    form = await request.form()
    reply_text = str(form.get("text", "")).strip()

    user = await UserRepository(db_session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not reply_text:
        return redirect_to_user(user_id, error="flash.reply_required")
    if user.is_blocked:
        return redirect_to_user(user_id, error="flash.user_is_blocked")

    message_service = MessageService(db_session)
    try:
        telegram_message_id = await TelegramService(request.app.state.settings).send_text_to_user(
            user=user,
            text=reply_text,
        )
    except Exception as exc:
        await message_service.save_outgoing_text(
            user=user,
            text=reply_text,
            status=MessageStatus.failed,
            error_text=str(exc),
        )
        await db_session.commit()
        return redirect_to_user(user_id, error="flash.reply_failed")

    await message_service.save_outgoing_text(
        user=user,
        text=reply_text,
        status=MessageStatus.answered,
        telegram_message_id=telegram_message_id,
    )
    await MessageRepository(db_session).mark_user_incoming_as_answered(user.id)
    await db_session.commit()
    return redirect_to_user(user_id, message="flash.reply_sent")


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    require_admin_session(request, request.app.state.settings)
    await verify_csrf_request(request, request.app.state.settings)
    user = await UserRepository(db_session).set_blocked(user_id, True)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db_session.commit()
    return redirect_to_user(user_id, message="flash.user_blocked")


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    require_admin_session(request, request.app.state.settings)
    await verify_csrf_request(request, request.app.state.settings)
    user = await UserRepository(db_session).set_blocked(user_id, False)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db_session.commit()
    return redirect_to_user(user_id, message="flash.user_unblocked")


@router.post("/users/{user_id}/read")
async def mark_user_messages_read(
    user_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    require_admin_session(request, request.app.state.settings)
    await verify_csrf_request(request, request.app.state.settings)
    user = await UserRepository(db_session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await MessageRepository(db_session).mark_user_incoming_as_read(user.id)
    await db_session.commit()
    return redirect_to_user(user_id, message="flash.incoming_read")


def parse_blocked_filter(value: str | None) -> bool | None:
    if value in {None, ""}:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "blocked"}:
        return True
    if normalized in {"0", "false", "no", "active", "not_blocked"}:
        return False
    return None


def build_users_url(request: Request, page: int) -> str:
    params = dict(request.query_params)
    params.pop("message", None)
    params.pop("error", None)
    params["page"] = str(page)
    return f"/users?{urlencode(params)}"


def redirect_to_user(user_id: int, *, message: str | None = None, error: str | None = None) -> RedirectResponse:
    params = {}
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(
        f"/users/{user_id}{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
