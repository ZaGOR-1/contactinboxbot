"""FastAPI web admin application factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> Any:
    app_settings = settings or get_settings()
    configure_logging(app_settings)

    from fastapi import FastAPI, Request
    from fastapi.exceptions import HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from starlette.exceptions import HTTPException as StarletteHTTPException

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    from app.web.i18n import get_language, translate

    templates.env.globals["current_lang"] = get_language
    templates.env.globals["t"] = translate

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.is_development,
        docs_url=app_settings.docs_url,
        redoc_url=app_settings.redoc_url,
        openapi_url=app_settings.openapi_url,
    )

    app.state.settings = app_settings
    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    from app.web.routes.auth import router as auth_router
    from app.web.routes.dashboard import router as dashboard_router
    from app.web.routes.language import router as language_router
    from app.web.routes.messages import router as messages_router
    from app.web.routes.service import router as service_router
    from app.web.routes.users import router as users_router

    app.include_router(service_router)
    app.include_router(language_router)
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(messages_router)
    app.include_router(users_router)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> HTMLResponse:
        location = exc.headers.get("Location") if exc.headers else None
        if 300 <= exc.status_code < 400 and location:
            return RedirectResponse(location, status_code=exc.status_code)
        if exc.status_code >= 500:
            logger.error("HTTP exception", extra={"status_code": exc.status_code, "path": request.url.path})
        return render_error_page(request, exc.status_code, templates)

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> HTMLResponse:
        location = exc.headers.get("Location") if exc.headers else None
        if 300 <= exc.status_code < 400 and location:
            return RedirectResponse(location, status_code=exc.status_code)
        if exc.status_code >= 500:
            logger.error("HTTP exception", extra={"status_code": exc.status_code, "path": request.url.path})
        return render_error_page(request, exc.status_code, templates)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
        logger.exception("Unhandled web exception", exc_info=exc)
        return render_error_page(request, 500, templates)

    return app


def render_error_page(request: Any, status_code: int, templates: Any) -> Any:
    response_status_code = status_code if 400 <= status_code < 600 else 500
    normalized_status_code = (
        404
        if response_status_code == 404
        else 403
        if response_status_code < 500
        else 500
    )
    template_name = {
        403: "errors/403.html",
        404: "errors/404.html",
        500: "errors/500.html",
    }[normalized_status_code]

    return templates.TemplateResponse(
        request,
        template_name,
        {"status_code": response_status_code},
        status_code=response_status_code,
    )


try:
    app = create_app()
except (ImportError, ModuleNotFoundError) as exc:
    logger.warning("Web app dependencies are not installed yet: %s", exc)
    app = None
