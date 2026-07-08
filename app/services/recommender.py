import time
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models import RecommendationHistory, Movie
from app.database.schemas import RecommendationResponse, MovieResponse
from app.models.hybrid import HybridRecommender
from app.services.cache import RedisCacheService

logger = logging.getLogger(__name__)

class RecommenderCoordinator:
    def __init__(self):
        self.hybrid_model = HybridRecommender()
        self.cache_service = RedisCacheService()

    async def get_recommendations(
        self, 
        user_id: int, 
        limit: int, 
        db: Session, 
        bypass_cache: bool = False
    ) -> RecommendationResponse:
        """Retrieves and coordinates movie recommendation generation, caching, and audit logging."""
        start_time = time.time()
        
        # 1. Attempt Cache Retrieval
        if not bypass_cache:
            cached_recs = self.cache_service.get_cached_recommendations(user_id)
            if cached_recs is not None:
                # Cache hit: slice to requested limit
                sliced_recs = cached_recs[:limit]
                execution_time = time.time() - start_time
                
                # Fetch movie details for response (in case cache only stored raw structures)
                # Ensure we format items as MovieResponse schemas
                movie_objs = []
                for item in sliced_recs:
                    movie = db.query(Movie).filter(Movie.id == item["movie_id"]).first()
                    if movie:
                        movie_objs.append(MovieResponse.from_orm(movie))
                
                logger.info(f"Returning {len(movie_objs)} cached recommendations for user {user_id}")
                return RecommendationResponse(
                    recommendation_type="cached_hybrid",
                    movies=movie_objs,
                    generated_at=datetime.utcnow(),
                    execution_time_seconds=execution_time
                )

        # 2. Cache Miss: Execute Recommendation Models
        logger.info(f"Generating live recommendations for user {user_id}...")
        recs = self.hybrid_model.recommend(user_id, top_n=limit * 2, db=db) # Fetch double size for buffer
        
        # Slice to requested size
        sliced_recs = recs[:limit]
        rec_movie_ids = [item["movie_id"] for item in sliced_recs]
        
        # Determine recommendation strategy used
        rec_type = "hybrid"
        # If fallback happened, model logs would indicate. Check if results have content weights.
        if sliced_recs and "metadata" not in sliced_recs[0]:
            rec_type = "popularity_cold_start"

        # 3. Create Audit Trail Entry in DB
        try:
            history_entry = RecommendationHistory(
                user_id=user_id,
                recommendation_type=rec_type,
                movie_ids=rec_movie_ids
            )
            db.add(history_entry)
            db.commit()
            logger.info(f"Audit log created: recommendation history saved for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to write recommendation audit log to database: {str(e)}")
            db.rollback()

        # 4. Format objects as MovieResponse
        movie_objs = []
        for item in sliced_recs:
            movie = db.query(Movie).filter(Movie.id == item["movie_id"]).first()
            if movie:
                movie_objs.append(MovieResponse.from_orm(movie))

        # 5. Save to Cache in background
        # Save complete prediction set (up to limit * 2) so subsequent smaller requests can hit cache
        cache_data = [{"movie_id": item["movie_id"]} for item in recs]
        self.cache_service.set_cached_recommendations(user_id, cache_data)

        execution_time = time.time() - start_time
        logger.info(f"Live recommendations computed for user {user_id} in {execution_time:.4f}s")
        
        return RecommendationResponse(
            recommendation_type=rec_type,
            movies=movie_objs,
            generated_at=datetime.utcnow(),
            execution_time_seconds=execution_time
        )
