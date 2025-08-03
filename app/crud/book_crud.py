# # app/crud/book_crud.py
# """
# Book CRUD operations module.

# This module provides database operations for Book entities following
# the repository pattern with comprehensive error handling and logging.
# """

# import logging
# from datetime import datetime, timedelta
# from typing import List, Optional, Dict, Any, Tuple, TypeVar, Generic
# from abc import ABC, abstractmethod

# from sqlmodel.ext.asyncio.session import AsyncSession
# from sqlmodel import select, func, and_, or_, col
# from sqlalchemy.orm import selectinload, joinedload
# from sqlalchemy.exc import IntegrityError, SQLAlchemyError
# from sqlalchemy import distinct

# from app.models.book_model import Book
# from app.models.tag_model import Tag
# from app.models.user_model import User
# from app.schemas.book_schema import (
#     BookCreate,
#     BookUpdate,
#     BookSearchParams,
#     BookListResponse,
#     BookResponse,
# )
# from app.core.exceptions import (
#     BookNotFound,
#     BookAlreadyExists,
#     DatabaseError,
#     ValidationError,
# )
# from app.core.cache import cache_key_wrapper, invalidate_cache
# from app.core.database import get_session_context

# logger = logging.getLogger(__name__)

# T = TypeVar("T")


# class BaseRepository(ABC, Generic[T]):
#     """Abstract base repository providing common database operations."""

#     def __init__(self, model: type[T]):
#         self.model = model

#     @abstractmethod
#     async def get(self, id: int, db: AsyncSession) -> Optional[T]:
#         """Get entity by ID."""
#         pass

#     @abstractmethod
#     async def create(self, entity: T, db: AsyncSession) -> T:
#         """Create new entity."""
#         pass

#     @abstractmethod
#     async def update(self, entity: T, db: AsyncSession) -> T:
#         """Update existing entity."""
#         pass

#     @abstractmethod
#     async def delete(self, id: int, db: AsyncSession) -> bool:
#         """Delete entity by ID."""
#         pass


# class BookRepository:
#     """
#     Repository class for Book entity operations.

#     This class encapsulates all database operations related to books,
#     providing a clean interface for the service layer.
#     """

#     def __init__(self):
#         self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

#     async def get_by_id(
#         self, book_id: int, db: AsyncSession, load_relationships: bool = True
#     ) -> Book:
#         """
#         Retrieve a book by its ID.

#         Args:
#             book_id: The book's primary key
#             db: Database session
#             load_relationships: Whether to load related entities

#         Returns:
#             Book object

#         Raises:
#             BookNotFound: If book doesn't exist
#             DatabaseError: If database operation fails
#         """
#         if book_id <= 0:
#             raise ValidationError(
#                 detail="Invalid book ID", field="book_id", value=book_id
#             )

#         try:
#             query = select(Book).where(Book.id == book_id)

#             if load_relationships:
#                 query = query.options(
#                     selectinload(Book.tags),
#                     selectinload(Book.user),
#                     selectinload(Book.reviews),
#                 )

#             result = await db.execute(query)
#             book = result.scalar_one_or_none()

#             if not book:
#                 raise BookNotFound(book_id=str(book_id))

#             self._logger.debug(f"Retrieved book: {book.id} - {book.title}")
#             return book

#         except BookNotFound:
#             raise
#         except SQLAlchemyError as e:
#             self._logger.error(
#                 f"Database error retrieving book {book_id}: {e}", exc_info=True
#             )
#             raise DatabaseError(detail=f"Failed to retrieve book", service="database")

#     async def get_many(
#         self,
#         db: AsyncSession,
#         params: BookSearchParams,
#         skip: int = 0,
#         limit: int = 100,
#     ) -> BookListResponse:
#         """
#         Retrieve books with filtering, search, and pagination.

#         Args:
#             db: Database session
#             params: Search parameters
#             skip: Number of records to skip
#             limit: Maximum number of records to return

#         Returns:
#             BookListResponse with paginated results

#         Raises:
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Build base query with relationships
#             query = select(Book).options(selectinload(Book.tags), joinedload(Book.user))

#             # Apply filters
#             query = self._apply_filters(query, params)

#             # Count total before pagination
#             count_query = select(func.count(distinct(Book.id))).select_from(
#                 query.subquery()
#             )
#             total = await db.scalar(count_query) or 0

#             # Apply ordering
#             query = self._apply_ordering(query, params)

#             # Apply pagination
#             query = query.offset(skip).limit(limit)

