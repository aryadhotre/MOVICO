import pytest
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data

def test_auth_flow(client: TestClient):
    # 1. Register new user
    reg_response = client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "secretpassword"
        }
    )
    assert reg_response.status_code == 201
    reg_data = reg_response.json()
    assert reg_data["username"] == "newuser"
    assert "id" in reg_data
    
    # 2. Login
    login_response = client.post(
        "/api/auth/login",
        data={
            "username": "newuser",
            "password": "secretpassword"
        }
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    
    # 3. Get profile (me) using token
    token = login_data["access_token"]
    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["username"] == "newuser"

def test_search_movies(client: TestClient):
    response = client.get("/api/movies/search?q=Toy")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert "Toy Story" in results[0]["title"]

def test_search_movies_returns_enriched_fields(client: TestClient):
    """Verifies that movie search results include TMDB enrichment metadata."""
    response = client.get("/api/movies/search?q=Toy")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    
    movie = results[0]
    # Check enriched fields are present (they may be null for some movies)
    assert "poster_path" in movie
    assert "overview" in movie
    assert "director" in movie
    assert "cast_list" in movie
    assert "poster_url" in movie
    assert "backdrop_url" in movie
    
    # For Toy Story specifically, we seeded enrichment data
    assert movie["poster_path"] is not None
    assert movie["overview"] is not None
    assert movie["director"] == "John Lasseter"
    assert "Tom Hanks" in movie["cast_list"]
    assert movie["poster_url"].startswith("https://image.tmdb.org")

def test_submit_rating(client: TestClient):
    # Get auth token first
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    token = login_response.json()["access_token"]
    
    # Submit rating for movie 4
    response = client.post(
        "/api/ratings/",
        json={"movie_id": 4, "rating": 4.5},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["movie_id"] == 4
    assert data["rating"] == 4.5
    assert "id" in data
    
    # Get rating history
    hist_response = client.get(
        "/api/ratings/history",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert hist_response.status_code == 200
    history = hist_response.json()
    # User had 3 original ratings + 1 new rating
    assert len(history) == 4
    assert any(item["movie_id"] == 4 for item in history)

def test_database_stats(client: TestClient):
    """Tests the /api/system/stats endpoint."""
    response = client.get("/api/system/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_movies" in data
    assert "total_ratings" in data
    assert "tmdb_enriched_movies" in data
    assert "tmdb_pending_movies" in data
    assert data["total_movies"] == 5
    assert data["total_ratings"] == 3
