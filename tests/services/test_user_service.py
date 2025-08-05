# tests/services/test_user_service.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.user_service import UserService
from app.schemas.user_schema import UserCreate, UserUpdate
from app.models.user_model import User, UserRole
from app.core.exceptions import (
    ResourceNotFound,
    NotAuthorized,
    ValidationError,
    ResourceAlreadyExists,
)
from tests.mocks.mock_user_repository import FakeUserRepository

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def user_service() -> UserService:
    """Fixture to create a UserService instance with a fresh fake repository for each test."""
    service = UserService()
    service.user_repository = FakeUserRepository()
    return service


@pytest.fixture
def sample_user() -> User:
    """A regular user for testing."""
    return User(
        id=1,
        email="user@example.com",
        username="regularuser",
        first_name="Regular",
        last_name="User",
        hashed_password="hashed_password",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_admin() -> User:
    """An admin user for testing."""
    return User(
        id=2,
        email="admin@example.com",
        username="adminuser",
        first_name="Admin",
        last_name="User",
        hashed_password="hashed_password",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_moderator() -> User:
    """A moderator user for testing."""
    return User(
        id=3,
        email="mod@example.com",
        username="moduser",
        first_name="Mod",
        last_name="User",
        hashed_password="hashed_password",
        role=UserRole.MODERATOR,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ==================== create_user TESTS ====================


async def test_create_user_success(user_service: UserService):
    """Test successful user creation."""
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        first_name="Test",
        last_name="User",
        password="aStrongPassword123!",
    )

    with patch("app.services.user_service.password_manager.hash_password") as mock_hash:
        mock_hash.return_value = "hashed_password_123"

        new_user = await user_service.create_user(db=None, user_in=user_data)

        assert new_user is not None
        assert new_user.email == user_data.email
        assert new_user.username == user_data.username
        assert new_user.hashed_password == "hashed_password_123"
        mock_hash.assert_called_once_with("aStrongPassword123!")


async def test_create_user_duplicate_email_fails(
    user_service: UserService, sample_user: User
):
    """Test that creating a user with duplicate email fails."""
    user_service.user_repository.users = [sample_user]

    user_data = UserCreate(
        email=sample_user.email,
        username="newusername",
        first_name="New",
        last_name="User",
        password="aStrongPassword123!",
    )

    with pytest.raises(ResourceAlreadyExists, match="already exists"):
        await user_service.create_user(db=None, user_in=user_data)


async def test_create_user_duplicate_username_fails(
    user_service: UserService, sample_user: User
):
    """Test that creating a user with duplicate username fails."""
    user_service.user_repository.users = [sample_user]

    user_data = UserCreate(
        email="newemail@example.com",
        username=sample_user.username,
        first_name="New",
        last_name="User",
        password="aStrongPassword123!",
    )

    with pytest.raises(ResourceAlreadyExists, match="already exists"):
        await user_service.create_user(db=None, user_in=user_data)


# ==================== get_user_for_auth TESTS ====================


async def test_get_user_for_auth_from_cache(
    user_service: UserService, sample_user: User
):
    """Test getting user for auth when user is in cache."""
    mock_db = MagicMock()
    mock_db.merge = AsyncMock(return_value=sample_user)

    with patch(
        "app.services.user_service.cache_service.get_user", return_value=sample_user
    ):
        result = await user_service.get_user_for_auth(mock_db, user_id=1)

        assert result == sample_user
        mock_db.merge.assert_called_once_with(sample_user)


async def test_get_user_for_auth_from_db(user_service: UserService, sample_user: User):
    """Test getting user for auth when user is not in cache."""
    user_service.user_repository.users = [sample_user]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user") as mock_cache:
            result = await user_service.get_user_for_auth(None, user_id=1)

            assert result == sample_user
            mock_cache.assert_called_once_with(sample_user)


async def test_get_user_for_auth_not_found(user_service: UserService):
    """Test getting user for auth when user doesn't exist."""
    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        result = await user_service.get_user_for_auth(None, user_id=999)
        assert result is None


# ==================== get_user_by_id TESTS ====================


async def test_get_user_by_id_invalid_id(user_service: UserService, sample_admin: User):
    """Test that invalid user ID raises ValidationError."""
    with pytest.raises(ValidationError, match="positive integer"):
        await user_service.get_user_by_id(None, user_id=0, current_user=sample_admin)

    with pytest.raises(ValidationError, match="positive integer"):
        await user_service.get_user_by_id(None, user_id=-1, current_user=sample_admin)


async def test_get_user_by_id_not_found(user_service: UserService, sample_admin: User):
    """Test that non-existent user raises ResourceNotFound."""
    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with pytest.raises(ResourceNotFound, match="not found"):
            await user_service.get_user_by_id(
                None, user_id=999, current_user=sample_admin
            )


async def test_get_user_by_id_self_access(user_service: UserService, sample_user: User):
    """Test that users can access their own profile."""
    user_service.user_repository.users = [sample_user]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            result = await user_service.get_user_by_id(
                None, user_id=sample_user.id, current_user=sample_user
            )
            assert result == sample_user


async def test_get_user_by_id_admin_access(
    user_service: UserService, sample_user: User, sample_admin: User
):
    """Test that admins can access any user profile."""
    user_service.user_repository.users = [sample_user, sample_admin]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            result = await user_service.get_user_by_id(
                None, user_id=sample_user.id, current_user=sample_admin
            )
            assert result == sample_user


async def test_get_user_by_id_moderator_access(
    user_service: UserService, sample_user: User, sample_moderator: User
):
    """Test that moderators can access user profiles."""
    user_service.user_repository.users = [sample_user, sample_moderator]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            result = await user_service.get_user_by_id(
                None, user_id=sample_user.id, current_user=sample_moderator
            )
            assert result == sample_user


# ==================== get_users TESTS ====================


async def test_get_users_unauthorized(user_service: UserService, sample_user: User):
    """Test that regular users cannot list all users."""
    with pytest.raises(NotAuthorized, match="Only moderators"):
        await user_service.get_users(None, current_user=sample_user)


async def test_get_users_invalid_pagination(
    user_service: UserService, sample_admin: User
):
    """Test that invalid pagination parameters raise ValidationError."""
    with pytest.raises(ValidationError, match="non-negative"):
        await user_service.get_users(None, current_user=sample_admin, skip=-1)

    with pytest.raises(ValidationError, match="between 1 and 100"):
        await user_service.get_users(None, current_user=sample_admin, limit=0)

    with pytest.raises(ValidationError, match="between 1 and 100"):
        await user_service.get_users(None, current_user=sample_admin, limit=101)


async def test_get_users_moderator_success(
    user_service: UserService, sample_moderator: User, sample_user: User
):
    """Test that moderators can list users."""
    user_service.user_repository.users = [sample_user, sample_moderator]

    result = await user_service.get_users(
        None, current_user=sample_moderator, skip=0, limit=10
    )

    assert result.total == 2
    assert len(result.items) == 2


# ==================== get_users TESTS (continued) ====================


async def test_get_users_admin_success(
    user_service: UserService, sample_admin: User, sample_user: User
):
    """Test that admins can list users with pagination."""
    users = [sample_user, sample_admin]
    for i in range(3, 8):
        users.append(
            User(
                id=i,
                email=f"user{i}@example.com",
                username=f"user{i}",
                first_name=f"User{i}",
                last_name="Test",
                role=UserRole.USER,
                hashed_password="hashed",
                is_active=True,
                # --- THE FIX IS HERE ---
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
    user_service.user_repository.users = users

    # Test first page
    result = await user_service.get_users(
        None, current_user=sample_admin, skip=0, limit=3
    )
    assert result.total == 7
    assert len(result.items) == 3
    assert result.page == 1
    assert result.pages == 3

    # Test second page
    result = await user_service.get_users(
        None, current_user=sample_admin, skip=3, limit=3
    )
    assert result.total == 7
    assert len(result.items) == 3
    assert result.page == 2


async def test_get_users_with_filters(user_service: UserService, sample_admin: User):
    """Test listing users with filters."""
    users = [
        sample_admin,
        User(
            id=10,
            email="active@example.com",
            username="active",
            first_name="Active",
            last_name="User",
            role=UserRole.USER,
            is_active=True,
            hashed_password="hash",
            # --- THE FIX IS HERE ---
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        User(
            id=11,
            email="inactive@example.com",
            username="inactive",
            first_name="Inactive",
            last_name="User",
            role=UserRole.USER,
            is_active=False,
            hashed_password="hash",
            # --- THE FIX IS HERE ---
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    ]
    user_service.user_repository.users = users

    # Filter by active status
    result = await user_service.get_users(
        None, current_user=sample_admin, filters={"is_active": True}
    )
    assert result.total == 2
    assert all(user.is_active for user in result.items)


# ==================== update_user TESTS ====================


async def test_update_user_invalid_id(user_service: UserService, sample_admin: User):
    """Test that invalid user ID raises ValidationError."""
    update_data = UserUpdate(first_name="Updated")

    with pytest.raises(ValidationError, match="positive integer"):
        await user_service.update_user(
            None, user_id_to_update=0, user_data=update_data, current_user=sample_admin
        )


async def test_update_user_self_success(user_service: UserService, sample_user: User):
    """Test that users can update their own profile."""
    user_service.user_repository.users = [sample_user]
    update_data = UserUpdate(first_name="Updated", last_name="Name")

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch(
                "app.services.user_service.cache_service.invalidate_user"
            ) as mock_invalidate:
                result = await user_service.update_user(
                    None,
                    user_id_to_update=sample_user.id,
                    user_data=update_data,
                    current_user=sample_user,
                )

                assert result.first_name == "Updated"
                assert result.last_name == "Name"
                mock_invalidate.assert_called_once_with(sample_user.id)


async def test_update_user_admin_can_update_others(
    user_service: UserService, sample_user: User, sample_admin: User
):
    """Test that admins can update other users."""
    user_service.user_repository.users = [sample_user, sample_admin]
    update_data = UserUpdate(is_verified=True)

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch("app.services.user_service.cache_service.invalidate_user"):
                result = await user_service.update_user(
                    None,
                    user_id_to_update=sample_user.id,
                    user_data=update_data,
                    current_user=sample_admin,
                )

                assert result.is_verified is True


async def test_update_user_regular_cannot_update_others(
    user_service: UserService, sample_user: User
):
    """Test that regular users cannot update other users."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="other",
        role=UserRole.USER,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, other_user]
    update_data = UserUpdate(first_name="Hacked")

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(NotAuthorized):
                await user_service.update_user(
                    None,
                    user_id_to_update=other_user.id,
                    user_data=update_data,
                    current_user=sample_user,
                )


async def test_update_user_duplicate_email(
    user_service: UserService, sample_user: User
):
    """Test that updating to a duplicate email fails."""
    other_user = User(
        id=99,
        email="taken@example.com",
        username="other",
        role=UserRole.USER,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, other_user]
    update_data = UserUpdate(email="taken@example.com")

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(
                ResourceAlreadyExists, match="Email address is already in use"
            ):
                await user_service.update_user(
                    None,
                    user_id_to_update=sample_user.id,
                    user_data=update_data,
                    current_user=sample_user,
                )


async def test_update_user_duplicate_username(
    user_service: UserService, sample_user: User
):
    """Test that updating to a duplicate username fails."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="takenusername",
        role=UserRole.USER,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, other_user]
    update_data = UserUpdate(username="takenusername")

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(
                ResourceAlreadyExists, match="Username is already in use"
            ):
                await user_service.update_user(
                    None,
                    user_id_to_update=sample_user.id,
                    user_data=update_data,
                    current_user=sample_user,
                )


async def test_update_user_excludes_timestamps(
    user_service: UserService, sample_user: User
):
    """Test that timestamp fields are excluded from updates."""
    user_service.user_repository.users = [sample_user]
    update_data = UserUpdate(
        first_name="Updated",
        created_at=datetime.now(timezone.utc),  # Should be ignored
        updated_at=datetime.now(timezone.utc),  # Should be ignored
    )

    original_created_at = sample_user.created_at

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch("app.services.user_service.cache_service.invalidate_user"):
                result = await user_service.update_user(
                    None,
                    user_id_to_update=sample_user.id,
                    user_data=update_data,
                    current_user=sample_user,
                )

                assert result.first_name == "Updated"
                assert result.created_at == original_created_at  # Should not change


# ==================== deactivate_user TESTS ====================


async def test_deactivate_user_invalid_id(
    user_service: UserService, sample_admin: User
):
    """Test that invalid user ID raises ValidationError."""
    with pytest.raises(ValidationError, match="positive integer"):
        await user_service.deactivate_user(
            None, user_id_to_deactivate=0, current_user=sample_admin
        )


async def test_deactivate_user_self_success(
    user_service: UserService, sample_user: User
):
    """Test that users can deactivate their own account."""
    user_service.user_repository.users = [sample_user]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch(
                "app.services.user_service.cache_service.invalidate_user"
            ) as mock_invalidate:
                result = await user_service.deactivate_user(
                    None, user_id_to_deactivate=sample_user.id, current_user=sample_user
                )

                assert result.is_active is False
                assert result.is_verified is False
                mock_invalidate.assert_called_once_with(sample_user.id)


async def test_deactivate_user_already_inactive(
    user_service: UserService, sample_admin: User
):
    """Test that deactivating an already inactive user fails."""
    inactive_user = User(
        id=99,
        email="inactive@example.com",
        username="inactive",
        role=UserRole.USER,
        is_active=False,
        hashed_password="hash",
    )
    user_service.user_repository.users = [inactive_user, sample_admin]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(ValidationError, match="already deactivated"):
                await user_service.deactivate_user(
                    None,
                    user_id_to_deactivate=inactive_user.id,
                    current_user=sample_admin,
                )


async def test_deactivate_user_admin_cannot_self_deactivate(
    user_service: UserService, sample_admin: User
):
    """Test that admins cannot deactivate their own account."""
    user_service.user_repository.users = [sample_admin]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(ValidationError, match="cannot deactivate their own"):
                await user_service.deactivate_user(
                    None,
                    user_id_to_deactivate=sample_admin.id,
                    current_user=sample_admin,
                )


async def test_deactivate_user_unauthorized(
    user_service: UserService, sample_user: User
):
    """Test that users cannot deactivate other users."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="other",
        role=UserRole.USER,
        is_active=True,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, other_user]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(NotAuthorized):
                await user_service.deactivate_user(
                    None, user_id_to_deactivate=other_user.id, current_user=sample_user
                )


# ==================== activate_user TESTS ====================


async def test_activate_user_success(user_service: UserService, sample_admin: User):
    """Test that admins can activate users."""
    inactive_user = User(
        id=99,
        email="inactive@example.com",
        username="inactive",
        role=UserRole.USER,
        is_active=False,
        hashed_password="hash",
    )
    user_service.user_repository.users = [inactive_user, sample_admin]

    with patch(
        "app.services.user_service.cache_service.invalidate_user"
    ) as mock_invalidate:
        result = await user_service.activate_user(
            None, user_id_to_activate=inactive_user.id, current_user=sample_admin
        )

        assert result.is_active is True
        mock_invalidate.assert_called_once_with(inactive_user.id)


async def test_activate_user_not_found(user_service: UserService, sample_admin: User):
    """Test that activating non-existent user raises ResourceNotFound."""
    with pytest.raises(ResourceNotFound, match="not found"):
        await user_service.activate_user(
            None, user_id_to_activate=999, current_user=sample_admin
        )


async def test_activate_user_already_active(
    user_service: UserService, sample_admin: User, sample_user: User
):
    """Test that activating an already active user fails."""
    user_service.user_repository.users = [sample_user, sample_admin]

    with pytest.raises(ValidationError, match="already active"):
        await user_service.activate_user(
            None, user_id_to_activate=sample_user.id, current_user=sample_admin
        )


# ==================== change_role TESTS ====================


async def test_change_role_success(
    user_service: UserService, sample_admin: User, sample_user: User
):
    """Test that admins can change user roles."""
    user_service.user_repository.users = [sample_user, sample_admin]

    with patch(
        "app.services.user_service.cache_service.invalidate_user"
    ) as mock_invalidate:
        result = await user_service.change_role(
            None,
            user_id_to_change=sample_user.id,
            new_role=UserRole.MODERATOR,
            current_user=sample_admin,
        )

        assert result.role == UserRole.MODERATOR
        mock_invalidate.assert_called_once_with(sample_user.id)


async def test_change_role_admin_cannot_change_own(
    user_service: UserService, sample_admin: User
):
    """Test that admins cannot change their own role."""
    with pytest.raises(ValidationError, match="cannot change their own role"):
        await user_service.change_role(
            None,
            user_id_to_change=sample_admin.id,
            new_role=UserRole.USER,
            current_user=sample_admin,
        )


# ==================== change_role TESTS (continued) ====================


async def test_change_role_user_not_found(
    user_service: UserService, sample_admin: User
):
    """Test that changing role of non-existent user raises ResourceNotFound."""
    with pytest.raises(ResourceNotFound, match="not found"):
        await user_service.change_role(
            None,
            user_id_to_change=999,
            new_role=UserRole.MODERATOR,
            current_user=sample_admin,
        )


# ==================== delete_user TESTS ====================


async def test_delete_user_invalid_id(user_service: UserService, sample_admin: User):
    """Test that invalid user ID raises ValidationError."""
    with pytest.raises(ValidationError, match="positive integer"):
        await user_service.delete_user(
            None, user_id_to_delete=0, current_user=sample_admin
        )


async def test_delete_user_success(
    user_service: UserService, sample_admin: User, sample_user: User
):
    """Test that admins can delete users."""
    # Add another admin to avoid "last admin" validation
    another_admin = User(
        id=100,
        email="admin2@example.com",
        username="admin2",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, sample_admin, another_admin]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch(
                "app.services.user_service.cache_service.invalidate_user"
            ) as mock_invalidate:
                result = await user_service.delete_user(
                    None, user_id_to_delete=sample_user.id, current_user=sample_admin
                )

                assert result["message"] == "User deleted successfully"
                assert len(user_service.user_repository.users) == 2
                assert sample_user not in user_service.user_repository.users
                mock_invalidate.assert_called_once_with(sample_user.id)


async def test_delete_user_cannot_self_delete(
    user_service: UserService, sample_user: User
):
    """Test that users cannot delete their own account."""
    user_service.user_repository.users = [sample_user]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(ValidationError, match="cannot delete their own"):
                await user_service.delete_user(
                    None, user_id_to_delete=sample_user.id, current_user=sample_user
                )


async def test_delete_user_cannot_delete_last_admin(
    user_service: UserService, sample_admin: User
):
    """Test that the last admin cannot be deleted."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="other",
        role=UserRole.USER,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_admin, other_user]

    # Create another admin to try to delete the first one
    deleting_admin = User(
        id=100,
        email="admin2@example.com",
        username="admin2",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(
                ValidationError, match="Cannot delete the last active administrator"
            ):
                await user_service.delete_user(
                    None, user_id_to_delete=sample_admin.id, current_user=deleting_admin
                )


async def test_delete_user_unauthorized(user_service: UserService, sample_user: User):
    """Test that regular users cannot delete other users."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="other",
        role=UserRole.USER,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, other_user]

    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with pytest.raises(NotAuthorized):
                await user_service.delete_user(
                    None, user_id_to_delete=other_user.id, current_user=sample_user
                )


# ==================== _check_authorization TESTS ====================


async def test_check_authorization_admin_can_do_anything(
    user_service: UserService, sample_admin: User, sample_user: User
):
    """Test that admins pass all authorization checks."""
    # Should not raise any exception
    user_service._check_authorization(
        current_user=sample_admin, target_user=sample_user, action="any action"
    )


async def test_check_authorization_user_can_act_on_self(
    user_service: UserService, sample_user: User
):
    """Test that users can perform actions on themselves."""
    # Should not raise any exception
    user_service._check_authorization(
        current_user=sample_user, target_user=sample_user, action="update"
    )


async def test_check_authorization_user_cannot_act_on_others(
    user_service: UserService, sample_user: User
):
    """Test that users cannot perform actions on other users."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="other",
        role=UserRole.USER,
        hashed_password="hash",
    )

    with pytest.raises(NotAuthorized, match="not authorized to"):
        user_service._check_authorization(
            current_user=sample_user, target_user=other_user, action="update"
        )


# ==================== _validate_user_update TESTS ====================


async def test_validate_user_update_no_conflicts(
    user_service: UserService, sample_user: User
):
    """Test validation passes when there are no conflicts."""
    user_service.user_repository.users = [sample_user]
    update_data = UserUpdate(first_name="NewName")

    # Should not raise any exception
    await user_service._validate_user_update(None, update_data, sample_user)


async def test_validate_user_update_email_conflict(
    user_service: UserService, sample_user: User
):
    """Test validation fails when email is already taken."""
    other_user = User(
        id=99, email="taken@example.com", username="other", hashed_password="hash"
    )
    user_service.user_repository.users = [sample_user, other_user]
    update_data = UserUpdate(email="taken@example.com")

    with pytest.raises(ResourceAlreadyExists, match="Email address is already in use"):
        await user_service._validate_user_update(None, update_data, sample_user)


async def test_validate_user_update_username_conflict(
    user_service: UserService, sample_user: User
):
    """Test validation fails when username is already taken."""
    other_user = User(
        id=99,
        email="other@example.com",
        username="takenusername",
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, other_user]
    update_data = UserUpdate(username="takenusername")

    with pytest.raises(ResourceAlreadyExists, match="Username is already in use"):
        await user_service._validate_user_update(None, update_data, sample_user)


async def test_validate_user_update_same_email_ok(
    user_service: UserService, sample_user: User
):
    """Test that updating to the same email doesn't cause conflict."""
    user_service.user_repository.users = [sample_user]
    update_data = UserUpdate(email=sample_user.email)

    # Should not raise any exception
    await user_service._validate_user_update(None, update_data, sample_user)


# ==================== _validate_user_deletion TESTS ====================


async def test_validate_user_deletion_success(
    user_service: UserService, sample_admin: User, sample_user: User
):
    """Test successful deletion validation."""
    # Add another admin to avoid "last admin" issue
    another_admin = User(
        id=100,
        email="admin2@example.com",
        username="admin2",
        role=UserRole.ADMIN,
        is_active=True,
        hashed_password="hash",
    )
    user_service.user_repository.users = [sample_user, sample_admin, another_admin]

    # Should not raise any exception
    await user_service._validate_user_deletion(None, sample_user, sample_admin)


async def test_validate_user_deletion_self_delete(
    user_service: UserService, sample_user: User
):
    """Test that self-deletion is prevented."""
    with pytest.raises(ValidationError, match="cannot delete their own"):
        await user_service._validate_user_deletion(None, sample_user, sample_user)


async def test_validate_user_deletion_last_admin(
    user_service: UserService, sample_admin: User
):
    """Test that deleting the last admin is prevented."""
    user_service.user_repository.users = [sample_admin]

    # Create another admin to perform the deletion
    deleting_admin = User(
        id=100,
        email="admin2@example.com",
        username="admin2",
        role=UserRole.ADMIN,
        hashed_password="hash",
    )

    with pytest.raises(
        ValidationError, match="Cannot delete the last active administrator"
    ):
        await user_service._validate_user_deletion(None, sample_admin, deleting_admin)


# ==================== Integration-style tests ====================


async def test_user_lifecycle(user_service: UserService, sample_admin: User):
    """Test complete user lifecycle: create, update, deactivate, activate, delete."""
    # Setup: Add admin to repository
    user_service.user_repository.users = [sample_admin]

    # 1. Create user
    user_data = UserCreate(
        email="lifecycle@example.com",
        username="lifecycleuser",
        first_name="Life",
        last_name="Cycle",
        password="TestPassword123!",
    )

    with patch(
        "app.services.user_service.password_manager.hash_password",
        return_value="hashed",
    ):
        new_user = await user_service.create_user(None, user_in=user_data)

    assert new_user.email == "lifecycle@example.com"
    assert new_user.is_active is True

    # 2. Update user
    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch("app.services.user_service.cache_service.invalidate_user"):
                update_data = UserUpdate(first_name="Updated")
                updated_user = await user_service.update_user(
                    None,
                    user_id_to_update=new_user.id,
                    user_data=update_data,
                    current_user=sample_admin,
                )
                assert updated_user.first_name == "Updated"

    # 3. Deactivate user
    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch("app.services.user_service.cache_service.invalidate_user"):
                deactivated_user = await user_service.deactivate_user(
                    None, user_id_to_deactivate=new_user.id, current_user=sample_admin
                )
                assert deactivated_user.is_active is False

    # 4. Activate user
    with patch("app.services.user_service.cache_service.invalidate_user"):
        activated_user = await user_service.activate_user(
            None, user_id_to_activate=new_user.id, current_user=sample_admin
        )
        assert activated_user.is_active is True

    # 5. Delete user
    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch("app.services.user_service.cache_service.invalidate_user"):
                result = await user_service.delete_user(
                    None, user_id_to_delete=new_user.id, current_user=sample_admin
                )
                assert result["message"] == "User deleted successfully"
                assert (
                    len(user_service.user_repository.users) == 1
                )  # Only admin remains


async def test_concurrent_operations_scenario(
    user_service: UserService, sample_admin: User
):
    """Test handling of concurrent-like operations."""
    user_service.user_repository.users = [sample_admin]

    # Create two users with similar data
    user1_data = UserCreate(
        email="user1@example.com",
        username="user1",
        first_name="User",
        last_name="One",
        password="Password123!",
    )

    user2_data = UserCreate(
        email="user2@example.com",
        username="user2",
        first_name="User",
        last_name="Two",
        password="Password123!",
    )

    with patch(
        "app.services.user_service.password_manager.hash_password",
        return_value="hashed",
    ):
        user1 = await user_service.create_user(None, user_in=user1_data)
        user2 = await user_service.create_user(None, user_in=user2_data)

    # Try to update both users to have the same email (should fail for the second)
    with patch("app.services.user_service.cache_service.get_user", return_value=None):
        with patch("app.services.user_service.cache_service.cache_user"):
            with patch("app.services.user_service.cache_service.invalidate_user"):
                # First update succeeds
                update1 = UserUpdate(email="newemail@example.com")
                await user_service.update_user(
                    None,
                    user_id_to_update=user1.id,
                    user_data=update1,
                    current_user=sample_admin,
                )

                # Second update should fail
                update2 = UserUpdate(email="newemail@example.com")
                with pytest.raises(ResourceAlreadyExists):
                    await user_service.update_user(
                        None,
                        user_id_to_update=user2.id,
                        user_data=update2,
                        current_user=sample_admin,
                    )
