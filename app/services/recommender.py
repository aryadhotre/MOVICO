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
        bypass_cache: bool = False,
        include_explanations: bool = True
    ) -> RecommendationResponse:
        """Retrieves and coordinates movie recommendation generation, caching, and audit logging."""
        start_time = time.time()
        
        # Imports needed for response schemas
        from app.database.schemas import RecommendedMovieResponse, RecommendationExplanation
        
        # 1. Attempt Cache Retrieval
        if not bypass_cache:
            cached_recs = self.cache_service.get_cached_recommendations(user_id)
            if cached_recs is not None:
                # Cache hit: slice to requested limit
                sliced_recs = cached_recs[:limit]
                execution_time = time.time() - start_time
                
                # Fetch movie details for response
                movie_objs = []
                rec_ids = []
                for item in sliced_recs:
                    movie = db.query(Movie).filter(Movie.id == int(item["movie_id"])).first()
                    if movie:
                        movie_objs.append(movie)
                        rec_ids.append(movie.id)
                
                # Generate explanations on-the-fly for the page returned if requested
                explanations = {}
                if include_explanations and rec_ids:
                    explanations = self.hybrid_model._generate_explanations(user_id, rec_ids, db)
                
                formatted_movies = []
                for movie in movie_objs:
                    schema_movie = RecommendedMovieResponse.from_orm(movie)
                    if movie.id in explanations:
                        schema_movie.explanation = explanations[movie.id]
                    formatted_movies.append(schema_movie)
                
                logger.info(f"Returning {len(formatted_movies)} cached recommendations for user {user_id}")
                return RecommendationResponse(
                    recommendation_type="cached_hybrid",
                    movies=formatted_movies,
                    generated_at=datetime.utcnow(),
                    execution_time_seconds=execution_time
                )

        # 2. Cache Miss: Execute Recommendation Models
        logger.info(f"Generating live recommendations for user {user_id}...")
        recs = self.hybrid_model.recommend(
            user_id, 
            top_n=limit * 2, 
            db=db, 
            include_explanations=include_explanations
        ) # Fetch double size for buffer
        
        # Slice to requested size
        sliced_recs = recs[:limit]
        rec_movie_ids = [item["movie_id"] for item in sliced_recs]
        
        # Determine recommendation strategy used
        rec_type = "hybrid"
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

        # 4. Format objects as RecommendedMovieResponse
        formatted_movies = []
        for item in sliced_recs:
            movie = db.query(Movie).filter(Movie.id == int(item["movie_id"])).first()
            if movie:
                schema_movie = RecommendedMovieResponse.from_orm(movie)
                if "explanation" in item and item["explanation"]:
                    schema_movie.explanation = item["explanation"]
                formatted_movies.append(schema_movie)

        # 5. Save to Cache in background
        cache_data = [{"movie_id": item["movie_id"]} for item in recs]
        self.cache_service.set_cached_recommendations(user_id, cache_data)

        execution_time = time.time() - start_time
        logger.info(f"Live recommendations computed for user {user_id} in {execution_time:.4f}s")
        
        return RecommendationResponse(
            recommendation_type=rec_type,
            movies=formatted_movies,
            generated_at=datetime.utcnow(),
            execution_time_seconds=execution_time
        )
