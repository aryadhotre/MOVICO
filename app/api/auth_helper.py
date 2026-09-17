import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.database.connection import get_db
from app.database.models import User

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
    """Generates a signed JWT access token containing arbitrary payload data."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency that decodes access token and retrieves the authenticated database User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user
