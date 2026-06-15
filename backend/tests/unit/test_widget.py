"""
Feature:  Embeddable Storefront Widget
Layer:    Tests / Unit
Module:   tests.unit.test_widget
Purpose:  Unit tests for widget token issuance, widget.js delivery, settings
          update, and origin-check enforcement. Vault and DB mocked — no network.
Depends:  app.api.widget
HITL:     None.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
from app.api.deps import get_current_user, get_session
from app.api.widget import _ALGORITHM, _WIDGET_TOKEN_TTL, router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Test helpers ────────────────────────────────────────────────────────────────

_PRIVATE_KEY: str
_PUBLIC_KEY: str


def _generate_test_keys() -> tuple[str, str]:
    """Generate a fresh RSA key pair for unit tests."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv_pem, pub_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_test_keys()


def _make_widget_token(
    tenant_id: str = "tenant_001",
    scope: str = "widget",
    expired: bool = False,
) -> str:
    now = datetime.now(UTC)
    exp = now - timedelta(seconds=1) if expired else now + _WIDGET_TOKEN_TTL
    payload = {
        "tenant_id": tenant_id,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _PRIVATE_KEY, algorithm=_ALGORITHM)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


# ── widget.js delivery ─────────────────────────────────────────────────────────


class TestWidgetJs:
    def test_returns_javascript(self) -> None:
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/widget/widget.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_contains_mawrid_identifier(self) -> None:
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/widget/widget.js")
        assert "mawrid" in resp.text.lower()

    def test_cache_control_header(self) -> None:
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/widget/widget.js")
        assert "cache-control" in resp.headers
        assert "max-age" in resp.headers["cache-control"]


# ── GET /widget/token ──────────────────────────────────────────────────────────


class TestGetWidgetToken:
    def _mock_secrets(self) -> MagicMock:
        secrets = MagicMock()
        secrets.jwt_private_key = _PRIVATE_KEY
        return secrets

    def test_returns_signed_jwt(self) -> None:
        app = _make_app()
        mock_user = MagicMock()
        mock_user.tenant_id = "tenant_001"
        app.dependency_overrides[get_current_user] = lambda: mock_user

        with (
            patch("app.api.widget.get_secrets", return_value=self._mock_secrets()),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            resp = client.get("/api/v1/widget/token")

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["expires_in"] == 900  # 15 min

    def test_token_has_widget_scope(self) -> None:
        app = _make_app()
        mock_user = MagicMock()
        mock_user.tenant_id = "tenant_abc"
        app.dependency_overrides[get_current_user] = lambda: mock_user

        with (
            patch("app.api.widget.get_secrets", return_value=self._mock_secrets()),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            resp = client.get("/api/v1/widget/token")

        token = resp.json()["token"]
        decoded = jwt.decode(token, _PUBLIC_KEY, algorithms=[_ALGORITHM])
        assert decoded["scope"] == "widget"
        assert decoded["tenant_id"] == "tenant_abc"


# ── PATCH /widget/settings ─────────────────────────────────────────────────────


class TestUpdateWidgetSettings:
    def test_update_allowed_origins(self) -> None:
        app = _make_app()
        mock_user = MagicMock()
        mock_user.tenant_id = "tenant_001"
        mock_repo = MagicMock()
        mock_repo.update_allowed_origins = AsyncMock()
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.widget.TenantRepo", return_value=mock_repo):
            app.dependency_overrides[get_current_user] = lambda: mock_user
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.patch(
                    "/api/v1/widget/settings",
                    json={"allowed_origins": "https://shop.example.com,https://www.example.com"},
                )

        assert resp.status_code == 204
        mock_repo.update_allowed_origins.assert_awaited_once()


# ── POST /widget/chat origin check ─────────────────────────────────────────────


class TestWidgetChat:
    def _mock_secrets(self) -> MagicMock:
        secrets = MagicMock()
        secrets.jwt_private_key = _PRIVATE_KEY
        secrets.jwt_public_key = _PUBLIC_KEY
        return secrets

    def _mock_tenant(self, allowed_origins: str | None = "https://shop.example.com") -> MagicMock:
        t = MagicMock()
        t.allowed_origins = allowed_origins
        return t

    def test_missing_auth_returns_401(self) -> None:
        app = _make_app()
        with patch("app.api.widget.get_secrets", return_value=self._mock_secrets()):
            app.dependency_overrides[get_session] = lambda: MagicMock()
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/api/v1/widget/chat", json={"query": "test"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self) -> None:
        token = _make_widget_token(expired=True)
        app = _make_app()
        mock_session = MagicMock()
        with patch("app.api.widget.get_secrets", return_value=self._mock_secrets()):
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/widget/chat",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 401

    def test_wrong_scope_returns_403(self) -> None:
        token = _make_widget_token(scope="access")
        app = _make_app()
        mock_session = MagicMock()
        with patch("app.api.widget.get_secrets", return_value=self._mock_secrets()):
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/widget/chat",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 403

    def test_allowed_origin_passes(self) -> None:
        token = _make_widget_token()
        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=self._mock_tenant("https://shop.example.com"))
        app = _make_app()

        with (
            patch("app.api.widget.get_secrets", return_value=self._mock_secrets()),
            patch("app.api.widget.TenantRepo", return_value=mock_repo),
            patch(
                "app.api.widget.run_rag",
                new=AsyncMock(return_value=MagicMock(answer="Great product!")),
            ),
        ):
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/widget/chat",
                    json={"query": "Tell me about Widget A"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Origin": "https://shop.example.com",
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Great product!"

    def test_disallowed_origin_returns_403(self) -> None:
        token = _make_widget_token()
        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=self._mock_tenant("https://shop.example.com"))
        app = _make_app()

        with (
            patch("app.api.widget.get_secrets", return_value=self._mock_secrets()),
            patch("app.api.widget.TenantRepo", return_value=mock_repo),
        ):
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/widget/chat",
                    json={"query": "test"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Origin": "https://evil.attacker.com",
                    },
                )
        assert resp.status_code == 403

    def test_no_allowed_origins_configured_returns_403(self) -> None:
        token = _make_widget_token()
        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=self._mock_tenant(None))
        app = _make_app()

        with (
            patch("app.api.widget.get_secrets", return_value=self._mock_secrets()),
            patch("app.api.widget.TenantRepo", return_value=mock_repo),
        ):
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/widget/chat",
                    json={"query": "test"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Origin": "https://shop.example.com",
                    },
                )
        assert resp.status_code == 403

    def test_no_origin_header_skips_check(self) -> None:
        """Requests without an Origin header (e.g. server-to-server) skip the origin check."""
        token = _make_widget_token()
        mock_session = MagicMock()
        app = _make_app()

        with (
            patch("app.api.widget.get_secrets", return_value=self._mock_secrets()),
            patch("app.api.widget.run_rag", new=AsyncMock(return_value=MagicMock(answer="OK"))),
        ):
            app.dependency_overrides[get_session] = lambda: mock_session
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/widget/chat",
                    json={"query": "test"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 200
