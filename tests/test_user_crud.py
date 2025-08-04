import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch, AsyncMock
from typing import List

from app.crud.user_crud import user_repository
from app.schemas.user_schema import UserCreate, UserUpdate
from app.models.user_model import User, UserRole
from app.core.exceptions import InternalServerError
from app.core.security import password_manager
from datetime import datetime, timezone

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


def prepare_user_model_from_schema(schema: UserCreate) -> User:
    """Converts a UserCreate schema to a valid User model for repository tests."""
    user_dict = schema.model_dump()
    password = user_dict.pop("password")
    user_dict["hashed_password"] = password_manager.hash_password(password)
    # Ensure all required model fields are present
    if "role" not in user_dict:
        user_dict["role"] = UserRole.USER
    user_dict["created_at"] = datetime.now(timezone.utc)
    user_dict["updated_at"] = datetime.now(timezone.utc)
    return User(**user_dict)


# ==================== CREATE TESTS ====================


async def test_create_user_success(db_session: AsyncSession, sample_user_data: dict):
    """
    Test case: Successfully create a new user.
    - GIVEN a valid User model object.
    - WHEN the create method is called.
    - THEN the user is saved to the database.
    """
    user_data = sample_user_data.copy()
    password = user_data.pop("password")

    # The service layer is responsible for hashing the password and building the model.
    # We simulate that here for the test.
    user_data["hashed_password"] = password_manager.hash_password(password)

    user_data["role"] = UserRole.USER

    user_to_create = User(**user_data)

    # Pass the User model object, not the schema
    new_user = await user_repository.create(db=db_session, db_obj=user_to_create)

    assert new_user is not None
    assert new_user.id is not None
    assert new_user.email == sample_user_data["email"]


