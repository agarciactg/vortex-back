import pytest
from httpx import AsyncClient
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/users"


class TestListUsers:
    async def test_returns_all_users(
        self, client_a: AsyncClient, user_a: User, user_b: User
    ):
        response = await client_a.get(BASE)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        ids = [u["id"] for u in data["items"]]
        assert user_a.id in ids
        assert user_b.id in ids

    async def test_search_by_name(
        self, client_a: AsyncClient, user_a: User
    ):
        response = await client_a.get(BASE, params={"search": "Ana"})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == user_a.id

    async def test_search_by_email(
        self, client_a: AsyncClient, user_b: User
    ):
        response = await client_a.get(BASE, params={"search": "luis@"})

        assert response.status_code == 200
        assert response.json()["total"] == 1

    async def test_search_no_match(self, client_a: AsyncClient):
        response = await client_a.get(BASE, params={"search": "zzznomatch"})

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_pagination_limit(
        self, client_a: AsyncClient, user_b: User
    ):
        response = await client_a.get(BASE, params={"limit": 1})

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2

    async def test_requires_auth(self, client_unauth: AsyncClient):
        response = await client_unauth.get(BASE)
        assert response.status_code == 403


class TestGetMe:
    async def test_returns_current_user_profile(
        self, client_a: AsyncClient, user_a: User
    ):
        response = await client_a.get(f"{BASE}/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_a.id
        assert data["email"] == user_a.email


class TestGetUserById:
    async def test_returns_user_by_id(
        self, client_a: AsyncClient, user_b: User
    ):
        response = await client_a.get(f"{BASE}/{user_b.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_b.id
        assert data["name"] == user_b.name

    async def test_returns_404_for_unknown_id(self, client_a: AsyncClient):
        response = await client_a.get(f"{BASE}/nonexistent-id")

        assert response.status_code == 404

    async def test_requires_auth(self, client_unauth: AsyncClient, user_b: User):
        response = await client_unauth.get(f"{BASE}/{user_b.id}")
        assert response.status_code == 403
