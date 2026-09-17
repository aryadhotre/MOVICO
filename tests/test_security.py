"""Security regressions.

Each test here corresponds to a specific way the service could be attacked, and
each would pass silently if the protection were removed -- which is exactly why
they are worth pinning. A rate limiter that stops limiting, a CORS pattern that
widens by one character, or a password rule that gets relaxed during a refactor
all leave every functional test green.
"""

from __future__ import annotations

import re

import pytest

from app.api.security import SlidingWindowLimiter, login_limiter, register_limiter
from app.config.settings import PLACEHOLDER_SECRET, Settings


@pytest.fixture(autouse=True)
def _clear_limiters():
    """Limiters are process-global, so one test's attempts would count in another."""
    login_limiter._hits.clear()
    register_limiter._hits.clear()
    yield
    login_limiter._hits.clear()
    register_limiter._hits.clear()


# ------------------------------------------------------------------ boot guards


def _production(**overrides) -> dict:
    base = {
        "APP_ENV": "production",
        "SECRET_KEY": "k" * 48,
        "DEBUG": False,
        "CORS_ORIGINS": "https://movico.vercel.app",
    }
    base.update(overrides)
    return base


def test_production_refuses_placeholder_secret():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(**_production(SECRET_KEY=PLACEHOLDER_SECRET))


def test_production_refuses_short_secret():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(**_production(SECRET_KEY="short"))


def test_production_refuses_debug():
    with pytest.raises(ValueError, match="DEBUG"):
        Settings(**_production(DEBUG=True))


def test_production_refuses_unset_cors():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(**_production(CORS_ORIGINS=""))


def test_production_boots_when_configured():
    settings = Settings(**_production())
    assert settings.is_production


def test_development_tolerates_defaults():
    """The guard must not make a local checkout unrunnable."""
    assert Settings(APP_ENV="development").SECRET_KEY == PLACEHOLDER_SECRET


def test_debug_is_off_by_default():
    """The *declared* default, not an instance: a local .env may opt in, which is
    the point -- opting in is explicit and opting out is not something to forget."""
    assert Settings.model_fields["DEBUG"].default is False


def test_localhost_is_not_a_production_origin():
    origins = Settings(**_production()).cors_origins
    assert origins == ["https://movico.vercel.app"]
    assert not any("localhost" in origin for origin in origins)


# --------------------------------------------------------------- CORS behaviour


@pytest.mark.parametrize(
    "origin,allowed",
    [
        ("https://movico.vercel.app", True),
        ("https://movico-git-main-arya.vercel.app", True),
        ("https://movico-9f3a2b1.vercel.app", True),
        # The whole point: another person's Vercel project must not match.
        ("https://evil.vercel.app", False),
        ("https://notmovico.vercel.app", False),
        ("https://movico.vercel.app.evil.com", False),
        ("http://movico.vercel.app", False),
    ],
)
def test_preview_origin_regex_is_scoped_to_the_project(origin, allowed):
    pattern = Settings(**_production(VERCEL_PROJECT="movico")).cors_origin_regex
    assert bool(re.fullmatch(pattern, origin)) is allowed


def test_no_preview_regex_without_a_project_slug():
    assert Settings(**_production()).cors_origin_regex is None


# ------------------------------------------------------------- the rate limiter


def test_limiter_allows_up_to_the_limit_then_refuses():
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.check("a") for _ in range(3)] == [None, None, None]
    assert limiter.check("a") is not None


def test_limiter_is_per_key():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert limiter.check("a") is None
    assert limiter.check("b") is None, "one caller must not exhaust another's budget"


def test_limiter_window_expires(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr("app.api.security.time.monotonic", lambda: clock["now"])

    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    assert limiter.check("a") is None
    assert limiter.check("a") is None
    assert limiter.check("a") is not None

    clock["now"] += 61
    assert limiter.check("a") is None, "attempts must age out of the window"


def test_limiter_reset_clears_history():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    limiter.check("a")
    assert limiter.check("a") is not None
    limiter.reset("a")
    assert limiter.check("a") is None


# ------------------------------------------------------------------ live routes


def test_repeated_failed_logins_are_throttled(client):
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/login", data={"username": "testuser", "password": "wrong-password"}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_successful_login_clears_the_failure_budget(client):
    for _ in range(4):
        client.post("/api/auth/login", data={"username": "testuser", "password": "nope"})

    ok = client.post(
        "/api/auth/login", data={"username": "testuser", "password": "testpassword"}
    )
    assert ok.status_code == 200

    # Without the reset, a shared address locks itself out through normal use.
    again = client.post("/api/auth/login", data={"username": "testuser", "password": "nope"})
    assert again.status_code == 401


def test_login_does_not_reveal_whether_an_account_exists(client):
    missing = client.post(
        "/api/auth/login", data={"username": "no-such-user", "password": "whatever1"}
    )
    wrong = client.post(
        "/api/auth/login", data={"username": "testuser", "password": "wrong-password"}
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["detail"] == wrong.json()["detail"]


@pytest.mark.parametrize(
    "password",
    ["short1", "password", "password123", "aaaaaaaaaa", "12345678"],
)
def test_weak_passwords_are_rejected(client, password):
    response = client.post(
        "/api/auth/register",
        json={"username": "newperson", "email": "new@example.com", "password": password},
    )
    assert response.status_code == 422


def test_a_reasonable_password_is_accepted(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "newperson",
            "email": "new@example.com",
            "password": "correct-horse-battery",
        },
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "username",
    ["has space", "semi;colon", "ab", "unicode‮override", "tab\there"],
)
def test_malformed_usernames_are_rejected(client, username):
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": "new@example.com", "password": "a-good-passphrase"},
    )
    assert response.status_code == 422


def test_security_headers_are_present(client):
    response = client.get("/api/system/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_admin_endpoints_reject_a_wrong_token(client):
    response = client.post("/api/system/cache/clear", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 403


def test_admin_endpoints_reject_a_missing_token(client):
    assert client.post("/api/system/cache/clear").status_code == 403


def test_expired_tokens_are_refused(client):
    from datetime import timedelta

    from app.api.auth_helper import create_access_token

    token = create_access_token(
        data={"sub": "testuser"}, expires_delta=timedelta(minutes=-5)
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_tokens_signed_with_another_key_are_refused(client):
    import jwt

    from app.api.auth_helper import ALGORITHM

    forged = jwt.encode(
        {"sub": "testuser", "exp": 9999999999}, "not-the-real-key", algorithm=ALGORITHM
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_unsigned_tokens_are_refused(client):
    """The ``alg: none`` forgery, pinned because the fix is one argument wide."""
    import jwt

    forged = jwt.encode({"sub": "testuser", "exp": 9999999999}, key="", algorithm="none")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
