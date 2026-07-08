import pytest
import numpy as np
import pickle
import os
from scipy.sparse import csr_matrix
from app.models.popularity import PopularityRecommender
from app.models.content_based import ContentBasedRecommender
from app.models.collaborative import CollaborativeRecommender
from app.models.hybrid import HybridRecommender
from app.pipeline.preprocess import MoviePreprocessor

def test_popularity_recommender(db):
    recommender = PopularityRecommender()
    # User 1 has watched movie 1, 2, 3
    # Top available movies are 4, 5
    recs = recommender.recommend(user_id=1, top_n=2, db=db)
    
    assert len(recs) <= 2
    if recs:
        # Recommendations should not include watched movies
        rec_ids = {r["movie_id"] for r in recs}
        assert 1 not in rec_ids
        assert 2 not in rec_ids
        assert 3 not in rec_ids
        # Recommendations should be movies 4 or 5
        assert rec_ids.issubset({4, 5})

def test_content_based_recommender(db):
    preprocessor = MoviePreprocessor()
    tfidf_matrix, movie_to_idx = preprocessor.build_content_features(db)
    
    # Reload files to fit Content model
    with open("./test_models_checkpoint/movie_mappings.pkl", "rb") as f:
        movie_mappings = pickle.load(f)
    with open("./test_models_checkpoint/vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)
        
    recommender = ContentBasedRecommender()
    recommender.fit(tfidf_matrix, movie_mappings, vectorizer)
    
    # Test movie similarity (similar to movie 1 'Toy Story')
    similar_movies = recommender.recommend_similar_movies(movie_id=1, top_n=2, db=db)
    assert len(similar_movies) > 0
    assert similar_movies[0]["movie_id"] != 1 # Target should be excluded
    
    # Test user recommendation
    recs = recommender.recommend(user_id=1, top_n=2, db=db)
    assert len(recs) <= 2

def test_collaborative_recommender(db):
    preprocessor = MoviePreprocessor()
    csr_data, user_to_idx, movie_to_idx = preprocessor.build_rating_matrix(db)
    
    mappings = {
        "user_to_idx": user_to_idx,
        "idx_to_user": {v: k for k, v in user_to_idx.items()},
        "movie_to_idx": movie_to_idx,
        "idx_to_movie": {v: k for k, v in movie_to_idx.items()}
    }
    
    recommender = CollaborativeRecommender(epochs=5, k_components=2)
    recommender.fit(csr_data, mappings)
    
    # Predict rating for user 1, movie 3 (already rated)
    pred_rating = recommender.predict_rating(user_id=1, movie_id=3)
    assert 0.5 <= pred_rating <= 5.0
    
    # Predict rating for user 1, movie 4 (unrated, but in catalog)
    pred_rating_unrated = recommender.predict_rating(user_id=1, movie_id=4)
    assert 0.5 <= pred_rating_unrated <= 5.0

def test_hybrid_recommender_cold_start_fallback(db):
    recommender = HybridRecommender(cold_start_threshold=5)
    # User 1 has 3 ratings which is < threshold (5). It should trigger popularity model.
    recs = recommender.recommend(user_id=1, top_n=2, db=db)
    
    # Check that recommendations are returned successfully
    assert len(recs) > 0
    # Ensure they don't contain watched movies (1, 2, 3)
    rec_ids = {r["movie_id"] for r in recs}
    assert 1 not in rec_ids
    assert 2 not in rec_ids
    assert 3 not in rec_ids
