from __future__ import annotations

from pathlib import Path

from app.core.security import (
    CSRF_COOKIE_NAME,
    PENDING_2FA_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    clear_pending_2fa_cookie,
    clear_session_cookie,
    create_csrf_pair,
    create_pending_2fa_cookie_value,
    create_signed_session,
    hash_password,
    load_pending_2fa_cookie_value,
    load_signed_session,
    set_csrf_cookie,
    set_pending_2fa_cookie,
    set_session_cookie,
    verify_csrf_token,
    verify_password,
)

from tests.helpers import CookieRecorder, TestSettings


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_signed_session_round_trip_rejects_tampering_and_expiration() -> None:
    settings = TestSettings()

    signed = create_signed_session(admin_user_id=42, username="admin", settings=settings)
    loaded = load_signed_session(signed, settings)

    assert loaded is not None
    assert loaded.admin_user_id == 42
    assert loaded.username == "admin"

    tampered = f"{signed[:-1]}x"
    assert load_signed_session(tampered, settings) is None
    assert load_signed_session(signed, settings, max_age_seconds=-1) is None
    assert SESSION_MAX_AGE_SECONDS == 60 * 60 * 12


def test_pending_2fa_cookie_value_is_signed_and_expiring() -> None:
    settings = TestSettings()

    signed = create_pending_2fa_cookie_value(
        admin_user_id=7,
        username="admin",
        settings=settings,
    )
    loaded = load_pending_2fa_cookie_value(signed, settings)

    assert loaded is not None
    assert loaded.admin_user_id == 7
    assert loaded.username == "admin"
    assert load_pending_2fa_cookie_value(signed, settings, max_age_seconds=-1) is None


def test_csrf_pair_validates_only_matching_token_and_digest() -> None:
    settings = TestSettings()

    token, digest = create_csrf_pair(settings)

    assert verify_csrf_token(token, digest, settings)
    assert not verify_csrf_token("wrong-token", digest, settings)
    assert not verify_csrf_token(token, "wrong-digest", settings)
    assert not verify_csrf_token(None, digest, settings)
    assert not verify_csrf_token(token, None, settings)


def test_security_cookies_use_secure_httponly_samesite_flags() -> None:
    settings = TestSettings(session_cookie_secure=True, session_cookie_httponly=True)
    response = CookieRecorder()

    set_session_cookie(response, "signed-session", settings)
    set_csrf_cookie(response, "csrf-digest", settings)
    set_pending_2fa_cookie(response, "pending-2fa", settings)

    session_cookie = response.cookies[0]
    csrf_cookie = response.cookies[1]
    pending_cookie = response.cookies[2]

    assert session_cookie[0] == settings.session_cookie_name
    assert session_cookie[2]["secure"] is True
    assert session_cookie[2]["httponly"] is True
    assert session_cookie[2]["samesite"] == "lax"

    assert csrf_cookie[0] == CSRF_COOKIE_NAME
    assert csrf_cookie[2]["secure"] is True
    assert csrf_cookie[2]["httponly"] is True
    assert csrf_cookie[2]["samesite"] == "lax"

    assert pending_cookie[0] == PENDING_2FA_COOKIE_NAME
    assert pending_cookie[2]["secure"] is True
    assert pending_cookie[2]["httponly"] is True
    assert pending_cookie[2]["samesite"] == "lax"


def test_session_cookies_are_cleared_with_matching_flags() -> None:
    settings = TestSettings()
    response = CookieRecorder()

    clear_session_cookie(response, settings)
    clear_pending_2fa_cookie(response, settings)

    assert response.deleted[0][0] == settings.session_cookie_name
    assert response.deleted[0][1]["secure"] is True
    assert response.deleted[0][1]["httponly"] is True
    assert response.deleted[0][1]["samesite"] == "lax"
    assert response.deleted[1][0] == PENDING_2FA_COOKIE_NAME


def test_env_files_and_examples_do_not_expose_real_secrets() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")

    assert ".env" in gitignore
    assert "!.env.example" in gitignore
    assert "CHANGE_ME" in env_example
    assert "123456789:" not in env_example
    assert "SECRET_KEY=CHANGE_ME" in env_example