#             # Execute query
#             result = await db.execute(query)
#             books = result.unique().scalars().all()

#             # Calculate pagination info
#             pages = (total + limit - 1) // limit if limit > 0 else 0
#             current_page = (skip // limit) + 1 if limit > 0 else 1

#             self._logger.info(
#                 f"Retrieved {len(books)} books out of {total}",
#                 extra={
#                     "filters": params.model_dump(exclude_unset=True),
#                     "pagination": {"skip": skip, "limit": limit},
#                 },
#             )

#             return BookListResponse(
#                 items=books, total=total, page=current_page, pages=pages, size=limit
#             )

#         except SQLAlchemyError as e:
#             self._logger.error(f"Database error in get_many: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to retrieve books")

#     async def create(
#         self, book_data: BookCreate, user_id: int, db: AsyncSession
#     ) -> Book:
#         """
#         Create a new book.

#         Args:
#             book_data: Book creation data
#             user_id: ID of the user creating the book
#             db: Database session

#         Returns:
#             Created Book object

#         Raises:
#             BookAlreadyExists: If book already exists
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Check for duplicates
#             await self._check_duplicate(
#                 title=book_data.title,
#                 author=book_data.author,
#                 publisher=book_data.publisher,
#                 db=db,
#             )

#             # Create book instance
#             book = Book(**book_data.model_dump(exclude={"tags"}), user_id=user_id)

#             # Handle tags if provided
#             if book_data.tags:
#                 book.tags = await self._get_or_create_tags(book_data.tags, db)

#             db.add(book)
#             await db.commit()
#             await db.refresh(book)

#             # Invalidate relevant caches
#             await invalidate_cache(f"books:user:{user_id}")
#             await invalidate_cache("books:list:*")

#             self._logger.info(
#                 f"Book created: {book.id} - {book.title}",
#                 extra={
#                     "book_id": book.id,
#                     "user_id": user_id,
#                     "tags": [tag.name for tag in book.tags],
#                 },
#             )

#             return await self.get_by_id(book.id, db)

#         except BookAlreadyExists:
#             await db.rollback()
#             raise
#         except IntegrityError as e:
#             await db.rollback()
#             self._logger.error(f"Integrity error creating book: {e}")
#             raise BookAlreadyExists(title=book_data.title, author=book_data.author)
#         except SQLAlchemyError as e:
#             await db.rollback()
#             self._logger.error(f"Database error creating book: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to create book")

#     async def update(
#         self, book_id: int, book_data: BookUpdate, db: AsyncSession
#     ) -> Book:
#         """
#         Update an existing book.

#         Args:
#             book_id: ID of book to update
#             book_data: Update data
#             db: Database session

#         Returns:
#             Updated Book object

#         Raises:
#             BookNotFound: If book doesn't exist
#             BookAlreadyExists: If update would create duplicate
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Get existing book
#             book = await self.get_by_id(book_id, db, load_relationships=False)

#             # Get update data
#             update_dict = book_data.model_dump(exclude={"tags"}, exclude_unset=True)

#             # Check for duplicates if key fields are changing
#             if any(field in update_dict for field in ["title", "author", "publisher"]):
#                 await self._check_duplicate(
#                     title=update_dict.get("title", book.title),
#                     author=update_dict.get("author", book.author),
#                     publisher=update_dict.get("publisher", book.publisher),
#                     db=db,
#                     exclude_id=book_id,
#                 )

#             # Apply updates
#             for field, value in update_dict.items():
#                 setattr(book, field, value)

#             # Handle tags update
#             if book_data.tags is not None:
#                 book.tags = await self._get_or_create_tags(book_data.tags, db)

#             book.updated_at = datetime.utcnow()

#             await db.commit()
#             await db.refresh(book)

#             # Invalidate caches
#             await invalidate_cache(f"book:{book_id}")
#             await invalidate_cache(f"books:user:{book.user_id}")

#             self._logger.info(
#                 f"Book updated: {book_id}", extra={"updates": update_dict}
#             )

#             return await self.get_by_id(book_id, db)

#         except (BookNotFound, BookAlreadyExists):
#             await db.rollback()
#             raise
#         except SQLAlchemyError as e:
#             await db.rollback()
#             self._logger.error(f"Database error updating book: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to update book")

#     async def delete(self, book_id: int, db: AsyncSession) -> bool:
#         """
#         Delete a book.

#         Args:
#             book_id: ID of book to delete
#             db: Database session

#         Returns:
#             True if deleted successfully

