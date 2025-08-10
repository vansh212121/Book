import logging
from typing import Optional, Dict, Any, List

from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from app.crud.book_crud import book_repository
from app.crud.review_crud import review_repository
from app.crud.user_crud import user_repository
from app.crud.review_vote_crud import review_vote_repository
from app.schemas.review_schema import (
    ReviewCreate,
    ReviewUpdate,
    ReviewListResponse,
    ReviewVoteResponse,
)
from app.models.user_model import User
from app.models.book_model import Book
from app.models.review_model import Review
from app.models.review_vote_model import ReviewVote


from app.services.cache_service import cache_service
from app.core.exception_utils import raise_for_status
from app.core.exceptions import (
    ResourceNotFound,
    NotAuthorized,
    ValidationError,
    ResourceAlreadyExists,
    BadRequestException,
)

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Enhanced review service with business logic and authorization.

    This service extends the base CRUD service with additional
    business rules, authorization checks, and tag management.
    """

    def __init__(self):
        """
        Initializes the UserService.
        This version has no arguments, making it easy for FastAPI to use,
        while still allowing for dependency injection during tests.
        """
        self.user_repository = user_repository
        self.review_repository = review_repository
        self.book_repository = book_repository
        self.review_vote_repository = review_vote_repository
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _check_authorization(
        self, current_user: User, review: Review, action: str
    ) -> None:
        """
        Check if user is authorized to perform action on book.
        """
        # Admins can do anything
        if current_user.is_admin:
            return

        # Users can only modify their own Books
        is_not_self = review.user_id != current_user.id
        raise_for_status(
            condition=is_not_self,
            exception=NotAuthorized,
            detail=f"You are not authorized to {action} this user.",
        )

    # ======= READ OPERATIONS =======
    async def get_review_by_id(
        self, db: AsyncSession, *, review_id: int
    ) -> Optional[Review]:
        """Get a review by its ID"""

        if review_id <= 0:
            raise ValidationError("Book ID must be a positive integer")

        cached_review = await cache_service.get(Review, review_id)
        if cached_review:
            review = await db.merge(cached_review)
        else:
            review = await self.review_repository.get(db=db, obj_id=review_id)
            raise_for_status(
                condition=review is None,
                exception=ResourceNotFound,
                resource_type="Review",
                detail=f"Review with id {review_id} not found.",
            )

            await cache_service.set(review)

        return review

    async def get_book_reviews(
        self,
        db: AsyncSession,
        *,
        book_id: int,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ):
        """Get all reviews for a book with summary statistics."""

        # "verify book status"
        book = await self.book_repository.get(db=db, obj_id=book_id)

        raise_for_status(
            condition=book is None,
            exception=ResourceNotFound,
            resource_type="Book",
            detail=f"Book with id {book_id} not found.",
        )

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        if filters is None:
            filters = {}
        filters["book_id"] = book_id

        reviews, total = await self.review_repository.get_many(
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
        response = ReviewListResponse(
            items=reviews, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Review list retrieved : {len(reviews)} reviews returned")
        return response

    async def get_user_reviews(
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
        """Get all reviews for a book with summary statistics."""

        # "verify book status"
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

        reviews, total = await self.review_repository.get_many(
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
        response = ReviewListResponse(
            items=reviews, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Review list retrieved : {len(reviews)} reviews returned")
        return response

    async def get_reviews(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> ReviewListResponse:
        """Get all reviews with optional filtering and pagination"""

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        reviews, total = await self.review_repository.get_many(
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
        response = ReviewListResponse(
            items=reviews, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Review list retrieved : {len(reviews)} books returned")
        return response

    # ========CREATE======
    async def create_review(
        self,
        db: AsyncSession,
        *,
        review_data: ReviewCreate,
        book_id: int,
        current_user: User,
    ) -> Review:
        """Create a review using ReveiwCreate"""

        # Fetch the book
        book = await self.book_repository.get(db=db, obj_id=book_id)
        raise_for_status(
            condition=(book is None),
            exception=ResourceNotFound,
            resource_type="Book",
            resource_id=book_id,
        )

        # Check for conflicts
        existing_review = await self.review_repository.get_by_user_and_books(
            db=db, user_id=current_user.id, book_id=book_id
        )
        raise_for_status(
            condition=existing_review is not None,
            exception=ResourceAlreadyExists,
            detail=f"Review with title '{review_data.title}' already exists.",
            resource_type="Review",
        )

        # Prepare the review model
        review_dict = review_data.model_dump()
        review_dict["created_at"] = datetime.now(timezone.utc)
        review_dict["updated_at"] = datetime.now(timezone.utc)
        review_dict["user_id"] = current_user.id
        review_dict["book_id"] = book.id
        # review_dict["book_id"] = review_data.book_id

        review_to_create = Review(**review_dict)
        #  3. Delegate creation to the repository
        new_review = await self.review_repository.create(db=db, obj_in=review_to_create)
        self._logger.info(f"New review created: {new_review.title}")

        return new_review

    # ========UPDATE======
    async def update_review(
        self,
        db: AsyncSession,
        *,
        review_id_to_update: int,
        review_data: ReviewUpdate,
        current_user: int,
    ) -> Review:
        """Review update using review_id"""

        if review_id_to_update <= 0:
            raise ValidationError("Review ID must be a positive integer")

        review_to_update = await self.get_review_by_id(
            db=db, review_id=review_id_to_update
        )

        self._check_authorization(
            current_user=current_user, review=review_to_update, action="update"
        )

        await self._validate_review_update(db, review_data, review_to_update)

        update_dict = review_data.model_dump(exclude_unset=True, exclude_none=True)

        # Remove timestamp fields that should not be manually updated
        for ts_field in {"created_at", "updated_at"}:
            update_dict.pop(ts_field, None)

        updated_review = await self.review_repository.update(
            db=db, review=review_to_update, fields_to_update=update_dict
        )

        await cache_service.invalidate(Review, review_id_to_update)

        self._logger.info(
            f"Review {review_id_to_update} updated by {current_user.id}",
            extra={
                "updated_review_id": review_id_to_update,
                "updated_fields": list(update_dict.keys()),
            },
        )
        return updated_review

    # ========DELETE=======
    async def delete(
        self, db: AsyncSession, *, review_id_to_delete: int, current_user: User
    ) -> Dict[str, str]:
        """Delete review by its ID"""

        if review_id_to_delete <= 0:
            raise ValidationError("Review ID must be a positive Integer")

        review_to_delete = await self.get_review_by_id(
            db=db, review_id=review_id_to_delete
        )

        raise_for_status(
            condition=review_to_delete is None,
            exception=ResourceNotFound,
            resource_type="Review",
            detail=f"Review with id:{review_id_to_delete} not found.",
        )

        # 2. Perform authorization check
        self._check_authorization(
            current_user=current_user,
            review=review_to_delete,
            action="delete",
        )

        # 3. Business rules validation
        await self._validate_review_deletion(review_to_delete, current_user)

        # 4. Perform the deletion
        await self.review_repository.delete(db=db, obj_id=review_id_to_delete)

        # 5. Clean up cache and tokens
        await cache_service.invalidate(Review, review_id_to_delete)

        self._logger.warning(
            f"Review {review_id_to_delete} permanently deleted by {current_user.id}",
            extra={
                "deleted_review_id": review_id_to_delete,
                "deleter_id": current_user.id,
                "deleted_review_title": review_to_delete.title,
            },
        )

        return {"message": "Book deleted successfully"}

    # ======ENGAGEMENT Operations======
    # async def vote_on_review(
    #     self,
    #     db: AsyncSession,
    #     *,
    #     review_id: int,
    #     is_helpful: bool,
    #     current_user: User,
    # ) -> ReviewVote:
    #     """
    #     Handles the business logic for a user voting on a review.
    #     """
    #     # 1. Fetch the review to be voted on.
    #     review = await self.get_review_by_id(db=db, review_id=review_id)
    #     raise_for_status(
    #         condition=review is None,
    #         exception=ResourceNotFound,
    #         resource_type="Review",
    #         detail=f"Review with id:{review} not found.",
    #     )

    #     # 2. Perform authorization check
    #     self._check_authorization(
    #         current_user=current_user,
    #         review=review,
    #         action="vote",
    #     )

    #     # 3. Check for an existing vote from this user on this review.
    #     existing_vote = await self.review_vote_repository.get(
    #         db, user_id=current_user.id, review_id=review_id
    #     )

    #     fields_to_update = {}

    #     # 4. Determine the action based on the new vote and any existing vote.
    #     if existing_vote:
    #         if existing_vote.is_helpful == is_helpful:
    #             # User is clicking the same button again - this means "un-vote".
    #             await review_vote_repository.delete(db, vote=existing_vote)
    #             if is_helpful:
    #                 fields_to_update["helpful_count"] = review.helpful_count - 1
    #             else:
    #                 fields_to_update["unhelpful_count"] = review.unhelpful_count - 1
    #         else:
    #             # User is changing their vote (e.g., from helpful to unhelpful).
    #             raise BadRequestException(
    #                 detail="You have already voted on this review. To change your vote, please remove your existing vote first."
    #             )
    #     else:
    #         # No existing vote - this is a new vote.
    #         new_vote = ReviewVote(
    #             user_id=current_user.id, review_id=review_id, is_helpful=is_helpful
    #         )
    #         await review_vote_repository.create(db, vote=new_vote)
    #         if is_helpful:
    #             fields_to_update["helpful_count"] = review.helpful_count + 1
    #         else:
    #             fields_to_update["unhelpful_count"] = review.unhelpful_count + 1

    #     # 5. Save the updated counts on the review using the repository
    #     updated_review = await self.review_repository.update(
    #         db=db, review=review, fields_to_update=fields_to_update
    #     )

    #     # 6. Invalidate the cache for the updated review.
    #     await cache_service.invalidate(Review, review_id)

    #     return updated_review

    async def vote_on_review(
        self,
        db: AsyncSession,
        *,
        review_id: int,
        is_helpful: bool,
        current_user: User,
    ) -> ReviewVoteResponse:  # <-- The return type now matches the endpoint's promise
        """
        Handles the business logic for a user voting on a review.
        """
        # 1. Fetch the review to be voted on.
        review = await self.get_review_by_id(db=db, review_id=review_id)
        # Note: get_review_by_id already handles the "not found" case.

        # 2. Enforce Business Rules
        if review.user_id == current_user.id:
            raise BadRequestException(detail="You cannot vote on your own review.")

        # 3. Check for an existing vote from this user on this review.
        existing_vote = await review_vote_repository.get(
            db, user_id=current_user.id, review_id=review_id
        )

        fields_to_update = {}
        current_user_vote_status = None

        # 4. Determine the action based on the new vote and any existing vote.
        if existing_vote:
            if existing_vote.is_helpful == is_helpful:
                # User is clicking the same button again - this means "un-vote".
                await review_vote_repository.delete(db=db, vote=existing_vote)
                if is_helpful:
                    fields_to_update["helpful_count"] = review.helpful_count - 1
                else:
                    fields_to_update["unhelpful_count"] = review.unhelpful_count - 1
                # The user's vote is now None
                current_user_vote_status = None
            else:
                # User is changing their vote (e.g., from helpful to unhelpful).
                raise BadRequestException(
                    detail="You have already voted on this review. To change your vote, please remove your existing vote first."
                )
        else:
            # No existing vote - this is a new vote.
            new_vote = ReviewVote(
                user_id=current_user.id, review_id=review_id, is_helpful=is_helpful
            )
            await review_vote_repository.create(db=db, vote=new_vote)
            if is_helpful:
                fields_to_update["helpful_count"] = review.helpful_count + 1
                current_user_vote_status = "helpful"
            else:
                fields_to_update["unhelpful_count"] = review.unhelpful_count + 1
                current_user_vote_status = "unhelpful"

        # 5. Save the updated counts on the review using the repository
        updated_review = await self.review_repository.update(
            db=db, review=review, fields_to_update=fields_to_update
        )

        # 6. Invalidate the cache for the updated review.
        await cache_service.invalidate(Review, review_id)

        # 7. ** THE FIX IS HERE **
        #    Construct and return the correct response schema.
        return ReviewVoteResponse(
            review_id=updated_review.id,
            helpful_count=updated_review.helpful_count,
            unhelpful_count=updated_review.unhelpful_count,
            user_vote=current_user_vote_status,
        )

    # Helper Functions
    async def _validate_review_update(
        self, db: AsyncSession, review_data: ReviewUpdate, existing_review: Review
    ) -> None:
        """Validates review update data for potential conflicts."""

        if review_data.title and review_data.title != existing_review.title:
            if await self.review_repository.get_by_title(
                db=db, title=review_data.title
            ):
                raise ResourceAlreadyExists("Title is already in use")

    async def _validate_review_deletion(
        self, review_to_delete: ReviewCreate, current_user: User
    ) -> None:

        # Prevent self-deletion
        if current_user.id != review_to_delete.user_id:
            raise ValidationError("Users cannot delete other's Review/s.")


review_service = ReviewService()
