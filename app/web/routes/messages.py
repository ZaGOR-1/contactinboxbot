"""Message administration routes."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from math import ceil
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin_session, verify_csrf_request
from app.core.security import create_csrf_pair, set_csrf_cookie
from app.db.database import get_db_session
from app.db.models import MessageDirection, MessageStatus
from app.db.repositories import MessageRepository


router = APIRouter(tags=["messages"])

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100


@router.get("/messages")
async def messages_page(
    request: Request,
    q: str | None = None,
    status_filter: str | None = None,
    direction_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    admin_session = require_admin_session(request, request.app.state.settings)
    normalized_page = max(page, 1)
    normalized_per_page = min(max(per_page, 1), MAX_PER_PAGE)

    message_status = parse_message_status(status_filter or request.query_params.get("status"))
    message_direction = parse_message_direction(direction_filter or request.query_params.get("direction"))
    parsed_date_from = parse_start_date(date_from)
    parsed_date_to = parse_end_date(date_to)

    messages = MessageRepository(db_session)
    total = await messages.count_filtered_messages(
        search=q,
        status=message_status,
        direction=message_direction,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )
    items = await messages.search_messages(
        search=q,
        status=message_status,
        direction=message_direction,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        limit=normalized_per_page,
        offset=(normalized_page - 1) * normalized_per_page,
    )

    csrf_token, csrf_digest = create_csrf_pair(request.app.state.settings)
    response = request.app.state.templates.TemplateResponse(
        request,
        "messages.html",
        {
            "admin_session": admin_session,
            "csrf_token": csrf_token,
            "messages": items,
            "filters": {
                "q": q or "",
                "status": message_status.value if message_status else "",
                "direction": message_direction.value if message_direction else "",
                "date_from": date_from or "",
                "date_to": date_to or "",
            },
            "pagination": {
                "page": normalized_page,
                "per_page": normalized_per_page,
                "total": total,
                "pages": max(ceil(total / normalized_per_page), 1),
                "prev_url": build_messages_url(request, normalized_page - 1) if normalized_page > 1 else None,
                "next_url": build_messages_url(request, normalized_page + 1)
                if normalized_page * normalized_per_page < total
                else None,
            },
            "status_options": [item.value for item in MessageStatus],
            "direction_options": [item.value for item in MessageDirection],
            "flash": request.query_params.get("message"),
            "current_url": build_current_url(request),
        },
    )
    set_csrf_cookie(response, csrf_digest, request.app.state.settings)
    return response


@router.get("/messages/{message_id}")
async def message_detail_page(
    message_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    admin_session = require_admin_session(request, request.app.state.settings)
    message = await MessageRepository(db_session).get_by_id(message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    csrf_token, csrf_digest = create_csrf_pair(request.app.state.settings)
    response = request.app.state.templates.TemplateResponse(
        request,
        "message_detail.html",
        {
            "admin_session": admin_session,
            "csrf_token": csrf_token,
            "message": message,
            "back_url": request.query_params.get("next") or "/messages",
            "flash": request.query_params.get("message"),
        },
    )
    set_csrf_cookie(response, csrf_digest, request.app.state.settings)
    return response


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    require_admin_session(request, request.app.state.settings)
    await verify_csrf_request(request, request.app.state.settings)

    message = await MessageRepository(db_session).mark_as_read(message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    await db_session.commit()
    next_url = safe_next_url(str((await request.form()).get("next") or f"/messages/{message_id}"))
    separator = "&" if "?" in next_url else "?"
    return RedirectResponse(
        f"{next_url}{separator}message=Marked as read.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def parse_message_status(value: str | None) -> MessageStatus | None:
    if not value:
        return None
    try:
        return MessageStatus(value)
    except ValueError:
        return None


def parse_message_direction(value: str | None) -> MessageDirection | None:
    if not value:
        return None
    try:
        return MessageDirection(value)
    except ValueError:
        return None


def parse_start_date(value: str | None) -> datetime | None:
    parsed_date = parse_date(value)
    if parsed_date is None:
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=UTC)


def parse_end_date(value: str | None) -> datetime | None:
    parsed_date = parse_date(value)
    if parsed_date is None:
        return None
    return datetime.combine(parsed_date, time.max, tzinfo=UTC)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_messages_url(request: Request, page: int) -> str:
    params = dict(request.query_params)
    params.pop("message", None)
    params["page"] = str(page)
    return f"/messages?{urlencode(params)}"


def build_current_url(request: Request) -> str:
    query = str(request.url.query)
    return f"{request.url.path}?{query}" if query else request.url.path


def safe_next_url(value: str) -> str:
    if value.startswith("/") and not value.startswith("//"):
        return value
    return "/messages"
