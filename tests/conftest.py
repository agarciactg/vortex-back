import asyncio
import uuid
import pytest
import pytest_asyncio

from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.user import User
from app.models.ticket import Ticket, TicketStatus, TicketPriority


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def create_tables():
    """Create tables once per session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """
    DB session per test. Rollback at the end to isolate each test.
    """
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mock Redis — no token is blacklisted by default."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)

    async def _get_redis():
        return redis_mock

    monkeypatch.setattr("app.core.redis.get_redis", _get_redis)
    monkeypatch.setattr("app.dependencies.auth.get_redis", _get_redis)
    monkeypatch.setattr("app.services.auth_service.get_redis", _get_redis)
    return redis_mock


@pytest_asyncio.fixture
async def user_a(db: AsyncSession) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email="ana@test.com",
        name="Ana García",
        google_id=f"google_{uuid.uuid4().hex}",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def user_b(db: AsyncSession) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email="luis@test.com",
        name="Luis Martínez",
        google_id=f"google_{uuid.uuid4().hex}",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def client_a(db: AsyncSession, user_a: User) -> AsyncClient:
    """Client authenticated as user_a."""

    async def _override_db():
        yield db

    async def _override_auth():
        return user_a

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_auth

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_b(db: AsyncSession, user_b: User) -> AsyncClient:
    """Authenticated customer as user_b."""

    async def _override_db():
        yield db

    async def _override_auth():
        return user_b

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_auth

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_unauth() -> AsyncClient:
    """Unauthenticated client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def ticket_by_a(db: AsyncSession, user_a: User) -> Ticket:
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Fix login bug in production",
        description="Users can't log in after the latest deploy",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
        author_id=user_a.id,
    )
    db.add(ticket)
    await db.flush()
    return ticket
