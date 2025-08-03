
# import logging
# from typing import List, Optional, Dict, Any

# from sqlmodel.ext.asyncio.session import AsyncSession
# from sqlmodel import select, func, col
# from sqlalchemy.orm import selectinload
# from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# from app.models.tag_model import Tag
# from app.schemas.tag_schema import TagCreate, TagUpdate, TagListResponse
# from app.core.exceptions import (
#     TagNotFound,
#     TagAlreadyExists,
#     DatabaseError,
#     ValidationError
# )
# from app.core.cache import cache_key_wrapper, invalidate_cache

# logger = logging.getLogger(__name__)


# class TagRepository:
#     """
#     Repository class for Tag entity operations.
    
#     This class encapsulates all database operations related to tags,
#     providing a clean interface for the service layer.
#     """
    
#     def __init__(self):
#         self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
#     async def get_by_id(
#         self,
#         tag_id: int,
#         db: AsyncSession,
#         load_relationships: bool = True
#     ) -> Tag:
#         """
#         Retrieve a tag by its ID.
        
#         Args:
#             tag_id: The tag's primary key
#             db: Database session
#             load_relationships: Whether to load related entities
            
#         Returns:
#             Tag object
            
#         Raises:
#             TagNotFound: If tag doesn't exist
#             DatabaseError: If database operation fails
#         """
#         if tag_id <= 0:
#             raise ValidationError(
#                 detail="Invalid tag ID",
#                 field="tag_id",
#                 value=tag_id
#             )
        
#         try:
#             query = select(Tag).where(Tag.id == tag_id)
            
#             if load_relationships:
#                 query = query.options(selectinload(Tag.books))
            
#             result = await db.execute(query)
#             tag = result.scalar_one_or_none()
            
#             if not tag:
#                 raise TagNotFound(tag_id=str(tag_id))
            
#             self._logger.debug(f"Retrieved tag: {tag.id} - {tag.name}")
#             return tag
            
#         except TagNotFound:
#             raise
#         except SQLAlchemyError as e:
#             self._logger.error(
#                 f"Database error retrieving tag {tag_id}: {e}",
#                 exc_info=True
#             )
#             raise DatabaseError(
#                 detail="Failed to retrieve tag",
#                 service="database"
#             )
    
#     async def get_by_name(
#         self,
#         name: str,
#         db: AsyncSession
#     ) -> Optional[Tag]:
#         """
#         Get a tag by its unique name (case-insensitive).
        
#         Args:
#             name: Tag name
#             db: Database session
            
#         Returns:
#             Tag object or None if not found
#         """
#         try:
#             normalized_name = name.strip().lower()
            
#             result = await db.execute(
#                 select(Tag).where(func.lower(Tag.name) == normalized_name)
#             )
#             tag = result.scalar_one_or_none()
            
#             if tag:
#                 self._logger.debug(f"Found tag by name: {tag.name}")
            
#             return tag
            
#         except SQLAlchemyError as e:
#             self._logger.error(
#                 f"Database error getting tag by name '{name}': {e}",
#                 exc_info=True
#             )
#             # Return None instead of raising to maintain backward compatibility
#             return None
    
#     async def get_all(
#         self,
#         db: AsyncSession,
#         skip: int = 0,
#         limit: int = 100,
#         search: Optional[str] = None,
#         order_by: str = "name",
#         order_desc: bool = False
#     ) -> TagListResponse:
#         """
#         Get all tags with pagination and optional search.
        
#         Args:
#             db: Database session
#             skip: Number of records to skip
#             limit: Maximum number of records to return
#             search: Optional search term for tag names
#             order_by: Field to order by
#             order_desc: Whether to order in descending order
            
#         Returns:
#             TagListResponse with paginated results
            
#         Raises:
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Build base query
#             query = select(Tag)
            
#             # Apply search filter
#             if search:
#                 search_term = f"%{search.strip()}%"
#                 query = query.where(Tag.name.ilike(search_term))
            
#             # Count total before pagination
#             count_query = select(func.count(Tag.id)).select_from(query.subquery())
#             total = await db.scalar(count_query) or 0
            
#             # Apply ordering
#             order_column = getattr(Tag, order_by, Tag.name)
#             if order_desc:
#                 query = query.order_by(order_column.desc())
#             else:
#                 query = query.order_by(order_column.asc())
            
#             # Apply pagination
#             query = query.offset(skip).limit(limit)
            
#             # Execute query
#             result = await db.execute(query)
#             tags = result.scalars().all()
            
