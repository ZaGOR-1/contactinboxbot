"""Dashboard route for the private admin panel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin_session
from app.core.security import create_csrf_pair, set_csrf_cookie
from app.db.database import get_db_session
from app.db.models import MessageStatus
from app.db.repositories import MessageRepository, UserRepository


router = APIRouter(tags=["dashboard"])


@router.get("/")
async def dashboard(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> Any:
    admin_session = require_admin_session(request, request.app.state.settings)

    users = UserRepository(db_session)
    messages = MessageRepository(db_session)

    total_users = await users.count()
    total_messages = await messages.count()
    new_messages = await messages.count(status=MessageStatus.new)
    blocked_users = await users.count(is_blocked=True)
    latest_messages = await messages.latest_messages(limit=10)

    csrf_token, csrf_digest = create_csrf_pair(request.app.state.settings)
    response = request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "admin_session": admin_session,
            "csrf_token": csrf_token,
            "stats": {
                "total_users": total_users,
                "total_messages": total_messages,
                "new_messages": new_messages,
                "blocked_users": blocked_users,
            },
            "latest_messages": latest_messages,
        },
    )
    set_csrf_cookie(response, csrf_digest, request.app.state.settings)
    return response
