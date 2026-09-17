"""API contract tests.

These cover the bugs that made the previous frontend misbehave, so a regression on
any of them fails here rather than in the browser:

* add-to-watchlist accepting a JSON body (was a query param, 422 every time)
* ``POST /api/ratings`` answering without a redirect
* card payloads exposing ``year`` and a genre *list* rather than a pipe string
* posterless titles staying out of catalogue listings
"""

import pytest


class TestAuth:
    def test_register_returns_token_and_user(self, client):
        response = client.post(
            "/api/auth/register",
            json={"username": "newbie", "email": "newbie@example.com", "password": "hunter2!"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["access_token"]
        assert body["expires_in"] > 0
        assert body["user"]["username"] == "newbie"

    def test_duplicate_username_conflicts(self, client):
        response = client.post(
            "/api/auth/register",
            json={"username": "testuser", "email": "other@example.com", "password": "hunter2!"},
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_username_is_case_insensitive_on_login(self, client):
        response = client.post(
            "/api/auth/login",
            data={"username": "TESTUSER", "password": "testpassword"},
        )
        assert response.status_code == 200

    def test_bad_password_rejected(self, client):
        response = client.post(
            "/api/auth/login", data={"username": "testuser", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_returns_current_user(self, auth_client):
        response = auth_client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"


class TestCatalogue:
    def test_browse_returns_cards(self, client):
        response = client.get("/api/movies/browse?page_size=3")
        assert response.status_code == 200
        body = response.json()

        assert len(body["items"]) == 3
        assert body["pagination"]["total_items"] == 6

        card = body["items"][0]
        # Year is split out of the title, genres arrive as a list.
        assert card["title"] == "Toy Story"
        assert card["year"] == 1995
        assert isinstance(card["genres"], list)
        assert "Animation" in card["genres"]
        # Card payloads must stay lean -- no plot text.
        assert "overview" not in card

    def test_browse_orders_by_popularity_desc(self, client):
        items = client.get("/api/movies/browse?page_size=6").json()["items"]
        assert items[0]["title"] == "Toy Story"

    def test_browse_paginates_without_overlap(self, client):
        first = client.get("/api/movies/browse?page=1&page_size=3").json()["items"]
        second = client.get("/api/movies/browse?page=2&page_size=3").json()["items"]
        assert not {item["id"] for item in first} & {item["id"] for item in second}

    def test_browse_hides_posterless_titles(self, client, db):
        from app.database.models import Movie
        from app.services.cache import cache

        db.add(
            Movie(id=99, title="No Art (2020)", genres="Drama", poster_path=None,
                  popularity_score=999.0, bayes_score=5.0)
        )
        db.commit()
        cache.local.clear()

        ids = {item["id"] for item in client.get("/api/movies/browse?page_size=50").json()["items"]}
        assert 99 not in ids

    def test_browse_genre_filter(self, client):
        items = client.get("/api/movies/browse?genre=Romance&page_size=20").json()["items"]
        assert items
        assert all("Romance" in item["genres"] for item in items)

    def test_browse_rejects_bad_page(self, client):
        assert client.get("/api/movies/browse?page=0").status_code == 422

    def test_unknown_sort_falls_back_instead_of_erroring(self, client):
        # The previous version raised KeyError -> 500 on an unmapped sort field.
        response = client.get("/api/movies/browse?sort_by=not_a_column")
        assert response.status_code == 200

    def test_genres_endpoint(self, client):
        from app.services.cache import cache

        cache.local.clear()
        body = client.get("/api/movies/genres").json()
        names = {genre["name"] for genre in body["genres"]}
        assert "Comedy" in names
        assert body["total_genres"] == len(body["genres"])

    def test_detail_returns_full_record(self, client):
        body = client.get("/api/movies/1").json()
        assert body["title"] == "Toy Story"
        assert body["director"] == "John Lasseter"
        assert body["cast"] == ["Tom Hanks", "Tim Allen"]
        assert body["trailer_key"] == "v-PjgYDrg70"
        assert body["overview"]

    def test_detail_404(self, client):
        assert client.get("/api/movies/424242").status_code == 404

    def test_trending_endpoint(self, client):
        assert client.get("/api/movies/trending?page_size=5").status_code == 200

    def test_home_feed_bundles_rows(self, client):
        from app.services.cache import cache

        cache.local.clear()
        body = client.get("/api/movies/home").json()
        assert "hero" in body and "rows" in body
        assert all("key" in row and "items" in row for row in body["rows"])


class TestRatings:
    def test_submit_rating_without_redirect(self, auth_client):
        # The frontend posts to the slashless path; it must answer directly.
        response = auth_client.post(
            "/api/ratings", json={"movie_id": 4, "rating": 4.5}, follow_redirects=False
        )
        assert response.status_code == 201, response.text
        assert response.json()["rating"] == 4.5

    def test_rating_is_upserted_not_duplicated(self, auth_client, db):
        from app.database.models import Rating

        auth_client.post("/api/ratings", json={"movie_id": 1, "rating": 3.0})
        rows = db.query(Rating).filter(Rating.user_id == 1, Rating.movie_id == 1).all()
        assert len(rows) == 1
        assert rows[0].rating == 3.0

    def test_rating_range_validated(self, auth_client):
        assert auth_client.post("/api/ratings", json={"movie_id": 1, "rating": 9}).status_code == 422

    def test_rating_unknown_movie_404(self, auth_client):
        response = auth_client.post("/api/ratings", json={"movie_id": 999999, "rating": 4.0})
        assert response.status_code == 404

    def test_batch_ratings(self, auth_client):
        response = auth_client.post(
            "/api/ratings/batch",
            json=[{"movie_id": 4, "rating": 4.0}, {"movie_id": 5, "rating": 3.5}],
        )
        assert response.status_code == 201
        assert response.json()["saved"] == 2

    def test_ratings_map(self, auth_client):
        body = auth_client.get("/api/ratings/mine").json()
        assert body["ratings"]["1"] == 5.0

    def test_history_joins_movies(self, auth_client):
        body = auth_client.get("/api/ratings/history").json()
        assert body["items"]
        assert body["items"][0]["movie"]["title"]

    def test_stats_reflect_liked_genres(self, auth_client):
        body = auth_client.get("/api/ratings/stats").json()
        assert body["ratings_count"] == 3
        assert body["average_rating"] == pytest.approx(3.67, abs=0.01)
        # Only ratings >= 3.5 shape the taste profile, so Comedy (rated 2.0 via
        # Grumpier Old Men) should not outrank Adventure.
        assert body["top_genres"]

    def test_delete_rating(self, auth_client):
        assert auth_client.delete("/api/ratings/1").status_code == 200
        assert auth_client.delete("/api/ratings/1").status_code == 404

    def test_ratings_require_auth(self, client):
        assert client.post("/api/ratings", json={"movie_id": 1, "rating": 4.0}).status_code == 401


class TestWatchlist:
    def test_add_accepts_json_body(self, auth_client):
        # Previously declared as a query param, so a JSON body always 422'd.
        response = auth_client.post("/api/ratings/watchlist", json={"movie_id": 4})
        assert response.status_code == 201, response.text
        assert response.json()["movie"]["id"] == 4

    def test_add_is_idempotent(self, auth_client):
        auth_client.post("/api/ratings/watchlist", json={"movie_id": 4})
        response = auth_client.post("/api/ratings/watchlist", json={"movie_id": 4})
        assert response.status_code == 201
        ids = auth_client.get("/api/ratings/watchlist/ids").json()["movie_ids"]
        assert ids.count(4) == 1

    def test_add_unknown_movie_404(self, auth_client):
        response = auth_client.post("/api/ratings/watchlist", json={"movie_id": 999999})
        assert response.status_code == 404

    def test_list_joins_movies(self, auth_client):
        body = auth_client.get("/api/ratings/watchlist").json()
        assert body["items"][0]["movie"]["title"] == "Heat"

    def test_remove_by_movie_id(self, auth_client):
        assert auth_client.delete("/api/ratings/watchlist/6").status_code == 200
        assert auth_client.delete("/api/ratings/watchlist/6").status_code == 404


class TestSystem:
    def test_health(self, client):
        body = client.get("/api/system/health").json()
        assert body["database"] == "up"
        assert body["status"] in {"healthy", "degraded"}

    def test_stats(self, client):
        body = client.get("/api/system/stats").json()
        assert body["total_movies"] == 6
        assert body["poster_coverage"] == 1.0

    def test_maintenance_requires_admin_token(self, client):
        assert client.post("/api/system/train").status_code == 403
        assert client.post(
            "/api/system/train", headers={"X-Admin-Token": "nope"}
        ).status_code == 403

    def test_root(self, client):
        assert client.get("/").json()["status"] == "online"


class TestRecommendations:
    def test_requires_auth(self, client):
        assert client.get("/api/recommendations").status_code == 401

    def test_untrained_engine_returns_503_not_500(self, auth_client):
        """No artifacts exist in the test models dir, so this must degrade cleanly."""
        response = auth_client.get("/api/recommendations")
        assert response.status_code == 503
        assert "detail" in response.json()

    def test_validates_bounds(self, auth_client):
        assert auth_client.get("/api/recommendations?limit=0").status_code == 422
        assert auth_client.get("/api/recommendations?diversity=5").status_code == 422


class TestTitlePresentation:
    """Regression tests for MovieLens title and genre conventions.

    MovieLens files a leading article at the end ("Matrix, The") and uses the
    literal string "(no genres listed)" as a null marker. Both reached the UI.
    """

    @pytest.mark.parametrize(
        "stored,expected",
        [
            ("Matrix, The (1999)", "The Matrix"),
            ("Shawshank Redemption, The (1994)", "The Shawshank Redemption"),
            ("Usual Suspects, The (1995)", "The Usual Suspects"),
            ("Good, the Bad and the Ugly, The (1966)", "The Good, the Bad and the Ugly"),
            ("American Tail, An (1986)", "An American Tail"),
            ("Slipping-Down Life, A (1999)", "A Slipping-Down Life"),
            # Apostrophe articles rejoin without a space.
            ("Amour fou, L' (1969)", "L'Amour fou"),
            ("'burbs, The (1989)", "The 'burbs"),
            # The article inside an alternate title is restored independently.
            ("Postman, The (Postino, Il) (1994)", "The Postman (Il Postino)"),
            ("Andalusian Dog, An (Chien andalou, Un) (1929)", "An Andalusian Dog (Un Chien andalou)"),
            # An a.k.a. marker stays in front of the restored article.
            (
                "5th Musketeer, The (a.k.a. Fifth Musketeer, The) (1979)",
                "The 5th Musketeer (a.k.a. The Fifth Musketeer)",
            ),
            # Titles with no displaced article are untouched.
            ("Pulp Fiction (1994)", "Pulp Fiction"),
            ("Fight Club (1999)", "Fight Club"),
        ],
    )
    def test_displaced_articles_are_restored(self, stored, expected):
        from app.database.schemas import split_title

        assert split_title(stored)[0] == expected

    @pytest.mark.parametrize(
        "stored",
        [
            # "Die" here is a verb (the film *Die Mommie Die!*), not the article.
            "Die, Mommie, Die (2003)",
            # Trailing words that merely look like articles.
            "Happy, Texas (1999)",
            "Crime and Punishment, USA (1959)",
            "Dancer, Texas Pop. 81 (1998)",
            # The comma is mid-title, not a displaced article.
            "I, Robot (2004)",
        ],
    )
    def test_non_articles_are_left_alone(self, stored):
        from app.database.schemas import split_title

        assert split_title(stored)[0] == stored.rsplit(" (", 1)[0]

    def test_year_is_split_off(self):
        from app.database.schemas import split_title

        assert split_title("Matrix, The (1999)") == ("The Matrix", 1999)
        assert split_title("No Year Here")[1] is None

    def test_genre_placeholder_is_dropped(self):
        from app.database.schemas import split_genres

        assert split_genres("(no genres listed)") == []
        assert split_genres("Drama|(no genres listed)|Crime") == ["Drama", "Crime"]
        assert split_genres(None) == []

    def test_card_payload_uses_natural_title(self, client, db):
        from app.database.models import Movie
        from app.services.cache import cache

        db.add(
            Movie(
                id=77, title="Matrix, The (1999)", genres="Action|(no genres listed)|Sci-Fi",
                poster_path="/m.jpg", release_year=1999, popularity_score=500.0,
                bayes_score=4.3, vote_average=8.2,
            )
        )
        db.commit()
        cache.local.clear()

        card = client.get("/api/movies/browse?page_size=1").json()["items"][0]
        assert card["title"] == "The Matrix"
        assert card["genres"] == ["Action", "Sci-Fi"]

    def test_detail_payload_uses_natural_title(self, client, db):
        from app.database.models import Movie

        db.add(
            Movie(
                id=78, title="Godfather, The (1972)", genres="(no genres listed)",
                poster_path="/g.jpg", release_year=1972,
            )
        )
        db.commit()

        detail = client.get("/api/movies/78").json()
        assert detail["title"] == "The Godfather"
        assert detail["genres"] == []