#             # Calculate pagination info
#             pages = (total + limit - 1) // limit if limit > 0 else 0
#             current_page = (skip // limit) + 1 if limit > 0 else 1
            
#             self._logger.info(
#                 f"Retrieved {len(tags)} tags out of {total}",
#                 extra={
#                     "search": search,
#                     "pagination": {"skip": skip, "limit": limit}
#                 }
#             )
            
#             return TagListResponse(
#                 items=list(tags),
#                 total=total,
#                 page=current_page,
#                 pages=pages,
#                 size=limit
#             )
            
#         except SQLAlchemyError as e:
#             self._logger.error(f"Database error in get_all: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to retrieve tags")
    
#     async def create(
#         self,
#         tag_data: TagCreate,
#         db: AsyncSession
#     ) -> Tag:
#         """
#         Create a new tag.
        
#         Args:
#             tag_data: Tag creation data
#             db: Database session
            
#         Returns:
#             Created Tag object
            
#         Raises:
#             TagAlreadyExists: If tag with same name exists
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Normalize tag name
#             normalized_name = tag_data.name.strip().lower()
            
#             # Check if tag already exists
#             existing_tag = await self.get_by_name(normalized_name, db)
#             if existing_tag:
#                 raise TagAlreadyExists(tag_name=normalized_name)
            
#             # Create new tag
#             new_tag = Tag(name=normalized_name)
            
#             db.add(new_tag)
#             await db.commit()
#             await db.refresh(new_tag)
            
#             # Invalidate cache
#             await invalidate_cache("tags:list:*")
            
#             self._logger.info(
#                 f"Tag created: {new_tag.id} - {new_tag.name}",
#                 extra={"tag_id": new_tag.id, "tag_name": new_tag.name}
#             )
            
#             return new_tag
            
#         except TagAlreadyExists:
#             await db.rollback()
#             raise
#         except IntegrityError as e:
#             await db.rollback()
#             self._logger.error(f"Integrity error creating tag: {e}")
#             raise TagAlreadyExists(tag_name=tag_data.name)
#         except SQLAlchemyError as e:
#             await db.rollback()
#             self._logger.error(f"Database error creating tag: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to create tag")
    
#     async def get_or_create(
#         self,
#         db: AsyncSession,
#         name: str
#     ) -> Tag:
#         """
#         Get existing tag or create new one.
        
#         Args:
#             db: Database session
#             name: Tag name
            
#         Returns:
#             Tag object (existing or newly created)
#         """
#         normalized_name = name.strip().lower()
        
#         # Try to get existing tag
#         tag = await self.get_by_name(normalized_name, db)
#         if tag:
#             return tag
        
#         # Create new tag
#         try:
#             tag_data = TagCreate(name=normalized_name)
#             return await self.create(tag_data, db)
#         except TagAlreadyExists:
#             # Handle race condition - tag was created by another request
#             tag = await self.get_by_name(normalized_name, db)
#             if tag:
#                 return tag
#             raise
    
#     async def update(
#         self,
#         tag_id: int,
#         tag_data: TagUpdate,
#         db: AsyncSession
#     ) -> Tag:
#         """
#         Update an existing tag.
        
#         Args:
#             tag_id: ID of tag to update
#             tag_data: Update data
#             db: Database session
            
#         Returns:
#             Updated Tag object
            
#         Raises:
#             TagNotFound: If tag doesn't exist
#             TagAlreadyExists: If new name conflicts with existing tag
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Get existing tag
#             tag = await self.get_by_id(tag_id, db, load_relationships=False)
            
#             # Get update data
#             update_dict = tag_data.model_dump(exclude_unset=True)
            
#             # Check if name is being updated
#             if "name" in update_dict:
#                 new_name = update_dict["name"].strip().lower()
                
#                 # Check if new name already exists
#                 existing_tag = await self.get_by_name(new_name, db)
#                 if existing_tag and existing_tag.id != tag_id:
#                     raise TagAlreadyExists(tag_name=new_name)
                
#                 update_dict["name"] = new_name
            
#             # Apply updates
#             for field, value in update_dict.items():
#                 setattr(tag, field, value)
            
#             await db.commit()
#             await db.refresh(tag)
            
#             # Invalidate caches
#             await invalidate_cache(f"tag:{tag_id}")
#             await invalidate_cache("tags:list:*")
            
#             self._logger.info(
#                 f"Tag updated: {tag_id}",
#                 extra={"updates": update_dict}
#             )
            