#         Raises:
#             BookNotFound: If book doesn't exist
#             DatabaseError: If database operation fails
#         """
#         try:
#             book = await self.get_by_id(book_id, db, load_relationships=False)

#             await db.delete(book)
#             await db.commit()

#             # Invalidate caches
#             await invalidate_cache(f"book:{book_id}")
#             await invalidate_cache(f"books:user:{book.user_id}")

#             self._logger.info(f"Book deleted: {book_id}")
#             return True

#         except BookNotFound:
#             raise
#         except SQLAlchemyError as e:
#             await db.rollback()
#             self._logger.error(f"Database error deleting book: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to delete book")

#     async def get_by_user(
#         self, user_id: int, db: AsyncSession, skip: int = 0, limit: int = 100
#     ) -> List[Book]:
#         """
#         Get all books created by a specific user.

#         Args:
#             user_id: User's ID
#             db: Database session
#             skip: Pagination offset
#             limit: Maximum results

#         Returns:
#             List of Book objects
#         """
#         try:
#             query = (
#                 select(Book)
#                 .where(Book.user_id == user_id)
#                 .options(selectinload(Book.tags))
#                 .order_by(Book.created_at.desc())
#                 .offset(skip)
#                 .limit(limit)
#             )

#             result = await db.execute(query)
#             books = result.scalars().all()

#             return list(books)

#         except SQLAlchemyError as e:
#             self._logger.error(
#                 f"Database error getting books for user {user_id}: {e}", exc_info=True
#             )
#             raise DatabaseError(detail="Failed to retrieve user books")

#     async def get_statistics(self, db: AsyncSession) -> Dict[str, Any]:
#         """
#         Get statistical information about books.

#         Args:
#             db: Database session

#         Returns:
#             Dictionary with statistics
#         """
#         try:
#             stats = {}

#             # Total books
#             stats["total_books"] = await db.scalar(select(func.count(Book.id))) or 0

#             # Books by language
#             language_stats = await db.execute(
#                 select(Book.language, func.count(Book.id).label("count"))
#                 .group_by(Book.language)
#                 .order_by(col("count").desc())
#             )
#             stats["books_by_language"] = [
#                 {"language": row.language, "count": row.count} for row in language_stats
#             ]

#             # Recent books (last 30 days)
#             thirty_days_ago = datetime.utcnow() - timedelta(days=30)
#             stats["recent_books"] = (
#                 await db.scalar(
#                     select(func.count(Book.id)).where(
#                         Book.created_at >= thirty_days_ago
#                     )
#                 )
#                 or 0
#             )

#             # Top authors
#             author_stats = await db.execute(
#                 select(Book.author, func.count(Book.id).label("book_count"))
#                 .group_by(Book.author)
#                 .order_by(col("book_count").desc())
#                 .limit(10)
#             )
#             stats["top_authors"] = [
#                 {"author": row.author, "book_count": row.book_count}
#                 for row in author_stats
#             ]

#             # Average pages
#             stats["average_pages"] = (
#                 await db.scalar(select(func.avg(Book.page_count))) or 0
#             )

#             return stats

#         except SQLAlchemyError as e:
#             self._logger.error(f"Database error getting statistics: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to get statistics")

#     # Private helper methods

#     async def _check_duplicate(
#         self,
#         title: str,
#         author: str,
#         publisher: str,
#         db: AsyncSession,
#         exclude_id: Optional[int] = None,
#     ) -> None:
#         """
#         Check if a book with the same title, author, and publisher exists.

#         Args:
#             title: Book title
#             author: Book author
#             publisher: Book publisher
#             db: Database session
#             exclude_id: Book ID to exclude from check

#         Raises:
#             BookAlreadyExists: If duplicate found
#         """
#         query = select(Book).where(
#             and_(
#                 func.lower(Book.title) == title.lower(),
#                 func.lower(Book.author) == author.lower(),
#                 func.lower(Book.publisher) == publisher.lower(),
#             )
#         )

#         if exclude_id:
#             query = query.where(Book.id != exclude_id)

#         result = await db.execute(query)
#         if result.scalar_one_or_none():
#             raise BookAlreadyExists(title=title, author=author)

#     async def _get_or_create_tags(
#         self, tag_names: List[str], db: AsyncSession
#     ) -> List[Tag]:
#         """
#         Get existing tags or create new ones.

#         Args:
#             tag_names: List of tag names
#             db: Database session

#         Returns:
#             List of Tag objects
#         """
#         tags = []