async def test_create_user_duplicate_email_fails(
    db_session: AsyncSession, sample_user: User
):
    """Tests that creating a user with a duplicate email raises an error."""
    user_to_create = User(
        email=sample_user.email,
        username="new_unique_username",
        first_name="New",
        last_name="User",
        hashed_password="Hashed_pass_21",
        role=UserRole.USER,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # FIX: Expect InternalServerError because the decorator catches the IntegrityError
    with pytest.raises(InternalServerError):
        await user_repository.create(db=db_session, db_obj=user_to_create)


async def test_create_user_duplicate_username_fails(
    db_session: AsyncSession, sample_user: User
):
    """Tests that creating a user with a duplicate username raises an error."""
    user_create_schema = UserCreate(
        email="unique_email@example.com",
        username=sample_user.username,
        first_name="New",
        last_name="User",
        password="Hashed_pass_21",
    )
    user_to_create = prepare_user_model_from_schema(user_create_schema)
    # FIX: Expect InternalServerError because the decorator catches the IntegrityError
    with pytest.raises(InternalServerError):
        await user_repository.create(db=db_session, db_obj=user_to_create)


async def test_create_user_database_error_handling(
    db_session: AsyncSession, sample_user_data: dict
):
    """
    Test case: Database error during user creation.
    - GIVEN a database error occurs during creation.
    - WHEN the create method is called.
    - THEN an InternalServerError should be raised.
    """
    user_create = UserCreate(**sample_user_data)
    user_create.password = "hashed_password_placeholder"

    with patch.object(db_session, "commit", side_effect=Exception("Database error")):
        with pytest.raises(InternalServerError):
            await user_repository.create(db=db_session, db_obj=user_create)


# ==================== GET TESTS ====================


async def test_get_user_by_id_success(db_session: AsyncSession, sample_user: User):
    retrieved_user = await user_repository.get(db=db_session, obj_id=sample_user.id)
    assert retrieved_user is not None
    assert retrieved_user.id == sample_user.id


async def test_get_user_by_id_not_found(db_session: AsyncSession):
    """
    Test case: Attempt to retrieve a user with a non-existent ID.
    - GIVEN a non-existent user ID.
    - WHEN the get method is called.
    - THEN the result should be None.
    """
    non_existent_id = 99999
    retrieved_user = await user_repository.get(db=db_session, obj_id=non_existent_id)

    assert retrieved_user is None


async def test_get_user_by_id_negative_id(db_session: AsyncSession):
    """
    Test case: Attempt to retrieve a user with a negative ID.
    - GIVEN a negative user ID.
    - WHEN the get method is called.
    - THEN the result should be None.
    """
    negative_id = -1
    retrieved_user = await user_repository.get(db=db_session, obj_id=negative_id)

    assert retrieved_user is None


async def test_get_user_by_id_zero(db_session: AsyncSession):
    """
    Test case: Attempt to retrieve a user with ID zero.
    - GIVEN user ID is zero.
    - WHEN the get method is called.
    - THEN the result should be None.
    """
    retrieved_user = await user_repository.get(db=db_session, obj_id=0)

    assert retrieved_user is None


# ==================== GET BY EMAIL TESTS ====================


async def test_get_by_email_case_insensitive(
    db_session: AsyncSession, sample_user: User
):
    """
    Test case: Retrieve a user by email, ignoring case.
    - GIVEN an existing user.
    - WHEN the get_by_email method is called with various case combinations.
    - THEN the correct user is returned.
    """
    # Test uppercase
    uppercase_email = sample_user.email.upper()
    retrieved_user = await user_repository.get_by_email(
        db=db_session, email=uppercase_email
    )
    assert retrieved_user is not None
    assert retrieved_user.id == sample_user.id

    # Test mixed case
    mixed_case_email = sample_user.email[0].upper() + sample_user.email[1:].lower()
    retrieved_user = await user_repository.get_by_email(
        db=db_session, email=mixed_case_email
    )
    assert retrieved_user is not None
    assert retrieved_user.id == sample_user.id


async def test_get_by_email_not_found(db_session: AsyncSession):
    """
    Test case: Attempt to retrieve a user with a non-existent email.
    - GIVEN a non-existent email.
    - WHEN the get_by_email method is called.
    - THEN the result should be None.
    """
    non_existent_email = "nonexistent@example.com"
    retrieved_user = await user_repository.get_by_email(
        db=db_session, email=non_existent_email
    )

    assert retrieved_user is None


async def test_get_by_email_empty_string(db_session: AsyncSession):
    """
    Test case: Attempt to retrieve a user with an empty email string.
    - GIVEN an empty email string.
    - WHEN the get_by_email method is called.
    - THEN the result should be None.
    """
    retrieved_user = await user_repository.get_by_email(db=db_session, email="")

    assert retrieved_user is None


# ==================== GET BY USERNAME TESTS ====================


async def test_get_by_username_case_insensitive(
    db_session: AsyncSession, sample_user: User
):
    """
    Test case: Retrieve a user by username, ignoring case.
    - GIVEN an existing user.
    - WHEN the get_by_username method is called with various case combinations.
    - THEN the correct user is returned.
    """
    # Test uppercase
    uppercase_username = sample_user.username.upper()
    retrieved_user = await user_repository.get_by_username(
        db=db_session, username=uppercase_username
    )
    assert retrieved_user is not None
    assert retrieved_user.id == sample_user.id

    # Test mixed case
    mixed_case_username = (
        sample_user.username[0].upper() + sample_user.username[1:].lower()
    )
    retrieved_user = await user_repository.get_by_username(
        db=db_session, username=mixed_case_username
    )
    assert retrieved_user is not None
    assert retrieved_user.id == sample_user.id


async def test_get_by_username_not_found(db_session: AsyncSession):
    """
    Test case: Attempt to retrieve a user with a non-existent username.
    - GIVEN a non-existent username.
    - WHEN the get_by_username method is called.
    - THEN the result should be None.
    """
    non_existent_username = "nonexistentuser"
    retrieved_user = await user_repository.get_by_username(
        db=db_session, username=non_existent_username
    )

    assert retrieved_user is None


# ==================== GET ALL TESTS ====================


async def test_get_all_basic(db_session: AsyncSession, multiple_users: List[User]):
    """
    Test case: Get all users with default parameters.
    - GIVEN multiple users in the database.
    - WHEN get_all is called with default parameters.
    - THEN all users are returned with correct count.
    """
    users, total = await user_repository.get_all(db=db_session)

    assert len(users) == len(multiple_users)
    assert total == len(multiple_users)


async def test_get_all_with_pagination(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Get users with pagination.
    - GIVEN multiple users in the database.
    - WHEN get_all is called with skip and limit.
    - THEN the correct subset of users is returned.
    """
    # Get first 2 users
    users, total = await user_repository.get_all(db=db_session, skip=0, limit=2)
    assert len(users) == 2
    assert total == len(multiple_users)

    # Get next 2 users
    users, total = await user_repository.get_all(db=db_session, skip=2, limit=2)
    assert len(users) == min(2, len(multiple_users) - 2)
    assert total == len(multiple_users)

    # Skip beyond available users
    users, total = await user_repository.get_all(db=db_session, skip=100, limit=10)
    assert len(users) == 0
    assert total == len(multiple_users)


async def test_get_all_with_filters(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Get users with various filters.
    - GIVEN multiple users with different attributes.
    - WHEN get_all is called with filters.
    - THEN only matching users are returned.
    """
    # Filter by role
    filters = {"role": "user"}
    users, total = await user_repository.get_all(db=db_session, filters=filters)
    assert all(user.role == "user" for user in users)

    # Filter by is_active
    filters = {"is_active": True}
    users, total = await user_repository.get_all(db=db_session, filters=filters)
    assert all(user.is_active for user in users)

    # Filter by is_verified
    filters = {"is_verified": False}
    users, total = await user_repository.get_all(db=db_session, filters=filters)
    assert all(not user.is_verified for user in users)

    # Search filter
    if multiple_users:
        search_term = multiple_users[0].email.split("@")[0][:3]
        filters = {"search": search_term}
        users, total = await user_repository.get_all(db=db_session, filters=filters)
        assert len(users) > 0


async def test_get_all_with_combined_filters(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Get users with multiple filters combined.
    - GIVEN multiple users with different attributes.
    - WHEN get_all is called with multiple filters.
    - THEN only users matching all filters are returned.
    """
    filters = {"role": "user", "is_active": True, "is_verified": False}
    users, total = await user_repository.get_all(db=db_session, filters=filters)

    for user in users:
        assert user.role == "user"
        assert user.is_active is True
        assert user.is_verified is False


async def test_get_all_with_ordering(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Get users with different ordering options.
    - GIVEN multiple users in the database.
    - WHEN get_all is called with ordering parameters.
    - THEN users are returned in the correct order.
    """
    # Order by created_at descending (default)
    users, _ = await user_repository.get_all(db=db_session)
    for i in range(1, len(users)):
        assert users[i - 1].created_at >= users[i].created_at

    # Order by created_at ascending
    users, _ = await user_repository.get_all(db=db_session, order_desc=False)
    for i in range(1, len(users)):
        assert users[i - 1].created_at <= users[i].created_at

    # Order by email
    users, _ = await user_repository.get_all(
        db=db_session, order_by="email", order_desc=False
    )
    for i in range(1, len(users)):
        assert users[i - 1].email <= users[i].email


async def test_get_all_with_invalid_order_by(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Get users with invalid order_by field.
    - GIVEN multiple users in the database.
    - WHEN get_all is called with invalid order_by field.
    - THEN it should fall back to created_at ordering.
    """
    users, _ = await user_repository.get_all(db=db_session, order_by="invalid_field")
    # Should not raise error, falls back to created_at
    assert len(users) == len(multiple_users)


async def test_get_all_empty_database(db_session: AsyncSession):
    """
    Test case: Get all users from empty database.
    - GIVEN no users in the database.
    - WHEN get_all is called.
    - THEN empty list and zero count are returned.
    """
    users, total = await user_repository.get_all(db=db_session)

    assert users == []
    assert total == 0


# ==================== COUNT TESTS ====================


async def test_count_all_users(db_session: AsyncSession, multiple_users: List[User]):
    """
    Test case: Count all users without filters.
    - GIVEN multiple users in the database.
    - WHEN count is called without filters.
    - THEN the correct total count is returned.
    """
    count = await user_repository.count(db=db_session)

    assert count == len(multiple_users)


# ==================== COUNT TESTS (continued) ====================


async def test_count_with_filters(db_session: AsyncSession, multiple_users: List[User]):
    """
    Test case: Count users with filters.
    - GIVEN multiple users with different attributes.
    - WHEN count is called with filters.
    - THEN the correct filtered count is returned.
    """
    # Count by role
    filters = {"role": "user"}
    count = await user_repository.count(db=db_session, filters=filters)
    expected_count = sum(1 for user in multiple_users if user.role == "user")
    assert count == expected_count

    # Count by is_active
    filters = {"is_active": True}
    count = await user_repository.count(db=db_session, filters=filters)
    expected_count = sum(1 for user in multiple_users if user.is_active)
    assert count == expected_count


async def test_count_empty_database(db_session: AsyncSession):
    """
    Test case: Count users in empty database.
    - GIVEN no users in the database.
    - WHEN count is called.
    - THEN zero is returned.
    """
    count = await user_repository.count(db=db_session)

    assert count == 0


# ==================== UPDATE TESTS ====================


async def test_update_user_success(db_session: AsyncSession, sample_user: User):
    """
    Test case: Successfully update a user's details.
    - GIVEN an existing user.
    - WHEN the update method is called with new data.
    - THEN the user object is updated in the database.
    """
    update_data = UserUpdate(first_name="UpdatedFirstName")

    updated_user = await user_repository.update(
        db=db_session, db_obj=sample_user, obj_in=update_data
    )

    assert updated_user.first_name == "UpdatedFirstName"
    assert updated_user.last_name == sample_user.last_name

    # Verify persistence
    await db_session.refresh(updated_user)
    assert updated_user.first_name == "UpdatedFirstName"


async def test_update_user_multiple_fields(db_session: AsyncSession, sample_user: User):
    """
    Test case: Update multiple user fields at once.
    - GIVEN an existing user.
    - WHEN the update method is called with multiple fields.
    - THEN all specified fields are updated.
    """
    update_data = UserUpdate(
        first_name="NewFirst",
        last_name="NewLast",
        email="Name@example.com",
    )

    updated_user = await user_repository.update(
        db=db_session, db_obj=sample_user, obj_in=update_data
    )

    assert updated_user.first_name == "NewFirst"
    assert updated_user.last_name == "NewLast"
    assert updated_user.email == "Name@example.com"


async def test_update_user_with_empty_data_raises_error():
    """
    Test case: Attempt to update a user with an empty update schema.
    - GIVEN an empty UserUpdate schema.
    - WHEN the schema is created.
    - THEN a ValueError should be raised by our model validator.
    """
    with pytest.raises(
        ValueError, match="At least one field must be provided for update"
    ):
        # This line will raise the error, and pytest will catch it,
        # making the test pass.
        UserUpdate()


async def test_update_user_with_none_values(
    db_session: AsyncSession, sample_user: User
):
    """
    Test case: Update user with None values (should be ignored due to exclude_unset).
    - GIVEN an existing user.
    - WHEN the update method is called with None values.
    - THEN only explicitly set fields are updated.
    """
    update_data = UserUpdate(first_name="UpdatedName", last_name=None)

    updated_user = await user_repository.update(
        db=db_session, db_obj=sample_user, obj_in=update_data
    )

    assert updated_user.first_name == "UpdatedName"
    assert updated_user.last_name == sample_user.last_name  # Should remain unchanged


async def test_update_user_database_error(db_session: AsyncSession, sample_user: User):
    """
    Test case: Database error during user update.
    - GIVEN a database error occurs during update.
    - WHEN the update method is called.
    - THEN an InternalServerError should be raised.
    """
    update_data = UserUpdate(first_name="UpdatedName")

    with patch.object(db_session, "commit", side_effect=Exception("Database error")):
        with pytest.raises(InternalServerError):
            await user_repository.update(
                db=db_session, db_obj=sample_user, obj_in=update_data
            )


# ==================== DELETE TESTS ====================


async def test_delete_user_success(db_session: AsyncSession, sample_user: User):
    """
    Test case: Successfully delete a user.
    - GIVEN an existing user.
    - WHEN the delete method is called with the user's ID.
    - THEN the user is permanently removed from the database.
    """
    user_id_to_delete = sample_user.id

    await user_repository.delete(db=db_session, obj_id=user_id_to_delete)

    # Verify the user is gone
    deleted_user = await user_repository.get(db=db_session, obj_id=user_id_to_delete)
    assert deleted_user is None


async def test_delete_non_existent_user(db_session: AsyncSession):
    """
    Test case: Attempt to delete a non-existent user.
    - GIVEN a non-existent user ID.
    - WHEN the delete method is called.
    - THEN no error should be raised (idempotent operation).
    """
    non_existent_id = 99999

    # Should not raise an error
    await user_repository.delete(db=db_session, obj_id=non_existent_id)


async def test_delete_user_database_error(db_session: AsyncSession, sample_user: User):
    """
    Test case: Database error during user deletion.
    - GIVEN a database error occurs during deletion.
    - WHEN the delete method is called.
    - THEN an InternalServerError should be raised.
    """
    with patch.object(db_session, "commit", side_effect=Exception("Database error")):
        with pytest.raises(InternalServerError):
            await user_repository.delete(db=db_session, obj_id=sample_user.id)


# ==================== EXISTS TESTS ====================


async def test_exists_by_id(db_session: AsyncSession, sample_user: User):
    """
    Test case: Check user existence by ID.
    - GIVEN an existing user and a non-existent ID.
    - WHEN exists is called.
    - THEN correct boolean values are returned.
    """
    exists_true = await user_repository.exists(db=db_session, obj_id=sample_user.id)
    exists_false = await user_repository.exists(db=db_session, obj_id=99999)

    assert exists_true is True
    assert exists_false is False


async def test_exists_by_email(db_session: AsyncSession, sample_user: User):
    """
    Test case: Check user existence by email.
    - GIVEN an existing user and a non-existent email.
    - WHEN exists_by_email is called.
    - THEN correct boolean values are returned.
    """
    exists_true = await user_repository.exists_by_email(
        db=db_session, email=sample_user.email
    )
    exists_false = await user_repository.exists_by_email(
        db=db_session, email="nonexistent@example.com"
    )

    assert exists_true is True
    assert exists_false is False


async def test_exists_by_email_case_insensitive(
    db_session: AsyncSession, sample_user: User
):
    """
    Test case: Check user existence by email with different cases.
    - GIVEN an existing user.
    - WHEN exists_by_email is called with different case variations.
    - THEN True is returned for all variations.
    """
    exists_upper = await user_repository.exists_by_email(
        db=db_session, email=sample_user.email.upper()
    )
    exists_lower = await user_repository.exists_by_email(
        db=db_session, email=sample_user.email.lower()
    )
    exists_mixed = await user_repository.exists_by_email(
        db=db_session,
        email=sample_user.email[0].upper() + sample_user.email[1:].lower(),
    )

    assert exists_upper is True
    assert exists_lower is True
    assert exists_mixed is True


async def test_exists_by_username(db_session: AsyncSession, sample_user: User):
    """
    Test case: Check user existence by username.
    - GIVEN an existing user and a non-existent username.
    - WHEN exists_by_username is called.
    - THEN correct boolean values are returned.
    """
    exists_true = await user_repository.exists_by_username(
        db=db_session, username=sample_user.username
    )
    exists_false = await user_repository.exists_by_username(
        db=db_session, username="nonexistentuser"
    )

    assert exists_true is True
    assert exists_false is False


async def test_exists_by_username_case_insensitive(
    db_session: AsyncSession, sample_user: User
):
    """
    Test case: Check user existence by username with different cases.
    - GIVEN an existing user.
    - WHEN exists_by_username is called with different case variations.
    - THEN True is returned for all variations.
    """
    exists_upper = await user_repository.exists_by_username(
        db=db_session, username=sample_user.username.upper()
    )
    exists_lower = await user_repository.exists_by_username(
        db=db_session, username=sample_user.username.lower()
    )
    exists_mixed = await user_repository.exists_by_username(
        db=db_session,
        username=sample_user.username[0].upper() + sample_user.username[1:].lower(),
    )

    assert exists_upper is True
    assert exists_lower is True
    assert exists_mixed is True


# ==================== EDGE CASE TESTS ====================


async def test_special_characters_in_search(db_session: AsyncSession):
    user_create_schema = UserCreate(
        email="special@example.com",
        username="userwithspecial",
        first_name="Test",
        last_name="User (Special)",
        password="Hashed_password_placeholder21",
    )
    user_to_create = prepare_user_model_from_schema(user_create_schema)
    await user_repository.create(db=db_session, db_obj=user_to_create)

    dangerous_searches = ["'; DROP TABLE users; --", "' OR '1'='1"]
    for search_term in dangerous_searches:
        filters = {"search": search_term}
        users, total = await user_repository.get_all(db=db_session, filters=filters)
        assert isinstance(users, list)
        assert isinstance(total, int)


async def test_unicode_characters(db_session: AsyncSession):
    unicode_schema = UserCreate(
        email="unicode@example.com",
        username="unicode_user",
        first_name="José",
        last_name="García",
        password="Hashed_password_placeholder21",
    )
    user_to_create = prepare_user_model_from_schema(unicode_schema)
    user = await user_repository.create(db=db_session, db_obj=user_to_create)
    assert user.first_name == "José"
    assert user.last_name == "García"

    # Search
    filters = {"search": "José"}
    users, total = await user_repository.get_all(db=db_session, filters=filters)
    assert total >= 1
    assert any(u.id == user.id for u in users)


async def test_null_handling_in_filters(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Handle None/null values in filters.
    - GIVEN filters with None values.
    - WHEN get_all is called.
    - THEN None values are handled appropriately.
    """
    filters = {"role": None, "is_active": None, "is_verified": None, "search": None}

    users, total = await user_repository.get_all(db=db_session, filters=filters)
    # Should return all users as None filters are ignored
    assert total == len(multiple_users)


# ==================== EDGE CASE TESTS (continued) ====================


async def test_empty_string_filters(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Handle empty strings in filters.
    - GIVEN filters with empty strings.
    - WHEN get_all is called.
    - THEN empty strings are handled appropriately.
    """
    filters = {"role": "", "search": ""}

    users, total = await user_repository.get_all(db=db_session, filters=filters)
    # Empty strings should be ignored in filters
    assert total == len(multiple_users)


async def test_extreme_pagination_values(
    db_session: AsyncSession, multiple_users: List[User]
):
    """
    Test case: Handle extreme pagination values.
    - GIVEN extreme skip and limit values.
    - WHEN get_all is called.
    - THEN pagination handles edge cases gracefully.
    """
    # Very large skip
    users, total = await user_repository.get_all(db=db_session, skip=1000000, limit=10)
    assert len(users) == 0
    assert total == len(multiple_users)

    # Very large limit
    users, total = await user_repository.get_all(db=db_session, skip=0, limit=1000000)
    assert len(users) == len(multiple_users)

    # Negative skip (should be handled by validation, but test anyway)
    try:
        users, total = await user_repository.get_all(db=db_session, skip=-1, limit=10)
        # If it doesn't raise an error, it should treat negative as 0
        assert len(users) <= len(multiple_users)
    except ValueError:
        # Expected if validation is strict
        pass

    # Zero limit
    users, total = await user_repository.get_all(db=db_session, skip=0, limit=0)
    assert len(users) == 0
    assert total == len(multiple_users)


async def test_database_connection_error(db_session: AsyncSession):
    """
    Test case: Handle database connection errors.
    - GIVEN a database connection error.
    - WHEN any repository method is called.
    - THEN InternalServerError is raised.
    """
    with patch.object(db_session, "execute", side_effect=Exception("Connection lost")):
        with pytest.raises(InternalServerError):
            await user_repository.get(db=db_session, obj_id=1)


async def test_transaction_rollback_on_error(
    db_session: AsyncSession, sample_user_data: dict
):
    """Tests that a transaction is rolled back on error."""
    user_create_schema = UserCreate(**sample_user_data)
    user_to_create = prepare_user_model_from_schema(user_create_schema)

    # FIX: Patch the 'commit' method to simulate a failure during the transaction.
    with patch.object(
        db_session, "commit", side_effect=Exception("Simulated commit failure")
    ):
        with pytest.raises(InternalServerError):
            await user_repository.create(db=db_session, db_obj=user_to_create)

    # Verify user was not created because the transaction was rolled back
    user_exists = await user_repository.exists_by_email(
        db=db_session, email=sample_user_data["email"]
    )
    assert not user_exists


# # ==================== PERFORMANCE TESTS ====================


async def test_get_all_with_large_dataset(db_session: AsyncSession):
    """Tests repository performance with a larger number of users."""
    users_to_create = []
    for i in range(20):  # Reduced from 100 for faster testing
        user_schema = UserCreate(
            email=f"perf_test_{i}@example.com",
            username=f"perf_user_{i}",
            first_name=f"User{i}",
            last_name="Test",
            password="Hashed_password_placeholder21",
        )
        users_to_create.append(prepare_user_model_from_schema(user_schema))

    for user_model in users_to_create:
        await user_repository.create(db=db_session, db_obj=user_model)

    users, total = await user_repository.get_all(db=db_session, skip=10, limit=5)
    assert len(users) == 5
    assert total == 20


# # ==================== FILTER COMBINATION TESTS ====================


async def test_complex_filter_combinations(db_session: AsyncSession):
    """Tests that complex combinations of filters work correctly."""
    test_data = [
        {
            "email": "admin1@example.com",
            "username": "admin1",
            "role": UserRole.ADMIN,
            "is_active": True,
            "is_verified": True,
        },
        {
            "email": "admin2@example.com",
            "username": "admin2",
            "role": UserRole.ADMIN,
            "is_active": False,
            "is_verified": True,
        },
        {
            "email": "user1@example.com",
            "username": "user1",
            "role": UserRole.USER,
            "is_active": True,
            "is_verified": False,
        },
    ]

    for data in test_data:
        user_to_create = User(
            first_name="Test",
            last_name="User",
            hashed_password="hashed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            **data,
        )
        await user_repository.create(db=db_session, db_obj=user_to_create)

    filters = {"role": UserRole.ADMIN, "is_active": True, "is_verified": True}
    users, total = await user_repository.get_all(db=db_session, filters=filters)
    assert total == 1
    assert users[0].username == "admin1"


# ==================== BOUNDARY VALUE TESTS ====================
async def test_boundary_id_values(db_session: AsyncSession, sample_user: User):
    """
    Test case: Test boundary values for ID.
    - GIVEN an existing user and a very large ID.
    - WHEN repository methods are called.
    - THEN they handle boundaries correctly.
    """
    # Test a very large, non-existent ID
    large_id = 999999999999999
    user = await user_repository.get(db=db_session, obj_id=large_id)
    assert user is None

    # FIX: Test with a known, existing ID from our fixture.
    exists = await user_repository.exists(db=db_session, obj_id=sample_user.id)
    assert exists is True


async def test_email_username_edge_cases(db_session: AsyncSession):
    """Tests edge cases for email and username values."""
    user_create_schema = UserCreate(
        email="short@example.com",
        username="aaa",
        first_name="Test",
        last_name="User",
        password="Hashed__pass21",
    )
    user_to_create = prepare_user_model_from_schema(user_create_schema)
    user = await user_repository.create(db=db_session, db_obj=user_to_create)
    assert user.username == "aaa"

    user_create_schema_2 = UserCreate(
        email="test+tag@sub.example.com",
        username="user_with_plus",
        first_name="Test",
        last_name="User",
        password="Hashed__pass21",
    )
    user_to_create_2 = prepare_user_model_from_schema(user_create_schema_2)
    user2 = await user_repository.create(db=db_session, db_obj=user_to_create_2)
    assert user2.email == "test+tag@sub.example.com"

    retrieved = await user_repository.get_by_email(
        db=db_session, email="test+tag@sub.example.com"
    )
    assert retrieved is not None
    assert retrieved.id == user2.id


# # ==================== CONSISTENCY TESTS ====================


async def test_create_get_consistency(db_session: AsyncSession, sample_user_data: dict):
    """Tests that data remains consistent between create and get operations."""
    user_create_schema = UserCreate(**sample_user_data)
    created_user = await user_repository.create(
        db=db_session, db_obj=prepare_user_model_from_schema(user_create_schema)
    )
    retrieved_user = await user_repository.get(db=db_session, obj_id=created_user.id)

    assert retrieved_user is not None
    assert created_user.id == retrieved_user.id
    assert created_user.email == retrieved_user.email


async def test_update_get_consistency(db_session: AsyncSession, sample_user: User):
    """
    Test case: Ensure consistency between update and get operations.
    - GIVEN an updated user.
    - WHEN the user is retrieved immediately.
    - THEN all updates are reflected.
    """
    # FIX: Removed 'is_verified' as it's not in the UserUpdate schema.
    update_data = UserUpdate(first_name="ConsistencyTest")

    updated_user = await user_repository.update(
        db=db_session, db_obj=sample_user, obj_in=update_data
    )
    retrieved_user = await user_repository.get(db=db_session, obj_id=updated_user.id)

    assert retrieved_user is not None
    assert retrieved_user.first_name == "ConsistencyTest"
    assert retrieved_user.updated_at >= sample_user.updated_at


# ==================== ERROR RECOVERY TESTS ====================


async def test_partial_update_failure_recovery(
    db_session: AsyncSession, sample_user: User
):
    """
    Test case: Recovery from partial update failure.
    - GIVEN an update that partially fails.
    - WHEN the operation is retried.
    - THEN the system recovers gracefully.
    """
    update_data = UserUpdate(first_name="FailedUpdate")
    original_commit = db_session.commit

    async def failing_commit():
        raise Exception("Simulated commit failure")

    with patch.object(db_session, "commit", side_effect=failing_commit):
        with pytest.raises(InternalServerError):
            await user_repository.update(
                db=db_session, db_obj=sample_user, obj_in=update_data
            )

    # FIX: Re-fetch the user to get an object attached to the new session state.
    user_for_retry = await user_repository.get(db=db_session, obj_id=sample_user.id)

    # Second call should now succeed with the fresh object
    updated_user = await user_repository.update(
        db=db_session, db_obj=user_for_retry, obj_in=update_data
    )
    assert updated_user.first_name == "FailedUpdate"


# ==================== LOGGING TESTS ====================


async def test_logging_on_operations(
    db_session: AsyncSession, sample_user_data: dict, caplog
):
    """Tests that CRUD operations produce the expected log messages."""
    import logging

    caplog.set_level(logging.INFO)

    user_create_schema = UserCreate(**sample_user_data)
    user_to_create = prepare_user_model_from_schema(user_create_schema)
    user = await user_repository.create(db=db_session, db_obj=user_to_create)
    assert f"User created: {user.id}" in caplog.text

    update_data = UserUpdate(first_name="LogTest")
    updated = await user_repository.update(
        db=db_session, db_obj=user, obj_in=update_data
    )
    assert f"User updated: {updated.id}" in caplog.text

    await user_repository.delete(db=db_session, obj_id=user.id)
    assert f"User hard deleted: {user.id}" in caplog.text
