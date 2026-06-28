"""Service endpoints for health and version checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request


router = APIRouter(tags=["service"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@router.get("/version")
async def version(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "docs_enabled": settings.docs_url is not None,
    }