#         for tag_name in tag_names:
#             # Check if tag exists
#             result = await db.execute(
#                 select(Tag).where(func.lower(Tag.name) == tag_name.lower())
#             )
#             tag = result.scalar_one_or_none()

#             if not tag:
#                 # Create new tag
#                 tag = Tag(name=tag_name)
#                 db.add(tag)

#             tags.append(tag)

#         return tags

#     def _apply_filters(self, query: select, params: BookSearchParams) -> select:
#         """Apply search filters to query."""
#         conditions = []

#         # Text search
#         if params.query:
#             search_term = f"%{params.query.strip()}%"
#             conditions.append(
#                 or_(
#                     Book.title.ilike(search_term),
#                     Book.author.ilike(search_term),
#                     Book.publisher.ilike(search_term),
#                 )
#             )

#         # Author filter
#         if params.author:
#             conditions.append(Book.author.ilike(f"%{params.author}%"))

#         # Language filter
#         if params.language:
#             conditions.append(Book.language == params.language.lower())

#         # Date range filters
#         if params.published_after:
#             conditions.append(Book.published_date >= params.published_after)

#         if params.published_before:
#             conditions.append(Book.published_date <= params.published_before)

#         # Page count filters
#         if params.min_pages:
#             conditions.append(Book.page_count >= params.min_pages)

#         if params.max_pages:
#             conditions.append(Book.page_count <= params.max_pages)

#         # Tag filter
#         if params.tags:
#             query = query.join(Book.tags)
#             tag_conditions = [
#                 func.lower(Tag.name).in_([tag.lower() for tag in params.tags])
#             ]
#             conditions.extend(tag_conditions)

#         if conditions:
#             query = query.where(and_(*conditions))

#         return query

#     def _apply_ordering(self, query: select, params: BookSearchParams) -> select:
#         """Apply ordering to query."""
#         # Default ordering
#         order_by = Book.created_at.desc()

#         # You can extend this to support different ordering options
#         # based on params if needed

#         return query.order_by(order_by)


# class BookService:
#     """
#     Service layer for book operations.

#     This class provides business logic and orchestrates repository operations.
#     """

#     def __init__(self, repository: BookRepository):
#         self.repository = repository
#         self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

#     @cache_key_wrapper("book:{book_id}", expire=3600)
#     async def get_book(self, book_id: int, db: AsyncSession) -> Book:
#         """
#         Get a book by ID with caching.

#         Args:
#             book_id: Book ID
#             db: Database session

#         Returns:
#             Book object
#         """
#         return await self.repository.get_by_id(book_id, db)

#     async def search_books(
#         self,
#         db: AsyncSession,
#         search_params: BookSearchParams,
#         page: int = 1,
#         size: int = 20,
#     ) -> BookListResponse:
#         """
#         Search books with pagination.

#         Args:
#             db: Database session
#             search_params: Search parameters
#             page: Page number (1-based)
#             size: Items per page

#         Returns:
#             Paginated book list
#         """
#         # Validate pagination
#         if page < 1:
#             raise ValidationError(detail="Page must be >= 1", field="page")
#         if size < 1 or size > 100:
#             raise ValidationError(detail="Size must be between 1 and 100", field="size")

#         skip = (page - 1) * size

#         return await self.repository.get_many(
#             db=db, params=search_params, skip=skip, limit=size
#         )

#     async def create_book(
#         self, book_data: BookCreate, user_id: int, db: AsyncSession
#     ) -> Book:
#         """
#         Create a new book.

#         Args:
#             book_data: Book creation data
#             user_id: ID of user creating the book
#             db: Database session

#         Returns:
#             Created book
#         """
#         # Additional business logic validation can go here

#         return await self.repository.create(book_data=book_data, user_id=user_id, db=db)

#     async def update_book(
#         self, book_id: int, book_data: BookUpdate, user_id: int, db: AsyncSession
#     ) -> Book:
#         """
#         Update a book.

#         Args:
#             book_id: Book ID
#             book_data: Update data
#             user_id: ID of user performing update
#             db: Database session

#         Returns:
#             Updated book

#         Raises:
#             NotAuthorized: If user doesn't own the book
#         """
#         # Check ownership
#         book = await self.repository.get_by_id(book_id, db, load_relationships=False)

#         if book.user_id != user_id:
#             from app.core.exceptions import NotAuthorized

#             raise NotAuthorized(
#                 detail="You can only update your own books",
#                 resource="book",
#                 action="update",
#             )

#         return await self.repository.update(book_id=book_id, book_data=book_data, db=db)

#     async def delete_book(self, book_id: int, user_id: int, db: AsyncSession) -> bool:
#         """
#         Delete a book.

