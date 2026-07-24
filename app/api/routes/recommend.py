from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.schemas import RecommendationResponse
from app.api.auth_helper import get_current_user
from app.database.models import User
from app.services.recommender import RecommenderCoordinator

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
coordinator = RecommenderCoordinator()

@router.get("", response_model=RecommendationResponse)
@router.get("/", response_model=RecommendationResponse)
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations to fetch"),
    bypass_cache: bool = Query(False, description="Bypass Redis cache and recalculate recommendations"),
    include_explanations: bool = Query(True, description="Include explanations ('Because you watched X') in recommendations"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves personalized movie recommendations for the authenticated user using the hybrid model."""
    try:
        response = await coordinator.get_recommendations(
            user_id=current_user.id,
            limit=limit,
            db=db,
            bypass_cache=bypass_cache,
            include_explanations=include_explanations
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}"
        )
