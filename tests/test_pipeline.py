import pytest
from app.pipeline.preprocess import MoviePreprocessor
from app.database.models import Movie, Rating

def test_title_cleaning():
    preprocessor = MoviePreprocessor()
    assert preprocessor.clean_title("Toy Story (1995)") == "toy story"
    assert preprocessor.clean_title("Heat (1995)") == "heat"
    assert preprocessor.clean_title("Grumpier Old Men (1995) ") == "grumpier old men"
    assert preprocessor.clean_title("Spider-Man 2 (2004)") == "spiderman 2"

def test_build_content_features(db):
    preprocessor = MoviePreprocessor()
    tfidf_matrix, movie_to_idx = preprocessor.build_content_features(db)
    
    assert tfidf_matrix is not None
    assert tfidf_matrix.shape[0] == 5 # 5 seeded movies in db
    assert len(movie_to_idx) == 5
    assert 1 in movie_to_idx
    assert 2 in movie_to_idx

def test_build_rating_matrix(db):
    preprocessor = MoviePreprocessor()
    csr_data, user_to_idx, movie_to_idx = preprocessor.build_rating_matrix(db)
    
    assert csr_data is not None
    assert csr_data.shape[0] == 1 # 1 user
    assert csr_data.shape[1] == 3 # 3 unique movies rated
    assert csr_data.nnz == 3 # 3 ratings in total
    assert user_to_idx[1] == 0
    assert csr_data[0, movie_to_idx[1]] == 5.0
