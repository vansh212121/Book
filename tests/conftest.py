import asyncio
from typing import AsyncGenerator, Generator, Dict, Any
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.security import PasswordManager
from app.db.session import get_session
from app.main import app
from app.models.user_model import User, UserRole
from app.schemas.user_schema import UserCreate

# --- Test Database Setup ---
TEST_DATABASE_URL = (
    str(settings.DATABASE_URL_TEST)
    if hasattr(settings, "DATABASE_URL_TEST")
    else "sqlite+aiosqlite:///:memory:"
)

if TEST_DATABASE_URL.startswith("sqlite"):
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
else:
    test_engine = create_async_engine(TEST_DATABASE_URL)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Pytest Fixtures ---


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Session-scoped fixture to create and drop database tables.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean, isolated database transaction for each test function.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = TestSessionLocal(bind=connection)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture(scope="function")
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an HTTP client for API testing, overriding the DB dependency.
    """

    def override_get_session() -> Generator[AsyncSession, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


# --- Test Data Fixtures ---


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Provides a dictionary of sample user data for creation."""
    unique_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test.user.{unique_id}@example.com",
        "username": f"testuser{unique_id}",
        "first_name": "Test",
        "last_name": "User",
        "password": "TestPassword123!",
    }


@pytest.fixture
def sample_admin_data() -> Dict[str, Any]:
    """Provides a dictionary of sample admin data for creation."""
    unique_id = str(uuid.uuid4())[:8]
    return {
        "email": f"admin.{unique_id}@example.com",
        "username": f"admin{unique_id}",
        "first_name": "Admin",
        "last_name": "User",
        "password": "AdminPassword123!",
        "role": UserRole.ADMIN,
    }


@pytest_asyncio.fixture
async def sample_user(
    db_session: AsyncSession, sample_user_data: Dict[str, Any]
) -> User:
    """Creates and returns a sample user in the database."""
    user_data = sample_user_data.copy()
    password = user_data.pop("password")

    user_data["hashed_password"] = PasswordManager.hash_password(password)
    user_data["is_verified"] = True

    user = User(**user_data)

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_admin(
    db_session: AsyncSession, sample_admin_data: Dict[str, Any]
) -> User:
    """Creates and returns a sample admin user in the database."""
    admin_data = sample_admin_data.copy()
    password = admin_data.pop("password")

    admin_data["hashed_password"] = PasswordManager.hash_password(password)
    admin_data["is_verified"] = True

    admin = User(**admin_data)

    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def multiple_users(db_session: AsyncSession) -> list[User]:
    """Creates multiple users for pagination/filtering tests."""
    users_to_create = []
    for i in range(5):
        unique_id = str(uuid.uuid4())[:8]
        user = User(
            email=f"user{i}.{unique_id}@example.com",
            username=f"user{i}_{unique_id}",
            first_name=f"Test",
            last_name=f"User {i}",
            hashed_password=PasswordManager.hash_password("TestPassword123!"),
            is_active=i % 2 == 0,
            is_verified=True,
            role=UserRole.MODERATOR if i == 0 else UserRole.USER,
        )
        db_session.add(user)
        users_to_create.append(user)

    await db_session.commit()

    for user in users_to_create:
        await db_session.refresh(user)

    return users_to_create
