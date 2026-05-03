import pytest

from httpx import AsyncClient

from app.models.user import User

pytestmark = pytest.mark.asyncio


class TestGetMe:
    async def test_returns_authenticated_user(self, client_a: AsyncClient, user_a: User):
        response = await client_a.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_a.id
        assert data["email"] == user_a.email
        assert data["name"] == user_a.name

    async def test_returns_401_without_token(self, client_unauth: AsyncClient):
        response = await client_unauth.get("/api/v1/auth/me")

        assert response.status_code == 403


class TestLogout:
    async def test_logout_returns_204(self, client_a: AsyncClient, mock_redis):
        response = await client_a.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer fake-token-for-test"},
        )
        assert response.status_code == 204

    async def test_logout_calls_redis_blacklist(self, client_a: AsyncClient, mock_redis):
        await client_a.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer fake-token-for-test"},
        )
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert "blacklist:" in call_args[0]