#         Args:
#             book_id: Book ID
#             user_id: ID of user performing deletion
#             db: Database session

#         Returns:
#             True if deleted

#         Raises:
#             NotAuthorized: If user doesn't own the book
#         """
#         # Check ownership
#         book = await self.repository.get_by_id(book_id, db, load_relationships=False)

#         if book.user_id != user_id:
#             from app.core.exceptions import NotAuthorized

#             raise NotAuthorized(
#                 detail="You can only delete your own books",
#                 resource="book",
#                 action="delete",
#             )

#         return await self.repository.delete(book_id, db)

#     async def bulk_delete_books(
#         self, book_ids: List[int], user_id: int, db: AsyncSession
#     ) -> Dict[str, Any]:
#         """
#         Delete multiple books.

#         Args:
#             book_ids: List of book IDs
#             user_id: ID of user performing deletion
#             db: Database session

#         Returns:
#             Deletion results
#         """
#         results = {"deleted": [], "not_found": [], "unauthorized": [], "errors": []}

#         for book_id in book_ids:
#             try:
#                 await self.delete_book(book_id, user_id, db)
#                 results["deleted"].append(book_id)
#             except BookNotFound:
#                 results["not_found"].append(book_id)
#             except NotAuthorized:
#                 results["unauthorized"].append(book_id)
#             except Exception as e:
#                 results["errors"].append({"book_id": book_id, "error": str(e)})

#         return results

#     @cache_key_wrapper("books:stats", expire=3600)
#     async def get_statistics(self, db: AsyncSession) -> Dict[str, Any]:
#         """Get book statistics with caching."""
#         return await self.repository.get_statistics(db)


# # Factory function to create service with repository
# def get_book_service() -> BookService:
#     """Create and return book service instance."""
#     repository = BookRepository()
#     return BookService(repository)


# # For backward compatibility, expose main functions
# book_service = get_book_service()


# async def get_all_books(
#     db: AsyncSession,
#     skip: int = 0,
#     limit: int = 100,
#     search: Optional[str] = None,
#     author_filter: Optional[str] = None,
#     tag_filter: Optional[str] = None,
#     user_id: Optional[int] = None,
#     order_by: str = "created_at",
#     order_desc: bool = True,
# ) -> Dict[str, Any]:
#     """Legacy function for backward compatibility."""
#     params = BookSearchParams(
#         query=search, author=author_filter, tags=[tag_filter] if tag_filter else None
#     )

#     result = await book_service.search_books(
#         db=db,
#         search_params=params,
#         page=(skip // limit) + 1 if limit > 0 else 1,
#         size=limit,
#     )

#     return {
#         "books": result.items,
#         "total": result.total,
#         "skip": skip,
#         "limit": limit,
#         "has_next": result.page < result.pages,
#         "has_previous": result.page > 1,
#     }


# async def get_book_by_id(book_id: int, db: AsyncSession) -> Optional[Book]:
#     """Legacy function for backward compatibility."""
#     try:
#         return await book_service.get_book(book_id, db)
#     except BookNotFound:
#         return None


# async def create_book(book: Book, db: AsyncSession) -> Book:
#     """Legacy function for backward compatibility."""
#     book_data = BookCreate(
#         title=book.title,
#         author=book.author,
#         publisher=book.publisher,
#         language=book.language,
#         page_count=book.page_count,
#         published_date=book.published_date,
#         tags=[tag.name for tag in book.tags] if book.tags else None,
#     )

#     return await book_service.create_book(
#         book_data=book_data, user_id=book.user_id, db=db
#     )


# async def update_book(
#     db: AsyncSession, book_to_update: Book, book_data: BookUpdate
# ) -> Optional[Book]:
#     """Legacy function for backward compatibility."""
#     try:
#         return await book_service.repository.update(
#             book_id=book_to_update.id, book_data=book_data, db=db
#         )
#     except BookNotFound:
#         return None


# async def delete_book(book_id: int, db: AsyncSession) -> Optional[Book]:
#     """Legacy function for backward compatibility."""
#     try:
#         book = await book_service.get_book(book_id, db)
#         await book_service.repository.delete(book_id, db)
#         return book
#     except BookNotFound:
#         return None


# __all__ = [
#     # Service and Repository classes
#     "BookRepository",
#     "BookService",
#     "get_book_service",
#     # Legacy functions
#     "get_all_books",
#     "get_book_by_id",
#     "create_book",
#     "update_book",
#     "delete_book",
# ]
