import logging
from typing import Optional, Dict, Any, List

from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from app.crud.book_crud import book_repository
from app.crud.tag_crud import tag_repository
from app.crud.book_tag_crud import book_tag_repository
from app.crud.user_crud import user_repository
from app.schemas.tag_schema import (
    TagCreate,
    TagUpdate,
    TagListResponse,
    TagSuggestion,
)
from sqlalchemy.exc import IntegrityError

from app.models.user_model import User
from app.models.tag_model import Tag
from app.schemas.book_schema import BookListResponse

from app.services.cache_service import cache_service
from app.core.exception_utils import raise_for_status
from app.core.exceptions import (
    ResourceNotFound,
    NotAuthorized,
    ValidationError,
    ResourceAlreadyExists,
)

logger = logging.getLogger(__name__)


class TagService:
    """
    Enhanced review service with business logic and authorization.

    This service extends the base CRUD service with additional
    business rules, authorization checks, and tag management.
    """

    def __init__(self):
        """
        Initializes the Tag Service.
        This version has no arguments, making it easy for FastAPI to use,
        while still allowing for dependency injection during tests.
        """
        self.user_repository = user_repository
        self.tag_repository = tag_repository
        self.book_repository = book_repository
        self.book_tag_repository = book_tag_repository
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _check_authorization(self, current_user: User, tag: Tag, action: str) -> None:
        """
        Check if user is authorized to perform action on book.
        """
        # Admins can do anything
        if current_user.is_admin:
            return

        # Users can only modify their own Books
        is_not_self = tag.created_by != current_user.id
        raise_for_status(
            condition=is_not_self,
            exception=NotAuthorized,
            detail=f"You are not authorized to {action} this user.",
        )

    async def get_by_id(self, db: AsyncSession, *, tag_id: int) -> Optional[Tag]:
        """Fetch tag by its ID"""

        if tag_id <= 0:
            raise ValidationError("Tag ID must be a positive integer")

        cached_tag = await cache_service.get(Tag, tag_id)
        if cached_tag:
            tag = await db.merge(cached_tag)
        else:
            tag = await self.tag_repository.get(db=db, obj_id=tag_id)
            raise_for_status(
                condition=tag is None,
                exception=ResourceNotFound,
                resource_type="Review",
                detail=f"Tag with id {tag_id} not found.",
            )

            await cache_service.set(tag)

        return tag

    async def get_tag_by_name(self, db: AsyncSession, *, name: str) -> Optional[Tag]:
        """Fetch tags by their name"""

        return await self.tag_repository.get_by_name(db=db, name=name)

    async def get_all_tags(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> TagListResponse:
        """Get all tags with optional filtering and pagination"""

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        tags, total = await self.tag_repository.get_many(
            db=db,
            skip=skip,
            limit=limit,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
        )

        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = (total + limit - 1) // limit  # Ceiling division

        # Construct the response schema
        response = TagListResponse(
            items=tags, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Tag list retrieved : {len(tags)} books returned")
        return response

    async def get_user_tags(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ):
        """Get all tags for a user."""

        # "verify user status"
        user = await self.user_repository.get(obj_id=user_id, db=db)

        raise_for_status(
            condition=user is None,
            exception=ResourceNotFound,
            resource_type="User",
            detail=f"User with id {user_id} not found.",
        )

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        if filters is None:
            filters = {}
        filters["user_id"] = user_id

        reviews, total = await self.tag_repository.get_many(
            db=db,
            skip=skip,
            limit=limit,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
        )

        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = (total + limit - 1) // limit  # Ceiling division

        # Construct the response schema
        response = TagListResponse(
            items=reviews, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Tag list retrieved : {len(reviews)} tags returned")
        return response

    async def get_books_by_tag_name(
        self, db: AsyncSession, *, tag_name: str, skip: int, limit: int
    ) -> BookListResponse:
        """
        Gets a paginated list of books for a specific tag, identified by its name.
        """
        # 1. First, find the tag by its name to get its ID.
        #    This is the "smart" part of the service logic.
        tag = await tag_repository.get_by_name(db=db, name=tag_name)

        # 2. Enforce the business rule: the tag must exist.
        raise_for_status(
            condition=(tag is None),
            exception=ResourceNotFound,
            resource_type="Tag",
            detail=f"Tag with name '{tag_name}' not found.",
        )

        # 3. Now, use the tag's ID to call our efficient, specialized repository method.
        books, total = await book_repository.get_all_by_tag(
            db=db, tag_id=tag.id, skip=skip, limit=limit
        )

        # 4. Construct the final response (our existing pattern).
        page = (skip // limit) + 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 0

        return BookListResponse(
            items=books, total=total, page=page, pages=total_pages, size=limit
        )

    # ========CREATE======
    async def create_tag(
        self, db: AsyncSession, *, tag_data: TagCreate, current_user: User
    ) -> Tag:
        """Create a new tag."""

        # check for conflicts
        existing_tag = await tag_repository.get_by_name(db=db, name=tag_data.name)
        raise_for_status(
            condition=existing_tag is not None,
            exception=ResourceAlreadyExists,
            detail=f"Tag with name '{tag_data.name}' already exists.",
            resource_type="Tag",
        )

        # Prepare the book model
        tag_dict = tag_data.model_dump()
        tag_dict["created_at"] = datetime.now(timezone.utc)
        tag_dict["updated_at"] = datetime.now(timezone.utc)
        tag_dict["created_by"] = current_user.id

        tag_to_create = Tag(**tag_dict)
        #  3. Delegate creation to the repository
        new_tag = await self.tag_repository.create(db=db, obj_in=tag_to_create)
        self._logger.info(f"New tag created: {new_tag.name}")

        return new_tag

    async def get_or_create_tag(
        self, db: AsyncSession, *, tag_name: str, current_user: User
    ) -> Tag:
        """
        Gets an existing tag by name or creates a new one if it doesn't exist.
        This method is idempotent and handles race conditions.
        This is the "smart" business logic.
        """
        # 1. Normalize the input to prevent duplicates (e.g., "Sci-Fi" vs "sci-fi")
        normalized_name = tag_name.strip().lower().replace(" ", "-")

        # 2. First, try to get the existing tag from the repository.
        existing_tag = await self.tag_repository.get_by_name(
            db=db, name=normalized_name
        )
        if existing_tag:
            return existing_tag

        # 3. If it doesn't exist, try to create it.
        try:
            # Prepare the new Tag model
            tag_to_create = Tag(
                name=normalized_name,
                created_by=current_user.id,
                # Other fields will use defaults from the model
            )

            new_tag = await self.tag_repository.create(db=db, obj_in=tag_to_create)
            return new_tag

        except IntegrityError:
            # 4. Handle the Race Condition:
            self._logger.warning(f"Race condition handled for tag: {normalized_name}")
            await db.rollback()  # Rollback the failed transaction

            # Re-fetch the now-existing tag
            tag = await self.tag_repository.get_by_name(db=db, name=normalized_name)
            return tag

    # ========UPDATE======
    async def update_tag(
        self,
        db: AsyncSession,
        *,
        tag_id_to_update: int,
        tag_data: TagUpdate,
        current_user: User,
    ):
        """Tag update using tag_id"""

        if tag_id_to_update <= 0:
            raise ValidationError("Tag ID must be a positive integer")

        tag_to_update = await self.get_by_id(db=db, tag_id=tag_id_to_update)

        self._check_authorization(
            current_user=current_user, tag=tag_to_update, action="update"
        )

        await self._validate_tag_update(db, tag_data, tag_to_update)

        update_dict = tag_data.model_dump(exclude_unset=True, exclude_none=True)

        for ts_field in {"created_at", "updated_at"}:
            update_dict.pop(ts_field, None)

        updated_tag = await self.tag_repository.update(
            db=db,
            tag=tag_to_update,
            fields_to_update=update_dict,
        )

        await cache_service.invalidate(Tag, tag_id_to_update)

        self._logger.info(
            f"Tag {tag_id_to_update} updated by {current_user.id}",
            extra={
                "updated_tag_id": tag_id_to_update,
                "updated_fields": list(update_dict.keys()),
            },
        )
        return updated_tag

    # ========DELETE======
    async def delete_tag(
        self, db: AsyncSession, tag_id_to_delete: int, current_user: User
    ) -> Dict[str, str]:
        """Hard deleting a tag by its ID"""

        # Input validation
        if tag_id_to_delete <= 0:
            raise ValidationError("Tag ID must be a positive integer")

        # 1. Fetch the user to delete
        tag_to_delete = await self.get_by_id(db, tag_id=tag_id_to_delete)

        # 2. Perform authorization check
        self._check_authorization(
            current_user=current_user,
            tag=tag_to_delete,
            action="delete",
        )

        # 3. Business rules validation
        await self._validate_tag_deletion(tag_to_delete, current_user)

        # 4. Perform the deletion
        await self.tag_repository.delete(db=db, obj_id=tag_id_to_delete)

        # 5. Clean up cache
        await cache_service.invalidate(Tag, tag_id_to_delete)

        self._logger.warning(
            f"Tag {tag_id_to_delete} permanently deleted by {current_user.id}",
            extra={
                "deleted_tag_id": tag_id_to_delete,
                "deleter_id": current_user.id,
                "deleted_tag_name": tag_to_delete.name,
            },
        )

        return {"message": "Tag deleted successfully"}

    # ========SUGGESTIONS======
    async def get_tag_suggestions(
        self,
        db: AsyncSession,
        book_id: Optional[int] = None,
        existing_tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[TagSuggestion]:  # Corrected return type
        """
        Get tag suggestions for a book.
        """
        suggestions = []

        if book_id:
            # --- THE FIX IS HERE: Unpack the tuple returned by get_many ---
            popular_tags_list, _ = await self.tag_repository.get_many(
                db=db,
                filters={"is_official": True},
                limit=limit + len(existing_tags or []),
            )

            # Now, loop over the list of tags directly
            for tag in popular_tags_list:
                if existing_tags and tag.name in existing_tags:
                    continue

                suggestions.append(
                    TagSuggestion(
                        tag=tag,
                        # The 'usage_count' field doesn't exist on our Tag model,
                        # so we'll use a placeholder confidence for now.
                        confidence=0.85,
                        reason="Popular tag in the library",
                    )
                )

                if len(suggestions) >= limit:
                    break

        return suggestions[:limit]

    async def get_related_tags(
        self, db: AsyncSession, *, tag_id: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Gets a list of tags related to a given tag.
        The business logic is that "relatedness" is defined by co-occurrence.
        """
        # First, ensure the original tag exists.
        tag = await self.tag_repository.get(db=db, obj_id=tag_id)
        raise_for_status(
            condition=(tag is None),
            exception=ResourceNotFound,
            resource_type="Tag",
            detail=f"Tag with id {tag_id} not found.",
        )

        # Delegate the complex query to the repository's specialized method.
        related_tags_data = await self.tag_repository.get_related_by_co_occurrence(
            db=db, tag_id=tag_id, limit=limit
        )

        return related_tags_data

    # Helper Functions
    async def _validate_tag_update(
        self, db: AsyncSession, tag_data: TagUpdate, existing_tag: Tag
    ) -> None:
        """Validates user update data for potential conflicts."""

        if tag_data.name and tag_data.name != existing_tag.name:
            if await self.tag_repository.get_by_name(db=db, name=tag_data.name):
                raise ResourceAlreadyExists("Name is already in use")

    async def _validate_tag_deletion(
        self, tag_to_delete: Tag, current_user: User
    ) -> None:

        if current_user.is_admin:
            return

        # Prevent self-deletion
        if current_user.id != tag_to_delete.created_by:
            raise ValidationError("Users cannot delete other's Tag.")


tag_service = TagService()
