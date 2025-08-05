# # app/api/v1/endpoints/book.py
# """
# Book API endpoints.

# This module provides RESTful API endpoints for book management,
# including CRUD operations, search, and bulk operations.
# """

# import logging
# from typing import List, Dict, Any, Optional

# from fastapi import APIRouter, status, Depends, Query, Path, Body
# from fastapi.responses import JSONResponse

# from app.core.config import settings
# from app.models.user_model import User
# from app.schemas.book_schema import (
#     BookCreate,
#     BookUpdate,
#     BookResponse,
#     BookResponseWithTags,
#     BookResponseWithUser,
#     BookResponseDetailed,
#     BookListResponse,
#     BookSearchParams,
# )
# from app.schemas.common import MessageResponse, BulkOperationResponse, ErrorResponse
# from sqlmodel.ext.asyncio.session import AsyncSession
# from app.services.book_service import book_service
# from app.db.session import get_session
# from app.utils.deps import (
#     get_current_verified_user,
#     get_current_active_user,
#     get_optional_current_user,
#     RateLimiter,
# )
# from app.core.exceptions import BookNotFound, NotAuthorized

# logger = logging.getLogger(__name__)

# router = APIRouter(
#     tags=["Books"],
#     prefix=f"{settings.API_V1_STR}/books",
#     responses={
#         401: {"description": "Not authenticated"},
#         403: {"description": "Not authorized"},
#         404: {"description": "Not found"},
#     },
# )


# # --- READ Endpoints ---


# @router.get(
#     "/",
#     status_code=status.HTTP_200_OK,
#     response_model=BookListResponse,
#     summary="Get all books",
#     description="Retrieve a paginated list of books with optional filtering and search",
# )
# async def get_all_books(
#     *,
#     db: AsyncSession = Depends(get_session),
#     current_user: Optional[User] = Depends(get_optional_current_user),
#     # Pagination
#     page: int = Query(1, ge=1, description="Page number"),
#     size: int = Query(20, ge=1, le=100, description="Items per page"),
#     # Search and filters
#     search: Optional[str] = Query(
#         None, description="Search in title, author, publisher"
#     ),
#     author: Optional[str] = Query(None, description="Filter by author"),
#     language: Optional[str] = Query(None, description="Filter by language"),
#     tags: Optional[List[str]] = Query(None, description="Filter by tags"),
#     published_after: Optional[str] = Query(
#         None, description="Filter by publication date (YYYY-MM-DD)"
#     ),
#     published_before: Optional[str] = Query(
#         None, description="Filter by publication date (YYYY-MM-DD)"
#     ),
#     min_pages: Optional[int] = Query(None, gt=0, description="Minimum page count"),
#     max_pages: Optional[int] = Query(None, gt=0, description="Maximum page count"),
#     # User filter
#     user_id: Optional[int] = Query(None, description="Filter by user ID (admin only)"),
#     my_books: bool = Query(False, description="Show only my books"),
# ):
#     """
#     Get all books with advanced filtering and pagination.

#     - **page**: Page number (starts from 1)
#     - **size**: Number of items per page
#     - **search**: Search term for title, author, or publisher
#     - **author**: Filter by author name
#     - **language**: Filter by language code
#     - **tags**: Filter by tag names (multiple allowed)
#     - **published_after**: Books published after this date
#     - **published_before**: Books published before this date
#     - **min_pages**: Minimum number of pages
#     - **max_pages**: Maximum number of pages
#     - **user_id**: Filter by user ID (admin only)
#     - **my_books**: Show only books created by current user
#     """
#     # Build search parameters
#     search_params = BookSearchParams(
#         query=search,
#         author=author,
#         language=language,
#         tags=tags,
#         published_after=published_after,
#         published_before=published_before,
#         min_pages=min_pages,
#         max_pages=max_pages,
#     )

#     # Handle user filtering
#     if my_books and current_user:
#         search_params.user_id = current_user.id
#     elif user_id and current_user and current_user.is_admin:
#         search_params.user_id = user_id

#     return await book_service.get_all_books(
#         db=db, search_params=search_params, page=page, size=size, user=current_user
#     )


# @router.get(
#     "/my-books",
#     status_code=status.HTTP_200_OK,
#     response_model=BookListResponse,
#     summary="Get my books",
#     description="Get all books created by the current user",
# )
# async def get_my_books(
#     *,
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
#     page: int = Query(1, ge=1, description="Page number"),
#     size: int = Query(20, ge=1, le=100, description="Items per page"),
# ):
#     """Get all books created by the authenticated user."""
#     return await book_service.get_user_books(
#         user=current_user, db=db, page=page, size=size
#     )


