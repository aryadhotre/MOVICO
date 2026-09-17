"""Personalised recommendation endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_helper import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.database.schemas import RecommendationResponse
from app.services.recommender import recommender

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=RecommendationResponse)
@router.get("/", response_model=RecommendationResponse, include_in_schema=False)
async def get_recommendations(
    limit: int = Query(20, ge=1, le=60),
    diversity: float = Query(
        1.0, ge=0.0, le=1.0,
        description="0 ranks purely by relevance; 1 applies full MMR diversification",
    ),
    novelty: float = Query(
        0.0, ge=0.0, le=1.0,
        description="Shifts weight from popular titles toward the long tail",
    ),
    genres: Optional[str] = Query(None, description="Comma-separated genre filter"),
    min_year: Optional[int] = Query(None, ge=1874, le=2100),
    explain: bool = Query(True, description="Include per-item attribution"),
    bypass_cache: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ranks the catalogue for the authenticated user.

    ``diversity`` and ``novelty`` are exposed rather than fixed because the right
    balance is a matter of taste, not a single correct value -- the UI surfaces them
    as controls so the user can steer their own feed.
    """
    genre_list = [part.strip() for part in genres.split(",") if part.strip()] if genres else None
    try:
        return await recommender.recommend(
            db=db,
            user_id=current_user.id,
            limit=limit,
            diversity=diversity,
            novelty=novelty,
            genres=genre_list,
            min_year=min_year,
            bypass_cache=bypass_cache,
            explain=explain,
        )
    except RuntimeError as exc:
        # The engine has no trained artifacts on disk yet.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
