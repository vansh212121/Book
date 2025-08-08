
    # # --- READ Operations ---


    # @cache_key_wrapper("book:detail:{book_id}", expire=1800)
    # async def get_book_by_id(
    #     self, book_id: int, db: AsyncSession, include_reviews: bool = False
    # ) -> BookResponseDetailed:
    #     """
    #     Get detailed book information by ID.

    #     Args:
    #         book_id: Book ID
    #         db: Database session
    #         include_reviews: Whether to include reviews

    #     Returns:
    #         Detailed book information

    #     Raises:
    #         BookNotFound: If book doesn't exist
    #     """
    #     book = await self.book_repository.get_by_id(
    #         book_id=book_id, db=db, load_relationships=True
    #     )

    #     # Calculate average rating if reviews are included
    #     average_rating = None
    #     review_count = 0

    #     if include_reviews and book.reviews:
    #         review_count = len(book.reviews)
    #         if review_count > 0:
    #             total_rating = sum(review.rating for review in book.reviews)
    #             average_rating = round(total_rating / review_count, 2)

    #     # Convert to detailed response
    #     return BookResponseDetailed(
    #         **book.model_dump(),
    #         average_rating=average_rating,
    #         review_count=review_count,
    #     )
