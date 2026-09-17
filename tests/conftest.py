import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Must be set before app.config.settings is imported anywhere.
os.environ["APP_ENV"] = "testing"
os.environ["USE_SQLITE"] = "true"
os.environ["DATA_DIR"] = "./test_data"
os.environ["MODELS_DIR"] = "./test_models_checkpoint"
os.environ["REDIS_ENABLED"] = "false"
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from app.api.auth_helper import get_password_hash  # noqa: E402
from app.database.connection import Base, get_db  # noqa: E402
from app.database.models import Movie, Rating, User, Watchlist  # noqa: E402
from app.main import app  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def test_directories():
    os.makedirs("./test_data", exist_ok=True)
    os.makedirs("./test_models_checkpoint", exist_ok=True)
    yield
    import shutil

    for path in ("./test_data", "./test_models_checkpoint"):
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)


def _movie(movie_id, title, genres, **overrides):
    """Builds a fully-populated movie row.

    Every fixture movie gets a poster because the catalogue endpoints exclude
    posterless titles by design, so a movie without one is invisible to browse.
    """
    defaults = dict(
        id=movie_id,
        title=title,
        genres=genres,
        poster_path=f"/poster{movie_id}.jpg",
        backdrop_path=f"/backdrop{movie_id}.jpg",
        tmdb_id=str(1000 + movie_id),
        overview=f"Synopsis for {title}.",
        release_year=int(title[-5:-1]),
        release_date=f"{title[-5:-1]}-06-01",
        vote_average=7.0,
        vote_count=1200,
        runtime=110,
        rating_count=5000,
        rating_mean=4.0,
        bayes_score=4.0,
        popularity_score=30.0,
        trending_score=20.0,
        original_language="en",
    )
    defaults.update(overrides)
    return Movie(**defaults)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    session.add(
        User(
            username="testuser",
            email="testuser@example.com",
            password_hash=get_password_hash("testpassword"),
        )
    )

    session.add_all(
        [
            _movie(1, "Toy Story (1995)", "Adventure|Animation|Children|Comedy|Fantasy",
                   director="John Lasseter", cast_list="Tom Hanks, Tim Allen",
                   user_tags="pixar animation classic", keywords="toys, friendship",
                   trailer_key="v-PjgYDrg70", bayes_score=4.2, popularity_score=40.0),
            _movie(2, "Jumanji (1995)", "Adventure|Children|Fantasy",
                   director="Joe Johnston", cast_list="Robin Williams, Kirsten Dunst",
                   bayes_score=3.6, popularity_score=32.0),
            _movie(3, "Grumpier Old Men (1995)", "Comedy|Romance",
                   bayes_score=3.1, popularity_score=20.0),
            _movie(4, "Waiting to Exhale (1995)", "Comedy|Drama|Romance",
                   bayes_score=2.9, popularity_score=15.0),
            _movie(5, "Father of the Bride Part II (1995)", "Comedy",
                   bayes_score=2.7, popularity_score=10.0),
            _movie(6, "Heat (1995)", "Action|Crime|Thriller",
                   director="Michael Mann", cast_list="Al Pacino, Robert De Niro",
                   bayes_score=4.1, popularity_score=35.0),
        ]
    )
    session.commit()

    session.add_all(
        [
            Rating(user_id=1, movie_id=1, rating=5.0),
            Rating(user_id=1, movie_id=2, rating=4.0),
            Rating(user_id=1, movie_id=3, rating=2.0),
        ]
    )
    session.add(Watchlist(user_id=1, movie_id=6))
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_client(client):
    """A client carrying a valid bearer token for ``testuser``."""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
