"""API response models.

Two deliberate choices here, both about payload weight:

**Split card and detail shapes.** The old ``MovieResponse`` was used for both grids
and detail pages, so a 40-card page shipped 40 plot summaries, 40 cast lists and 40
tag blobs -- tens of kilobytes of text that nothing rendered. ``MovieCard`` carries
only what a poster tile draws; ``MovieDetail`` adds the rest.

**Image paths, not image URLs.** The server returns the bare TMDB path and the
client composes the size it actually needs. Returning five pre-built URLs per movie
would trade the text bloat for URL bloat, and hard-coding ``w500`` for every
context is what made small cards download poster art four times larger than the
space they occupy.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

T = TypeVar("T")

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
_YEAR_SUFFIX = re.compile(r"\s*\((\d{4})\)\s*$")

# MovieLens stores a leading article at the *end* of the title: "The Matrix" is
# filed as "Matrix, The". 3,860 titles in the catalogue use the convention, across
# six languages, and rendering them raw is what produced "Matrix, The" on screen.
#
# The list is deliberately restricted to articles actually observed as suffixes in
# this catalogue. A permissive pattern also matches ", USA", ", Texas" and ", Mom",
# which are ordinary words rather than displaced articles.
TITLE_ARTICLES = (
    "The", "A", "An",                          # English
    "L'", "Le", "La", "Les", "Un", "Une",      # French
    "Der", "Die", "Das",                       # German
    "El", "Los", "Las", "Una",                 # Spanish
    "Il", "Lo", "Gli", "I",                    # Italian
    "De", "Het",                               # Dutch
    "En", "Ett", "Den", "Det",                 # Scandinavian
    "Os",                                      # Portuguese
)

_ARTICLE_SUFFIX = re.compile(
    r"^(?P<stem>.+?),\s+(?P<article>" + "|".join(re.escape(a) for a in TITLE_ARTICLES) + r")$"
)

# One trailing "(...)" group — alternate or original-language titles, and a.k.a.
# forms, which carry the same displaced article inside the brackets.
_PARENTHETICAL = re.compile(r"\s*\(([^()]*)\)\s*$")

GENRE_PLACEHOLDER = "(no genres listed)"

# Alternate-title markers that must stay in front of the restored article:
# "(a.k.a. Fifth Musketeer, The)" becomes "(a.k.a. The Fifth Musketeer)", not
# "(The a.k.a. Fifth Musketeer)".
_ALT_TITLE_PREFIX = re.compile(r"^(a\.k\.a\.\s+|aka\s+|alt(?:ernate)?\s+title:\s+)", re.IGNORECASE)


def _restore_article(text: str) -> str:
    """Moves a displaced leading article back to the front."""
    text = text.strip()

    prefix = ""
    marker = _ALT_TITLE_PREFIX.match(text)
    if marker:
        prefix = marker.group(0)
        text = text[marker.end():]

    match = _ARTICLE_SUFFIX.match(text)
    if not match:
        return f"{prefix}{text}"

    stem = match.group("stem").strip()
    article = match.group("article")

    # "Die, Mommie, Die" is the film *Die Mommie Die!* — the trailing "Die" is a
    # verb, not the German article, and moving it yields "Die Die, Mommie". A title
    # already opening with that word was never article-inverted. The boundary match
    # matters: the stem here is "Die, Mommie", so a plain "Die " prefix test misses.
    if re.match(rf"{re.escape(article)}\b", stem, re.IGNORECASE):
        return f"{prefix}{text}"

    # "Amour fou, L'" rejoins without a space: "L'Amour fou".
    joiner = "" if article.endswith("'") else " "
    return f"{prefix}{article}{joiner}{stem}"


def natural_title(title: str) -> str:
    """Renders a MovieLens title the way a person would write it.

    Trailing bracketed groups are peeled off first so the article inside each one
    is restored independently, which matters for entries like
    "Postman, The (Postino, Il)" -> "The Postman (Il Postino)".
    """
    text = (title or "").strip()
    suffixes: List[str] = []

    while True:
        match = _PARENTHETICAL.search(text)
        if not match:
            break
        suffixes.append(match.group(1).strip())
        text = text[: match.start()]

    parts = [_restore_article(text)]
    for inner in reversed(suffixes):
        parts.append(f"({_restore_article(inner)})")
    return " ".join(part for part in parts if part)


def split_title(title: str) -> tuple[str, Optional[int]]:
    """Separates "Matrix, The (1999)" into ("The Matrix", 1999)."""
    raw = title or ""
    match = _YEAR_SUFFIX.search(raw)
    if match:
        return natural_title(_YEAR_SUFFIX.sub("", raw)), int(match.group(1))
    return natural_title(raw), None


def split_list(value: Optional[str], separator: str = ",") -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(separator) if part.strip()]


def parse_billing(value: Optional[str]) -> List[dict]:
    """Decodes the compact cast_json blob into named fields.

    Stored with one-letter keys because the column carries ten entries for each of
    ~94k titles; expanded here so the API surface stays readable. A malformed blob
    degrades to an empty list rather than failing the whole response.
    """
    if not value:
        return []
    try:
        entries = json.loads(value)
    except (ValueError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    return [
        {"name": entry["n"], "character": entry.get("c"), "profile_path": entry.get("p")}
        for entry in entries
        if isinstance(entry, dict) and entry.get("n")
    ]


def split_genres(value: Optional[str]) -> List[str]:
    """Genre list with MovieLens's "(no genres listed)" filler removed.

    6,570 displayable titles carry that literal string. It is a marker for absent
    data, not a genre, and it rendered as a chip on the detail page.
    """
    return [genre for genre in split_list(value, "|") if genre != GENRE_PLACEHOLDER]


# --------------------------------------------------------------------- auth


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int = Field(..., description="Token lifetime in seconds")


class TokenData(BaseModel):
    username: Optional[str] = None


#: Passwords that a dictionary attack tries in its first few hundred guesses.
#: Length alone does not save "password123"; this is the short list that a length
#: rule most commonly lets through.
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "12345678", "123456789",
    "1234567890", "qwertyuiop", "qwerty123", "iloveyou", "welcome1", "admin123",
    "letmein1", "abc12345", "football", "baseball", "sunshine", "princess",
    "monkey12", "trustno1", "changeme", "starwars", "whatever", "superman",
}


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

    @field_validator("username")
    @classmethod
    def _clean_username(cls, value: str) -> str:
        """Restricts usernames to characters that cannot be confused or injected.

        Without this, a username can contain whitespace, control characters or
        right-to-left overrides -- so two visually identical accounts can exist,
        and a display of the name can be made to lie about which one it is.
        """
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,50}", value):
            raise ValueError(
                "Username may contain only letters, numbers, dots, underscores and hyphens"
            )
        return value


class UserCreate(UserBase):
    # 8 is the NIST SP 800-63B floor. The upper bound is bcrypt's: it reads only
    # the first 72 bytes, so accepting more would silently ignore the rest and
    # make two different long passwords interchangeable.
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def _reject_weak(cls, value: str) -> str:
        if value.lower() in _COMMON_PASSWORDS:
            raise ValueError("That password is too common. Choose something less guessable.")
        if len(set(value)) < 4:
            raise ValueError("Password is too repetitive. Use a greater variety of characters.")
        return value


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Aggregate taste summary shown on the profile page."""

    ratings_count: int
    watchlist_count: int
    average_rating: float
    top_genres: List["GenreCount"] = Field(default_factory=list)
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    decades: dict[str, int] = Field(default_factory=dict)


