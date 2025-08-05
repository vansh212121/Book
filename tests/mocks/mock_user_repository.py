# tests/mocks/mock_user_repository.py
from typing import List, Optional, Dict, Any, Tuple
from app.models.user_model import User


class FakeUserRepository:
    """
    A fake user repository that uses an in-memory list for testing.
    It mimics the interface of the real UserRepository.
    """

    def __init__(self, initial_users: List[User] = None):
        self.users = initial_users or []
        self._next_id = len(self.users) + 1 if self.users else 1

    async def get(self, db, *, obj_id: int) -> Optional[User]:
        """Finds a user by ID in the in-memory list."""
        for user in self.users:
            if user.id == obj_id:
                return user
        return None

    async def get_by_email(self, db, *, email: str) -> Optional[User]:
        """Finds a user by email in the in-memory list."""
        for user in self.users:
            if user.email.lower() == email.lower():
                return user
        return None

    async def get_by_username(self, db, *, username: str) -> Optional[User]:
        """Finds a user by username in the in-memory list."""
        for user in self.users:
            if user.username.lower() == username.lower():
                return user
        return None

    async def create(self, db, *, db_obj: User) -> User:
        """Adds a new user to the in-memory list."""
        if not db_obj.id:
            db_obj.id = self._next_id
            self._next_id += 1
        self.users.append(db_obj)
        return db_obj

    async def update(self, db, *, user: User, fields_to_update: Dict[str, Any]) -> User:
        """Updates specific fields of a user in the in-memory list."""
        for field, value in fields_to_update.items():
            setattr(user, field, value)
        return user

    async def delete(self, db, *, obj_id: int) -> None:
        """Removes a user from the in-memory list by ID."""
        self.users = [user for user in self.users if user.id != obj_id]

    async def get_all(
        self,
        db,
        *,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> Tuple[List[User], int]:
        """Gets all users with pagination and filtering."""
        filtered_users = self.users

        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                filtered_users = [
                    u for u in filtered_users if getattr(u, key, None) == value
                ]

        # Simple ordering (just reverse for desc)
        if order_desc:
            filtered_users = list(reversed(filtered_users))

        total = len(filtered_users)
        paginated_users = filtered_users[skip : skip + limit]

        return paginated_users, total

    async def count(self, db, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """Counts users matching the filters."""
        if not filters:
            return len(self.users)

        count = 0
        for user in self.users:
            match = True
            for key, value in filters.items():
                if getattr(user, key, None) != value:
                    match = False
                    break
            if match:
                count += 1
        return count
