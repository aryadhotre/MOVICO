"""Password hashing and JWT issue/verification."""

import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.database.connection import get_db
from app.database.models import User

ALGORITHM = "HS256"

# OAuth2 scheme definition
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def _encode_password(password: str) -> bytes:
    """Encodes a password for bcrypt, which rejects inputs over 72 bytes.

    bcrypt only ever consumed the first 72 bytes; recent releases raise instead of
    silently truncating, which would turn a long passphrase into a 500.
    """
    return password.encode("utf-8")[:72]

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies that a plain text password matches a bcrypt hashed password."""
    try:
        return bcrypt.checkpw(_encode_password(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database; treat as a failed login rather than a crash.
        return False

def get_password_hash(password: str) -> str:
    """Generates a bcrypt hash from a plain text password."""
    return bcrypt.hashpw(_encode_password(password), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT access token containing arbitrary payload data.

    Times are timezone-aware UTC. ``datetime.utcnow()`` returns a *naive* datetime
    that merely happens to hold UTC, which is deprecated in 3.12 and a standing
    trap: compared against an aware value it raises, and read by anything that
    assumes local time it silently shifts the expiry by the offset.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency that decodes the access token and loads the authenticated user.

    ``algorithms`` is pinned to a single symmetric algorithm and ``exp`` is
    required. Both matter: accepting a list the token gets to choose from is how
    the ``alg: none`` and RS256-verified-as-HS256 forgeries work, and a token
    without ``exp`` would otherwise be valid forever.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        username = payload.get("sub")
        if not username or not isinstance(username, str):
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception from None

    # Case-insensitive, matching how registration checks for clashes: usernames
    # are unique case-insensitively, so looking up case-sensitively here would
    # reject a token issued to "Arya" for the account stored as "arya".
    user = db.execute(
        select(User).where(func.lower(User.username) == username.lower())
    ).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