#             return tag
            
#         except (TagNotFound, TagAlreadyExists):
#             await db.rollback()
#             raise
#         except IntegrityError:
#             await db.rollback()
#             raise TagAlreadyExists(tag_name=tag_data.name)
#         except SQLAlchemyError as e:
#             await db.rollback()
#             self._logger.error(f"Database error updating tag: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to update tag")
    
#     async def delete(
#         self,
#         tag_id: int,
#         db: AsyncSession
#     ) -> bool:
#         """
#         Delete a tag.
        
#         Args:
#             tag_id: ID of tag to delete
#             db: Database session
            
#         Returns:
#             True if deleted successfully
            
#         Raises:
#             TagNotFound: If tag doesn't exist
#             DatabaseError: If database operation fails
#         """
#         try:
#             tag = await self.get_by_id(tag_id, db, load_relationships=False)
            
#             await db.delete(tag)
#             await db.commit()
            
#             # Invalidate caches
#             await invalidate_cache(f"tag:{tag_id}")
#             await invalidate_cache("tags:list:*")
            
#             self._logger.info(f"Tag deleted: {tag_id}")
#             return True
            
#         except TagNotFound:
#             raise
#         except SQLAlchemyError as e:
#             await db.rollback()
#             self._logger.error(f"Database error deleting tag: {e}", exc_info=True)
#             raise DatabaseError(detail="Failed to delete tag")
    
#     async def get_popular_tags(
#         self,
#         db: AsyncSession,
#         limit: int = 10
#     ) -> List[Dict[str, Any]]:
#         """
#         Get most popular tags by book count.
        
#         Args:
#             db: Database session
#             limit: Maximum number of tags to return
            
#         Returns:
#             List of dictionaries with tag info and book count
#         """
#         try:
#             from app.models.book_tag_model import BookTag
            
#             query = (
#                 select(
#                     Tag.id,
#                     Tag.name,
#                     func.count(BookTag.book_id).label("book_count")
#                 )
#                 .join(BookTag, Tag.id == BookTag.tag_id)
#                 .group_by(Tag.id, Tag.name)
#                 .order_by(col("book_count").desc())
#                 .limit(limit)
#             )
            
#             result = await db.execute(query)
            
#             return [
#                 {
#                     "id": row.id,
#                     "name": row.name,
#                     "book_count": row.book_count
#                 }
#                 for row in result
#             ]
            
#         except SQLAlchemyError as e:
#             self._logger.error(
#                 f"Database error getting popular tags: {e}",
#                 exc_info=True
#             )
#             raise DatabaseError(detail="Failed to get popular tags")


# # Create singleton instance
# tag_repository = TagRepository()


# # Legacy functions for backward compatibility
# async def get_tag_by_id(tag_id: int, db: AsyncSession) -> Optional[Tag]:
#     """Gets a single tag by its ID."""
#     try:
#         return await tag_repository.get_by_id(tag_id, db)
#     except TagNotFound:
#         return None


# async def get_tag_by_name(name: str, db: AsyncSession) -> Optional[Tag]:
#     """Gets a single tag by its unique name."""
#     return await tag_repository.get_by_name(name, db)


# async def get_all_tags(db: AsyncSession) -> List[Tag]:
#     """Gets a list of all tags."""
#     result = await tag_repository.get_all(db, limit=1000)
#     return result.items


# async def create_tag(tag_data: TagCreate, db: AsyncSession) -> Tag:
#     """Creates a new tag."""
#     return await tag_repository.create(tag_data, db)


# async def update_tag(
#     tag_id: int,
#     tag_data: TagUpdate,
#     db: AsyncSession
# ) -> Optional[Tag]:
#     """Updates an existing tag's name."""
#     try:
#         return await tag_repository.update(tag_id, tag_data, db)
#     except TagNotFound:
#         return None


# async def delete_tag(tag_id: int, db: AsyncSession) -> Optional[Tag]:
#     """Deletes a tag."""
#     try:
#         tag = await tag_repository.get_by_id(tag_id, db)
#         await tag_repository.delete(tag_id, db)
#         return tag
#     except TagNotFound:
#         return None


# __all__ = [
#     # Repository class
#     "TagRepository",
#     "tag_repository",
    
#     # Legacy functions
#     "get_tag_by_id",
#     "get_tag_by_name",
#     "get_all_tags",
#     "create_tag",
#     "update_tag",
#     "delete_tag",
# ]