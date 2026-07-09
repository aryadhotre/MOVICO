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

def test_search_movies_paginated(client: TestClient):
    """Verifies that movie search returns paginated results with metadata."""
    response = client.get("/api/movies/search?q=Toy&page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    
    # Check paginated structure
    assert "items" in data
    assert "pagination" in data
    
    # Check pagination metadata
    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 10
    assert "total_items" in pagination
    assert "total_pages" in pagination
    assert "has_next" in pagination
    assert "has_previous" in pagination
    assert pagination["has_previous"] is False  # First page
    
    # Check actual results
    assert len(data["items"]) > 0
    assert "Toy Story" in data["items"][0]["title"]

def test_search_movies_returns_enriched_fields(client: TestClient):
    """Verifies that movie search results include TMDB enrichment metadata."""
    response = client.get("/api/movies/search?q=Toy&page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    
    movie = data["items"][0]
    # Check enriched fields are present
    assert "poster_path" in movie
    assert "overview" in movie
    assert "director" in movie
    assert "cast_list" in movie
    assert "poster_url" in movie
    assert "backdrop_url" in movie
    assert "user_tags" in movie
    
    # For Toy Story specifically, we seeded enrichment data
    assert movie["poster_path"] is not None
    assert movie["overview"] is not None
    assert movie["director"] == "John Lasseter"
    assert "Tom Hanks" in movie["cast_list"]
    assert movie["poster_url"].startswith("https://image.tmdb.org")
    assert "pixar" in movie["user_tags"]

def test_browse_movies_paginated(client: TestClient):
    """Verifies that movie browsing returns paginated results sorted by popularity."""
    response = client.get("/api/movies/browse?page=1&page_size=2&sort_by=popularity&order=desc")
    assert response.status_code == 200
    data = response.json()
    
    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 2  # Requested 2 per page
    assert data["pagination"]["total_items"] == 5  # 5 test movies total
    assert data["pagination"]["total_pages"] == 3  # ceil(5/2) = 3
    assert data["pagination"]["has_next"] is True
    
    # Verify sorting by popularity descending
    assert data["items"][0]["popularity_score"] >= data["items"][1]["popularity_score"]

def test_browse_movies_page_2(client: TestClient):
    """Verifies pagination on page 2."""
    response = client.get("/api/movies/browse?page=2&page_size=2&sort_by=popularity&order=desc")
    assert response.status_code == 200
    data = response.json()
    
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["has_previous"] is True
    assert data["pagination"]["has_next"] is True  # Page 3 exists (5 items / 2 per page = 3 pages)
    assert len(data["items"]) == 2

def test_browse_movies_last_page(client: TestClient):
    """Verifies last page has correct has_next=False."""
    response = client.get("/api/movies/browse?page=3&page_size=2&sort_by=popularity&order=desc")
    assert response.status_code == 200
    data = response.json()
    
    assert data["pagination"]["page"] == 3
    assert data["pagination"]["has_next"] is False
    assert len(data["items"]) == 1  # Only 1 remaining item on last page

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
    
    # Get paginated rating history
    hist_response = client.get(
        "/api/ratings/history?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert hist_response.status_code == 200
    history = hist_response.json()
    
    # Check paginated structure
    assert "items" in history
    assert "pagination" in history
    assert history["pagination"]["total_items"] == 4  # 3 original + 1 new
    assert any(item["movie_id"] == 4 for item in history["items"])

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


# ========== Genre Filtering Tests ==========

def test_get_genres(client: TestClient):
    """Verifies the genre catalog endpoint returns all unique genres with counts."""
    response = client.get("/api/movies/genres")
    assert response.status_code == 200
    data = response.json()
    
    assert "genres" in data
    assert "total_genres" in data
    assert data["total_genres"] > 0
    
    # Each genre should have name and movie_count
    for genre in data["genres"]:
        assert "name" in genre
        assert "movie_count" in genre
        assert genre["movie_count"] > 0
    
    # Check known genres from our test fixtures exist
    genre_names = [g["name"] for g in data["genres"]]
    assert "Comedy" in genre_names
    assert "Adventure" in genre_names
    assert "Fantasy" in genre_names

def test_browse_with_single_genre_filter(client: TestClient):
    """Verifies browse endpoint filters correctly by a single genre."""
    # Filter by Comedy — test movies 1,3,4,5 have Comedy
    response = client.get("/api/movies/browse?page=1&page_size=20&genre=Comedy")
    assert response.status_code == 200
    data = response.json()
    
    # All returned movies should contain "Comedy" in their genres
    for movie in data["items"]:
        assert "Comedy" in movie["genres"], f"Movie '{movie['title']}' does not have Comedy genre"
    
    # We have 4 movies with Comedy in test data
    assert data["pagination"]["total_items"] == 4

def test_browse_with_multi_genre_filter(client: TestClient):
    """Verifies multi-genre AND filter returns only movies matching ALL specified genres."""
    # Filter by Adventure AND Fantasy — only Toy Story and Jumanji match both
    response = client.get("/api/movies/browse?page=1&page_size=20&genres=Adventure,Fantasy")
    assert response.status_code == 200
    data = response.json()
    
    assert data["pagination"]["total_items"] == 2
    for movie in data["items"]:
        assert "Adventure" in movie["genres"]
        assert "Fantasy" in movie["genres"]

def test_search_with_genre_filter(client: TestClient):
    """Verifies search + genre filter combination works correctly."""
    # Search for movies with "(1995)" in title, filtered to Adventure genre
    response = client.get("/api/movies/search?q=1995&genre=Adventure&page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    
    # Only Toy Story and Jumanji have Adventure genre
    for movie in data["items"]:
        assert "Adventure" in movie["genres"]
        assert "1995" in movie["title"]

def test_browse_genre_no_results(client: TestClient):
    """Verifies graceful handling when genre filter matches zero movies."""
    response = client.get("/api/movies/browse?page=1&page_size=20&genre=Western")
    assert response.status_code == 200
    data = response.json()
    
    assert data["pagination"]["total_items"] == 0
    assert len(data["items"]) == 0
    assert data["pagination"]["total_pages"] == 1
    assert data["pagination"]["has_next"] is False

def test_browse_with_year_filter(client: TestClient):
    """Verifies year filter works on the title-embedded year."""
    response = client.get("/api/movies/browse?page=1&page_size=20&year=1995")
    assert response.status_code == 200
    data = response.json()
    
    # All 5 test movies are from 1995
    assert data["pagination"]["total_items"] == 5
    for movie in data["items"]:
        assert "(1995)" in movie["title"]