# @router.get(
#     "/statistics",
#     status_code=status.HTTP_200_OK,
#     response_model=Dict[str, Any],
#     summary="Get book statistics",
#     description="Get statistical information about books",
# )
# async def get_book_statistics(
#     *,
#     db: AsyncSession = Depends(get_session),
#     current_user: Optional[User] = Depends(get_optional_current_user),
#     include_user_stats: bool = Query(
#         False, description="Include user-specific statistics"
#     ),
# ):
#     """
#     Get book statistics.

#     Returns general statistics about books in the system.
#     If authenticated and include_user_stats is true, also returns user-specific statistics.
#     """
#     user = current_user if include_user_stats else None
#     return await book_service.get_statistics(db=db, user=user)


# @router.get(
#     "/{book_id}",
#     status_code=status.HTTP_200_OK,
#     response_model=BookResponseDetailed,
#     summary="Get book by ID",
#     description="Get detailed information about a specific book",
# )
# async def get_book_by_id(
#     *,
#     db: AsyncSession = Depends(get_session),
#     book_id: int = Path(..., description="The ID of the book to retrieve"),
#     include_reviews: bool = Query(True, description="Include reviews in response"),
# ):
#     """
#     Get detailed information about a specific book.

#     Returns book details including tags, user information, and optionally reviews.
#     """
#     return await book_service.get_book_by_id(
#         book_id=book_id, db=db, include_reviews=include_reviews
#     )


# # --- CREATE Endpoints ---


# @router.post(
#     "/",
#     status_code=status.HTTP_201_CREATED,
#     response_model=BookResponseWithTags,
#     summary="Create a new book",
#     description="Create a new book entry",
#     dependencies=[
#         Depends(RateLimiter(times=10, seconds=60))
#     ],  # Rate limit: 10 books per minute
# )
# async def create_book(
#     *,
#     book_data: BookCreate = Body(
#         ...,
#         example={
#             "title": "The Great Gatsby",
#             "author": "F. Scott Fitzgerald",
#             "publisher": "Charles Scribner's Sons",
#             "language": "en",
#             "page_count": 180,
#             "published_date": "1925-04-10",
#             "tags": ["fiction", "classic", "american-literature"],
#         },
#     ),
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
# ):
#     """
#     Create a new book.

#     - **title**: The title of the book (required)
#     - **author**: The author of the book (required)
#     - **publisher**: The publisher of the book (required)
#     - **language**: Language code (e.g., 'en', 'es', 'fr')
#     - **page_count**: Number of pages
#     - **published_date**: Publication date (YYYY-MM-DD)
#     - **tags**: List of tag names to associate with the book

#     The book will be associated with the authenticated user.
#     """
#     return await book_service.create_book(db=db, book_data=book_data, user=current_user)


# @router.post(
#     "/bulk",
#     status_code=status.HTTP_201_CREATED,
#     response_model=BulkOperationResponse,
#     summary="Create multiple books",
#     description="Create multiple books in a single request",
#     dependencies=[
#         Depends(RateLimiter(times=5, seconds=60))
#     ],  # Stricter rate limit for bulk
# )
# async def create_books_bulk(
#     *,
#     books_data: List[BookCreate] = Body(
#         ..., min_items=1, max_items=50, description="List of books to create"
#     ),
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
# ):
#     """
#     Create multiple books in a single request.

#     Maximum 50 books per request.
#     Returns information about successful and failed creations.
#     """
#     results = {"successful": [], "failed": [], "total": len(books_data)}

#     for idx, book_data in enumerate(books_data):
#         try:
#             book = await book_service.create_book(
#                 db=db, book_data=book_data, user=current_user
#             )
#             results["successful"].append(
#                 {"index": idx, "book_id": book.id, "title": book.title}
#             )
#         except Exception as e:
#             results["failed"].append(
#                 {"index": idx, "title": book_data.title, "error": str(e)}
#             )
#             logger.error(f"Failed to create book at index {idx}: {e}")

#     return results


# # --- UPDATE Endpoints ---


# @router.patch(
#     "/{book_id}",
#     response_model=BookResponseWithTags,
#     status_code=status.HTTP_200_OK,
#     summary="Update a book",
#     description="Update book information",
# )
# async def update_book(
#     *,
#     book_id: int = Path(..., description="The ID of the book to update"),
#     book_data: BookUpdate = Body(
#         ...,
#         example={"title": "Updated Title", "page_count": 200, "tags": ["updated-tag"]},
#     ),
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
# ):
#     """
#     Update a book.

#     Only the book owner or an admin can update a book.
#     Only provided fields will be updated.
#     """
#     return await book_service.update_book(
#         db=db, book_id=book_id, book_data=book_data, user=current_user
#     )


# # --- DELETE Endpoints ---