# -------------------------------------------------------------------- movies


class MovieCard(BaseModel):
    """Minimal shape for grids, carousels and search results."""

    id: int
    title: str
    year: Optional[int] = None
    genres: List[str] = Field(default_factory=list)
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    bayes_score: Optional[float] = None
    runtime: Optional[int] = None
    rating_count: Optional[int] = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _from_orm_row(cls, data: Any) -> Any:
        """Normalises an ORM row: strips the year from the title, splits genres."""
        if isinstance(data, dict):
            return data
        title, year = split_title(getattr(data, "title", "") or "")
        return {
            "id": getattr(data, "id"),
            "title": title,
            "year": getattr(data, "release_year", None) or year,
            "genres": split_genres(getattr(data, "genres", None)),
            "poster_path": getattr(data, "poster_path", None),
            "backdrop_path": getattr(data, "backdrop_path", None),
            "vote_average": getattr(data, "vote_average", None),
            "bayes_score": getattr(data, "bayes_score", None),
            "runtime": getattr(data, "runtime", None),
            "rating_count": getattr(data, "rating_count", None),
        }


class CastMember(BaseModel):
    """One billed performer, with the portrait path the detail page renders."""

    name: str
    character: Optional[str] = None
    profile_path: Optional[str] = None


class MovieDetail(MovieCard):
    """Full record for the detail page."""

    overview: Optional[str] = None
    tagline: Optional[str] = None
    director: Optional[str] = None
    cast: List[str] = Field(default_factory=list)
    billing: List[CastMember] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    trailer_key: Optional[str] = None
    release_date: Optional[str] = None
    original_language: Optional[str] = None
    vote_count: Optional[int] = None
    rating_mean: Optional[float] = None
    popularity_score: Optional[float] = None
    trending_score: Optional[float] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _from_orm_row(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        title, year = split_title(getattr(data, "title", "") or "")
        return {
            "id": getattr(data, "id"),
            "title": title,
            "year": getattr(data, "release_year", None) or year,
            "genres": split_genres(getattr(data, "genres", None)),
            "poster_path": getattr(data, "poster_path", None),
            "backdrop_path": getattr(data, "backdrop_path", None),
            "vote_average": getattr(data, "vote_average", None),
            "bayes_score": getattr(data, "bayes_score", None),
            "runtime": getattr(data, "runtime", None),
            "rating_count": getattr(data, "rating_count", None),
            "overview": getattr(data, "overview", None),
            "tagline": getattr(data, "tagline", None),
            "director": getattr(data, "director", None),
            "cast": split_list(getattr(data, "cast_list", None)),
            "billing": parse_billing(getattr(data, "cast_json", None)),
            "keywords": split_list(getattr(data, "keywords", None)),
            "tags": split_list(getattr(data, "user_tags", None), " ")[:12],
            "trailer_key": getattr(data, "trailer_key", None),
            "release_date": getattr(data, "release_date", None),
            "original_language": getattr(data, "original_language", None),
            "vote_count": getattr(data, "vote_count", None),
            "rating_mean": getattr(data, "rating_mean", None),
            "popularity_score": getattr(data, "popularity_score", None),
            "trending_score": getattr(data, "trending_score", None),
            "imdb_id": getattr(data, "imdb_id", None),
            "tmdb_id": getattr(data, "tmdb_id", None),
        }


# ---------------------------------------------------------------- pagination


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedMovies(BaseModel):
    items: List[MovieCard]
    pagination: PaginationMeta


def build_pagination_meta(page: int, page_size: int, total_items: int) -> PaginationMeta:
    total_pages = max(1, math.ceil(total_items / page_size)) if page_size else 1
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


# -------------------------------------------------------------------- genres


class GenreCount(BaseModel):
    name: str
    movie_count: int


class GenreListResponse(BaseModel):
    genres: List[GenreCount]
    total_genres: int


# ---------------------------------------------------------- ratings/watchlist


class RatingCreate(BaseModel):
    movie_id: int
    rating: float = Field(..., ge=0.5, le=5.0)


class RatingResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    rating: float
    timestamp: datetime

    class Config:
        from_attributes = True


class RatedMovie(BaseModel):
    """A rating joined to its movie, for the ratings page."""

    rating: float
    rated_at: datetime
    movie: MovieCard


class PaginatedRatedMovies(BaseModel):
    items: List[RatedMovie]
    pagination: PaginationMeta


class WatchlistCreate(BaseModel):
    movie_id: int


class WatchlistEntry(BaseModel):
    added_at: datetime
    movie: MovieCard


class PaginatedWatchlist(BaseModel):
    items: List[WatchlistEntry]
    pagination: PaginationMeta


# ----------------------------------------------------------- recommendations


class BecauseOf(BaseModel):
    """One profile title that measurably contributed to a recommendation."""

    movie_id: int
    title: str
    weight: float


class Explanation(BaseModel):
    kind: str = Field(..., description="hybrid | cold_start")
    headline: str
    because_of: List[BecauseOf] = Field(default_factory=list)
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Standardised per-model contributions to the blended score",
    )
    shared_genres: List[str] = Field(default_factory=list)


class RecommendedMovie(MovieCard):
    score: float
    rank: int
    explanation: Optional[Explanation] = None


class RecommendationResponse(BaseModel):
    strategy: str
    movies: List[RecommendedMovie]
    generated_at: datetime
    execution_ms: float
    cached: bool = False


class MovieRow(BaseModel):
    """One titled carousel on the home page."""

    key: str
    title: str
    subtitle: Optional[str] = None
    items: List[MovieCard]


class HomeFeed(BaseModel):
    """Every home-page row in a single response.

    The home page previously issued one request per section. Bundling them removes
    a round trip per row and lets the whole page paint in one pass.
    """

    hero: List[MovieCard] = Field(default_factory=list)
    rows: List[MovieRow] = Field(default_factory=list)
    generated_at: datetime
    execution_ms: float


class CatalogueStats(BaseModel):
    total_movies: int
    with_posters: int
    poster_coverage: float
    total_ratings_modelled: int
    catalogue_years: dict[str, int]
    enrichment_pending: int
    engine: dict[str, Any] = Field(default_factory=dict)


UserStats.model_rebuild()
