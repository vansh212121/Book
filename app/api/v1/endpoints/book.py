import logging

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    rate_limit_heavy,
    rate_limit_api,
    require_admin,
    rate_limit_auth,
    PaginationParams,
)

from app.schemas.book_schema import (
    BookCreate,
    BookListResponse,
    BookResponseDetailed,
    BookResponseWithUser,
    BookResponse,
    BookUpdate,
    BookSearchParams,
)
from app.utils.deps import get_pagination_params
from app.models.book_model import Book
from app.models.user_model import User
from app.services.book_service import book_service


logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Books"],
    prefix=f"{settings.API_V1_STR}/books",
)


@router.get(
    "/bulk",
    # response_model=List[BookResponseDetailed],
    response_model=List[BookResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Multiple Books by IDs",
    description="Retrieves the full details for a list of book IDs.",
    dependencies=[Depends(rate_limit_api)],
)
async def get_books_in_bulk(
    *,
    db: AsyncSession = Depends(get_session),
    ids: List[int] = Query(
        ..., description="A comma-separated list of book IDs to fetch."
    ),
):
    """
    Retrieves a list of books based on the provided IDs.
    """
    return await book_service.get_by_ids(db=db, book_ids=ids)


@router.get(
    "/all",
    response_model=BookListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all books",
    description="Retrieve a paginated list of books with optional filtering and search",
    dependencies=[Depends(rate_limit_api)],
)
async def get_all_books(
    *,
    db: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: BookSearchParams = Depends(BookSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """
    Get all books with advanced filtering and pagination.

    - **page**: Page number (starts from 1)
    - **search**: Search term for title, author, or publisher
    - **author**: Filter by author name
    - **language**: Filter by language code
    - **tags**: Filter by tag names (multiple allowed)
    - **published_after**: Books published after this date
    - **published_before**: Books published before this date
    - **min_pages**: Minimum number of pages
    - **max_pages**: Maximum number of pages
    """
    return await book_service.get_books(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=search_params.model_dump(exclude_none=True),
        order_by=order_by,
        order_desc=order_desc,
    )


@router.post(
    "/",
    # response_model=BookResponseWithUser, Add later on when tags and review is built
    response_model=BookResponse,
    summary="Create a new book",
    status_code=status.HTTP_200_OK,
    description="Create a new book entry",
    dependencies=[Depends(rate_limit_api)],
)
async def create_book(
    *,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
    book_data: BookCreate,
):
    """
    Create a new book.
    - **title**: The title of the book (required)
    - **author**: The author of the book (required)
    - **publisher**: The publisher of the book (required)
    - **language**: Language code (e.g., 'en', 'es', 'fr')
    - **page_count**: Number of pages
    - **published_date**: Publication date (YYYY-MM-DD)
    - **tags**: List of tag names to associate with the book

    The book will be associated with the authenticated user.
    """
    return await book_service.create_book(
        db=db, book_data=book_data, current_user=current_user
    )


@router.get(
    "/{book_id}",
    status_code=status.HTTP_200_OK,
    # response_model=BookResponseDetailed,
    response_model=BookResponse,
    description="Get book by its id for book detail's page.",
    summary="Get book by id  profile",
    dependencies=[Depends(rate_limit_api)],
)
async def get_book_by_id(*, db: AsyncSession = Depends(get_session), book_id: int):
    """Get book by its ID"""
    return await book_service.get_book_by_id(db=db, book_id=book_id)


@router.patch(
    "/{book_id}",
    # response_model=BookResponseWithUser,
    response_model=BookResponse,
    summary="Update a book",
    status_code=status.HTTP_200_OK,
    description="Update a book by it's ID",
    dependencies=[Depends(rate_limit_api)],
)
async def update_book(
    *,
    db: AsyncSession = Depends(get_session),
    book_id: int,
    book_data: BookUpdate,
    current_user: User = Depends(get_current_verified_user),
):
    """
    Update a book.

    Only the book owner or an admin can update a book.
    Only provided fields will be updated.
    """
    return await book_service.update_book(
        db=db, book_id_to_update=book_id, book_data=book_data, current_user=current_user
    )


@router.delete(
    "/{book_id}",
    response_model=Dict[str, str],
    summary="Delete a book",
    status_code=status.HTTP_200_OK,
    description="Delete a book by it's Id",
    dependencies=[Depends(rate_limit_api)],
)
async def delete_book(
    *,
    db: AsyncSession = Depends(get_session),
    book_id: int,
    current_user: User = Depends(get_current_verified_user),
):
    """
    Delete a book.

    Only the book owner or an admin can delete a book.
    This will also delete all associated reviews.
    """
    await book_service.delete_book(
        db=db, book_id_to_delete=book_id, current_user=current_user
    )

    return {"message": "Book deleted succesfully"}


@router.put(
    "/{book_id}/transfer",
    status_code=status.HTTP_200_OK,
    summary="Transfer book ownership",
    response_model=Dict[str, str],
    description="Transfer ownership of a book to another user (admin only)",
    dependencies=[Depends(require_admin), Depends(rate_limit_api)],
)
async def transfer_ownership(
    *,
    db: AsyncSession = Depends(get_session),
    book_id: int,
    new_owner: int,
    cuurent_user: User = Depends(get_current_verified_user),
):
    """
    Transfer book ownership to another user (admin only).
    """

    updated_book = await book_service.transfer_ownership(
        db=db,
        new_owner_id=new_owner,
        book_id=book_id,
        admin_user=cuurent_user,
    )

    return {"message": f"Book transfered successfully to {new_owner}"}