# @router.delete(
#     "/{book_id}",
#     status_code=status.HTTP_200_OK,
#     response_model=MessageResponse,
#     summary="Delete a book",
#     description="Delete a book by ID",
# )
# async def delete_book(
#     *,
#     book_id: int = Path(..., description="The ID of the book to delete"),
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
# ):
#     """
#     Delete a book.

#     Only the book owner or an admin can delete a book.
#     This will also delete all associated reviews.
#     """
#     await book_service.delete_book(db=db, book_id=book_id, user=current_user)

#     return MessageResponse(message=f"Book {book_id} deleted successfully")


# @router.post(
#     "/bulk-delete",
#     status_code=status.HTTP_200_OK,
#     response_model=Dict[str, Any],
#     summary="Delete multiple books",
#     description="Delete multiple books in a single request",
# )
# async def delete_books_bulk(
#     *,
#     book_ids: List[int] = Body(
#         ...,
#         min_items=1,
#         max_items=100,
#         description="List of book IDs to delete",
#         example=[1, 2, 3],
#     ),
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
# ):
#     """
#     Delete multiple books in a single request.

#     Only books owned by the user (or any book for admins) will be deleted.
#     Returns information about successful and failed deletions.
#     """
#     return await book_service.bulk_delete_books(
#         db=db, book_ids=book_ids, user=current_user
#     )


# # --- Export Endpoints ---


# @router.get(
#     "/export/csv",
#     status_code=status.HTTP_200_OK,
#     summary="Export books to CSV",
#     description="Export filtered books to CSV format",
# )
# async def export_books_csv(
#     *,
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_active_user),
#     # Same filters as get_all_books
#     search: Optional[str] = Query(None),
#     author: Optional[str] = Query(None),
#     language: Optional[str] = Query(None),
#     tags: Optional[List[str]] = Query(None),
#     my_books: bool = Query(True, description="Export only my books"),
# ):
#     """
#     Export books to CSV format.

#     Applies the same filters as the book list endpoint.
#     By default, exports only the user's own books.
#     """
#     # Build search parameters
#     search_params = BookSearchParams(
#         query=search,
#         author=author,
#         language=language,
#         tags=tags,
#         user_id=current_user.id if my_books else None,
#     )

#     # Get books (no pagination for export)
#     result = await book_service.get_all_books(
#         db=db, search_params=search_params, page=1, size=10000  # Max export size
#     )

#     # Convert to CSV
#     import csv
#     import io

#     output = io.StringIO()
#     writer = csv.writer(output)

#     # Write headers
#     writer.writerow(
#         [
#             "ID",
#             "Title",
#             "Author",
#             "Publisher",
#             "Language",
#             "Page Count",
#             "Published Date",
#             "Tags",
#             "Created At",
#         ]
#     )

#     # Write data
#     for book in result.items:
#         writer.writerow(
#             [
#                 book.id,
#                 book.title,
#                 book.author,
#                 book.publisher,
#                 book.language,
#                 book.page_count,
#                 book.published_date.isoformat(),
#                 ", ".join([tag.name for tag in book.tags]),
#                 book.created_at.isoformat(),
#             ]
#         )

#     # Return CSV response
#     from fastapi.responses import Response

#     return Response(
#         content=output.getvalue(),
#         media_type="text/csv",
#         headers={
#             "Content-Disposition": f"attachment; filename=books_export_{current_user.id}.csv"
#         },
#     )


# @router.exception_handler(BookNotFound)
# async def book_not_found_handler(request, exc: BookNotFound):
#     """Handle book not found exceptions."""
#     return JSONResponse(
#         status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
#     )


# @router.exception_handler(NotAuthorized)
# async def not_authorized_handler(request, exc: NotAuthorized):
#     """Handle authorization exceptions."""
#     return JSONResponse(
#         status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)}
#     )


# # --- Additional Utility Endpoints ---


# @router.post(
#     "/{book_id}/duplicate",
#     status_code=status.HTTP_201_CREATED,
#     response_model=BookResponseWithTags,
#     summary="Duplicate a book",
#     description="Create a copy of an existing book",
# )
# async def duplicate_book(
#     *,
#     book_id: int = Path(..., description="The ID of the book to duplicate"),
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
#     title_suffix: str = Body(
#         " (Copy)", description="Suffix to add to the duplicated book's title"
#     ),
# ):
#     """
#     Create a duplicate of an existing book.

#     The duplicated book will:
#     - Have the same metadata as the original
#     - Be owned by the current user
#     - Have a modified title to distinguish it from the original
#     - Keep the same tags as the original
#     """
#     # Get original book
#     original_book = await book_service.get_book_by_id(book_id, db)

