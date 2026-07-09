import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set env before importing settings
os.environ["APP_ENV"] = "testing"
os.environ["POSTGRES_DB"] = "test_movico_db"
os.environ["REDIS_HOST"] = "localhost"
os.environ["DATA_DIR"] = "./test_data"
os.environ["MODELS_DIR"] = "./test_models_checkpoint"
os.environ["USE_SQLITE"] = "true"

from app.main import app
from app.database.connection import Base, get_db
from app.database.models import Movie, Rating, User
from app.api.auth_helper import get_password_hash

# Use in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_directories():
    """Ensures test folders exist and cleans them up after session."""
    os.makedirs("./test_data", exist_ok=True)
    os.makedirs("./test_models_checkpoint", exist_ok=True)
    yield
    # Cleanup
    import shutil
    if os.path.exists("./test_data"):
        shutil.rmtree("./test_data")
    if os.path.exists("./test_models_checkpoint"):
        shutil.rmtree("./test_models_checkpoint")

@pytest.fixture(scope="function")
def db():
    """Provides a clean in-memory database session for each test case."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Pre-seed basic test data
    # 1. Create a test user
    test_user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash=get_password_hash("testpassword")
    )
    session.add(test_user)
    
    # 2. Add some test movies (with TMDB enrichment fields)
    test_movies = [
        Movie(
            id=1, title="Toy Story (1995)", 
            genres="Adventure|Animation|Children|Comedy|Fantasy", 
            popularity_score=4.5, trending_score=4.0, tmdb_id="862",
            poster_path="/uXDfjJbdP4ijSERjOH7ROa6o.jpg",
            overview="Woody, a traditional pull-string cowboy doll, is Andy's favorite toy.",
            director="John Lasseter", cast_list="Tom Hanks, Tim Allen, Don Rickles",
            release_date="1995-10-30", vote_average=7.9, runtime=81,
            user_tags="pixar animation classic fun childhood"
        ),
        Movie(
            id=2, title="Jumanji (1995)", 
            genres="Adventure|Children|Fantasy", 
            popularity_score=3.0, trending_score=2.8, tmdb_id="8844",
            poster_path="/vgpXmVaVyUL7GGiDeiK1mKEKb2X.jpg",
            overview="When siblings Judy and Peter discover an enchanted board game...",
            director="Joe Johnston", cast_list="Robin Williams, Kirsten Dunst",
            release_date="1995-12-15", vote_average=7.0, runtime=104
        ),
        Movie(
            id=3, title="Grumpier Old Men (1995)", 
            genres="Comedy|Romance", 
            popularity_score=2.0, trending_score=3.5, tmdb_id="15602"
        ),
        Movie(
            id=4, title="Waiting to Exhale (1995)", 
            genres="Comedy|Drama|Romance", 
            popularity_score=1.5, trending_score=1.2, tmdb_id="31357"
        ),
        Movie(
            id=5, title="Father of the Bride Part II (1995)", 
            genres="Comedy", 
            popularity_score=1.0, trending_score=0.9, tmdb_id="11862"
        ),
    ]
    session.add_all(test_movies)
    session.commit()
    
    # 3. Add some ratings
    test_ratings = [
        Rating(user_id=1, movie_id=1, rating=5.0),
        Rating(user_id=1, movie_id=2, rating=4.0),
        Rating(user_id=1, movie_id=3, rating=2.0),
    ]
    session.add_all(test_ratings)
    session.commit()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    """Provides a FastAPI test client configured with database overrides."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