#     # Create new book data
#     book_data = BookCreate(
#         title=f"{original_book.title}{title_suffix}",
#         author=original_book.author,
#         publisher=original_book.publisher,
#         language=original_book.language,
#         page_count=original_book.page_count,
#         published_date=original_book.published_date,
#         tags=[tag.name for tag in original_book.tags],
#     )

#     return await book_service.create_book(db=db, book_data=book_data, user=current_user)


# @router.get(
#     "/search/suggestions",
#     status_code=status.HTTP_200_OK,
#     response_model=Dict[str, List[str]],
#     summary="Get search suggestions",
#     description="Get autocomplete suggestions for book search",
# )
# async def get_search_suggestions(
#     *,
#     db: AsyncSession = Depends(get_session),
#     query: str = Query(..., min_length=2, description="Search query"),
#     field: str = Query("all", pattern="^(all|title|author|publisher)$"),
#     limit: int = Query(10, ge=1, le=50),
# ):
#     """
#     Get search suggestions based on partial input.

#     - **query**: Partial search term (minimum 2 characters)
#     - **field**: Field to search in (all, title, author, publisher)
#     - **limit**: Maximum number of suggestions
#     """
#     suggestions = {"titles": [], "authors": [], "publishers": []}

#     search_term = f"{query}%"

#     if field in ["all", "title"]:
#         # Get title suggestions
#         result = await db.execute(
#             select(Book.title)
#             .where(Book.title.ilike(search_term))
#             .distinct()
#             .limit(limit)
#         )
#         suggestions["titles"] = [row[0] for row in result]

#     if field in ["all", "author"]:
#         # Get author suggestions
#         result = await db.execute(
#             select(Book.author)
#             .where(Book.author.ilike(search_term))
#             .distinct()
#             .limit(limit)
#         )
#         suggestions["authors"] = [row[0] for row in result]

#     if field in ["all", "publisher"]:
#         # Get publisher suggestions
#         result = await db.execute(
#             select(Book.publisher)
#             .where(Book.publisher.ilike(search_term))
#             .distinct()
#             .limit(limit)
#         )
#         suggestions["publishers"] = [row[0] for row in result]

#     return suggestions


# @router.get(
#     "/filters/options",
#     status_code=status.HTTP_200_OK,
#     response_model=Dict[str, Any],
#     summary="Get filter options",
#     description="Get available options for book filters",
# )
# async def get_filter_options(
#     *,
#     db: AsyncSession = Depends(get_session),
#     current_user: Optional[User] = Depends(get_optional_current_user),
# ):
#     """
#     Get available filter options for the book list.

#     Returns lists of unique values for:
#     - Languages
#     - Authors
#     - Publishers
#     - Publication years
#     - Available tags
#     """
#     # Get unique languages
#     languages_result = await db.execute(
#         select(Book.language, func.count(Book.id))
#         .group_by(Book.language)
#         .order_by(func.count(Book.id).desc())
#     )

#     # Get top authors
#     authors_result = await db.execute(
#         select(Book.author, func.count(Book.id))
#         .group_by(Book.author)
#         .order_by(func.count(Book.id).desc())
#         .limit(50)
#     )

#     # Get top publishers
#     publishers_result = await db.execute(
#         select(Book.publisher, func.count(Book.id))
#         .group_by(Book.publisher)
#         .order_by(func.count(Book.id).desc())
#         .limit(50)
#     )

#     # Get publication years
#     years_result = await db.execute(
#         select(func.extract("year", Book.published_date).label("year"))
#         .distinct()
#         .order_by("year")
#     )

#     # Get popular tags
#     from app.models.tag_model import Tag
#     from app.models.book_tag_model import BookTag

#     tags_result = await db.execute(
#         select(Tag.name, func.count(BookTag.book_id).label("count"))
#         .join(BookTag)
#         .group_by(Tag.name)
#         .order_by(func.count(BookTag.book_id).desc())
#         .limit(50)
#     )

#     return {
#         "languages": [{"code": row[0], "count": row[1]} for row in languages_result],
#         "authors": [{"name": row[0], "count": row[1]} for row in authors_result],
#         "publishers": [{"name": row[0], "count": row[1]} for row in publishers_result],
#         "years": [int(row[0]) for row in years_result if row[0]],
#         "tags": [{"name": row[0], "count": row[1]} for row in tags_result],
#     }


# # --- Health Check ---


# @router.get(
#     "/health",
#     status_code=status.HTTP_200_OK,
#     response_model=MessageResponse,
#     summary="Books endpoint health check",
#     description="Check if the books endpoint is operational",
#     include_in_schema=False,
# )
# async def health_check():
#     """Simple health check for the books endpoint."""
#     return MessageResponse(message="Books endpoint is healthy")
